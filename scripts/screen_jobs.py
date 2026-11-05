#!/usr/bin/env python3
"""
screen_jobs.py — Stage 2 of the job application pipeline.

Scores discovered jobs against Eli's profile (Section 4 of the architecture doc) and
buckets them into auto-apply / review / skip tiers.

Default scoring is deterministic and free (keyword + location + date heuristics), so this
runs with no API key. Pass --llm to use Claude for nuanced field-alignment scoring when
ANTHROPIC_API_KEY is set (falls back to heuristic if unavailable).

Usage:
    python screen_jobs.py --in data/new_jobs.json --out data/screened.json
    python screen_jobs.py --in data/new_jobs.json --out data/screened.json --md data/screened.md
    python screen_jobs.py --in data/samples/linkedin_sample.json --out /tmp/out.json --llm

Input: a JSON array of job records. Field names are normalized from common scraper outputs
(LinkedIn Jobs Scraper, Tavily). Recognized keys per job (all optional except a title):
    title / jobTitle, company / companyName, location, description / descriptionText,
    salary / salaryInfo, postedAt / postedDate, applicantsCount, url / jobUrl / link,
    workplaceType (remote/hybrid/onsite), deadline (ISO date), employmentType
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = ROOT / "config"


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_profile() -> dict:
    return load_json(CONFIG / "eli_profile.json")


def load_weights() -> dict:
    return load_json(CONFIG / "scoring_weights.json")


# --------------------------------------------------------------------------- #
# Normalization
# --------------------------------------------------------------------------- #
def _first(d: dict, *keys: str, default: str = "") -> str:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if v not in (None, "", []):
            return str(v)
    return default


def normalize_job(raw: dict) -> dict:
    """Map a raw scraper record into the fields the scorer expects."""
    return {
        "title": _first(raw, "title", "jobTitle", "position"),
        "company": _first(raw, "company", "companyName", "organization", "employer"),
        "location": _first(raw, "location", "jobLocation", "city"),
        "description": _first(raw, "description", "descriptionText", "jobDescription", "summary"),
        "salary": _first(raw, "salary", "salaryInfo", "compensation", "pay"),
        "posted": _first(raw, "postedAt", "postedDate", "datePosted", "publishedAt"),
        "deadline": _first(raw, "deadline", "applicationDeadline", "closeDate"),
        "workplace_type": _first(raw, "workplaceType", "remote", "workplace").lower(),
        "employment_type": _first(raw, "employmentType", "jobType", "type").lower(),
        "url": _first(raw, "url", "jobUrl", "link", "applyUrl"),
        "_raw": raw,
    }


def dedup_key(job: dict) -> str:
    """Cross-platform dedup on company + title + location (per architecture review)."""
    norm = lambda s: re.sub(r"\s+", " ", s.lower().strip())
    return f"{norm(job['company'])}|{norm(job['title'])}|{norm(job['location'])}"


# --------------------------------------------------------------------------- #
# Scoring dimensions
# --------------------------------------------------------------------------- #
def _has_term(haystack: str, term: str) -> bool:
    """Whole-word / whole-phrase match (case-insensitive). Avoids 'hr' inside 'hours'."""
    return re.search(rf"\b{re.escape(term.lower())}\b", haystack) is not None


def score_field(job: dict, profile: dict, w: dict) -> tuple[float, str]:
    prefs = profile["screening_preferences"]
    detail = w["scoring_detail"]["field"]
    haystack = f"{job['title']} {job['description']}".lower()

    hits = sorted({kw for kw in prefs["focus_keywords"] if _has_term(haystack, kw)})
    negs = sorted({kw for kw in prefs["negative_keywords"] if _has_term(haystack, kw)})

    pts = min(len(hits) * detail["per_keyword_points"], detail["strong_match_points"])
    pts -= len(negs) * detail["negative_keyword_penalty"]
    pts = max(0, min(pts, w["dimensions"]["field_alignment"]["max"]))

    note = f"matched {hits or 'none'}"
    if negs:
        note += f"; penalized {negs}"
    return float(pts), note


def score_location(job: dict, profile: dict, w: dict) -> tuple[float, str]:
    prefs = profile["screening_preferences"]
    d = w["scoring_detail"]["location"]
    loc = job["location"].lower()
    wp = job["workplace_type"]

    if "remote" in loc or "remote" in wp:
        return float(d["remote_points"]), "remote"
    for p in prefs["preferred_locations"]:
        token = p.lower().replace(" ca", "").replace(" or", "").strip()
        if token and token in loc:
            return float(d["preferred_points"]), f"preferred ({p})"
    # Greater Bay Area (~15mi of Berkeley): acceptable but lower than top-preferred
    bay_area_tokens = [b.lower().replace(" ca", "").strip()
                       for b in prefs.get("greater_bay_area", [])]
    if any(t and t in loc for t in bay_area_tokens):
        return float(d.get("bay_area_points", 7)), f"greater Bay Area ({loc})"
    # Also catch generic "Bay Area" or "San Jose" etc.
    if any(x in loc for x in ("bay area", "peninsula", "east bay", "south bay",
                               "north bay", "marin", "contra costa")):
        return float(d.get("bay_area_points", 7)), f"greater Bay Area ({loc})"
    if not loc:
        return float(d["us_other_points"]), "location unknown"
    # California but outside Bay Area
    if "ca" in loc or "california" in loc:
        return float(d.get("ca_other_points", 3)), f"California, outside Bay Area"
    intl = any(x in loc for x in ("uk", "united kingdom", "europe", "emea", "canada",
                                  "australia", "india", "germany", "france", "ireland"))
    if intl:
        return float(d["international_points"]), "international"
    return float(d["us_other_points"]), "US, non-preferred"


def _parse_date(s: str) -> dt.date | None:
    s = s.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y", "%d %b %Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return dt.date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    return None


def score_timing(job: dict, w: dict, today: dt.date) -> tuple[float, str]:
    t = w["scoring_detail"]["timing"]
    deadline = _parse_date(job["deadline"])
    if deadline is None:
        return float(t["no_deadline_points"]), "no deadline listed"
    days = (deadline - today).days
    if days < 0:
        return float(t["expired_points"]), f"deadline passed ({deadline})"
    if days <= t["soon_days"]:
        pts = min(t["open_aligned_points"] + t["deadline_soon_bonus"],
                  w["dimensions"]["timing"]["max"])
        return float(pts), f"closes in {days}d ({deadline})"
    return float(t["deadline_far_points"]), f"closes in {days}d ({deadline})"


def score_comp(job: dict, w: dict) -> tuple[float, str]:
    d = w["scoring_detail"]["compensation"]
    text = f"{job['salary']} {job['description']}".lower()
    if any(x in text for x in ("$", "/hr", "per hour", "salary", "paid", "stipend")) and "unpaid" not in text:
        if "stipend" in text and "$" not in text:
            return float(d["stipend_points"]), "stipend"
        return float(d["paid_points"]), "paid"
    if "unpaid" in text:
        return float(d["unpaid_points"]), "unpaid"
    return float(d["unknown_points"]), "comp not stated"


def score_growth(job: dict, w: dict) -> tuple[float, str]:
    """Light heuristic: known-brand / research / fellowship signals nudge growth up."""
    base = w["scoring_detail"]["growth_default"]
    text = f"{job['company']} {job['title']}".lower()
    strong = ("latham", "perkins coie", "doj", "department of justice", "court",
              "berkeley", "brattle", "general atomics", "fellow", "research")
    bump = 2 if any(s in text for s in strong) else 0
    pts = min(base + bump, w["dimensions"]["growth_signal"]["max"])
    return float(pts), ("notable signal" if bump else "baseline")


# --------------------------------------------------------------------------- #
# Optional LLM field scoring
# --------------------------------------------------------------------------- #
def llm_field_score(job: dict, profile: dict, w: dict) -> tuple[float, str] | None:
    """Use Claude to score field alignment 0-10. Returns None if unavailable."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic(api_key=key)
        prompt = (
            "Score 0-10 how well this job fits the candidate's focus areas: "
            f"{', '.join(profile['screening_preferences']['focus_areas'])}.\n\n"
            f"JOB TITLE: {job['title']}\nCOMPANY: {job['company']}\n"
            f"DESCRIPTION: {job['description'][:2000]}\n\n"
            'Reply with ONLY JSON: {"score": <int 0-10>, "reason": "<8 words>"}'
        )
        model = os.environ.get("SCREEN_MODEL", "claude-sonnet-4-5")
        msg = client.messages.create(
            model=model, max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)
        pts = max(0, min(int(data["score"]), w["dimensions"]["field_alignment"]["max"]))
        return float(pts), f"LLM: {data.get('reason', '')}"
    except Exception as e:  # noqa: BLE001
        print(f"  [llm] field scoring failed ({e}); using heuristic", file=sys.stderr)
        return None


# --------------------------------------------------------------------------- #
# Compose
# --------------------------------------------------------------------------- #
def tier_for(score: float, w: dict) -> str:
    if score >= w["tiers"]["auto_apply"]["min"]:
        return "auto_apply"
    if score >= w["tiers"]["review"]["min"]:
        return "review"
    return "skip"


def score_job(job: dict, profile: dict, w: dict, today: dt.date, use_llm: bool) -> dict:
    field = (use_llm and llm_field_score(job, profile, w)) or score_field(job, profile, w)
    loc = score_location(job, profile, w)
    timing = score_timing(job, w, today)
    comp = score_comp(job, w)
    growth = score_growth(job, w)

    breakdown = {
        "field_alignment": {"score": field[0], "note": field[1]},
        "location_fit": {"score": loc[0], "note": loc[1]},
        "timing": {"score": timing[0], "note": timing[1]},
        "compensation": {"score": comp[0], "note": comp[1]},
        "growth_signal": {"score": growth[0], "note": growth[1]},
    }
    composite = round(sum(d["score"] for d in breakdown.values()), 1)
    tier = tier_for(composite, w)
    rationale = (
        f"{job['title']} @ {job['company']} — {breakdown['field_alignment']['note']}; "
        f"{loc[1]}; {timing[1]}; {comp[1]}."
    )
    return {
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "url": job["url"],
        "deadline": job["deadline"],
        "composite_score": composite,
        "composite_max": w["composite_max"],
        "tier": tier,
        "rationale": rationale,
        "breakdown": breakdown,
        "status": "screened",
        "dedup_key": dedup_key(job),
    }


def screen(jobs_raw: list[dict], profile: dict, w: dict, use_llm: bool) -> list[dict]:
    today = dt.date.today()
    seen: set[str] = set()
    out: list[dict] = []
    for raw in jobs_raw:
        job = normalize_job(raw)
        if not job["title"]:
            continue
        key = dedup_key(job)
        if key in seen:
            continue
        seen.add(key)
        out.append(score_job(job, profile, w, today, use_llm))
    out.sort(key=lambda r: r["composite_score"], reverse=True)
    return out


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def to_markdown(results: list[dict], w: dict) -> str:
    by_tier: dict[str, list[dict]] = {"auto_apply": [], "review": [], "skip": []}
    for r in results:
        by_tier[r["tier"]].append(r)
    lines = [f"# Screening results — {dt.date.today().isoformat()}",
             f"{len(results)} jobs scored (max {w['composite_max']}).\n"]
    titles = {"auto_apply": "Auto-apply (≥30)", "review": "Review (20–29)", "skip": "Skip (<20)"}
    for tier in ("auto_apply", "review", "skip"):
        rows = by_tier[tier]
        lines.append(f"\n## {titles[tier]} — {len(rows)}\n")
        for r in rows:
            lines.append(f"- **{r['composite_score']}/{w['composite_max']}** "
                         f"{r['title']} @ {r['company']} ({r['location']}) — {r['rationale']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Score and tier discovered jobs.")
    ap.add_argument("--in", dest="inp", required=True, help="input JSON array of jobs")
    ap.add_argument("--out", dest="out", required=True, help="output JSON path")
    ap.add_argument("--md", dest="md", help="optional markdown summary path")
    ap.add_argument("--llm", action="store_true", help="use Claude for field scoring if ANTHROPIC_API_KEY set")
    args = ap.parse_args()

    profile, w = load_profile(), load_weights()
    raw = load_json(Path(args.inp))
    if isinstance(raw, dict):
        raw = raw.get("items") or raw.get("jobs") or [raw]
    results = screen(raw, profile, w, args.llm)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    counts = {t: sum(1 for r in results if r["tier"] == t) for t in ("auto_apply", "review", "skip")}
    print(f"Scored {len(results)} jobs -> {args.out}")
    print(f"  auto_apply={counts['auto_apply']}  review={counts['review']}  skip={counts['skip']}")

    if args.md:
        Path(args.md).write_text(to_markdown(results, w), encoding="utf-8")
        print(f"  markdown -> {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
