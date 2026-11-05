#!/usr/bin/env python3
"""
normalize_discovery.py — Merge and deduplicate job records from multiple sources.

Takes raw outputs from Tavily search results and/or Apify LinkedIn scraper,
normalizes them into the standard job format that screen_jobs.py expects,
deduplicates against previously seen jobs, and writes new_jobs.json.

Usage:
    python normalize_discovery.py --tavily data/tavily_raw.json --out data/new_jobs.json
    python normalize_discovery.py --apify data/apify_latest.json --out data/new_jobs.json
    python normalize_discovery.py --tavily data/tavily_raw.json --apify data/apify_latest.json \
        --out data/new_jobs.json
    python normalize_discovery.py --tavily data/tavily_raw.json --out data/new_jobs.json --no-dedup
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import hashlib
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SEEN_DB = ROOT / "data" / "seen_jobs.json"

_CITIES = {"san francisco", "berkeley", "oakland", "portland", "sacramento",
           "los angeles", "new york", "seattle", "denver", "austin", "chicago",
           "boston", "washington dc", "washington d.c."}


def dedup_key(title: str, company: str, location: str) -> str:
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())
    raw = f"{norm(company)}|{norm(title)}|{norm(location)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def load_seen() -> dict:
    if SEEN_DB.exists():
        data = json.loads(SEEN_DB.read_text(encoding="utf-8"))
        return data.get("seen", {})
    return {}


def save_seen(seen: dict) -> None:
    SEEN_DB.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0",
        "description": "Dedup tracker.",
        "seen": seen,
    }
    SEEN_DB.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def normalize_tavily_result(result: dict) -> dict | None:
    """Convert a single Tavily search result into the standard job format."""
    title_raw = result.get("title", "")
    url = result.get("url", "")
    content = result.get("content", "")
    published = result.get("published_date", "")

    if not title_raw or not url:
        return None

    job_title = title_raw
    company = ""
    location = ""

    # --- Step 1: Extract company from "X hiring Y" pattern FIRST ---
    hiring_match = re.match(r"^(.+?)\s+hiring\s+", job_title, re.IGNORECASE)
    if hiring_match:
        company = hiring_match.group(1).strip()
        job_title = job_title[hiring_match.end():].strip()

    # --- Step 2: If no hiring pattern, try separator-based parsing ---
    if not company:
        if " at " in title_raw:
            parts = title_raw.split(" at ", 1)
            job_title = parts[0].strip()
            remainder = parts[1].strip()
            if " - " in remainder:
                cp = remainder.rsplit(" - ", 1)
                company = cp[0].strip()
                location = cp[1].strip()
            else:
                company = remainder
        elif " | " in title_raw:
            parts = title_raw.split(" | ", 1)
            job_title = parts[0].strip()
            company = parts[1].strip()
        elif "—" in title_raw:  # em-dash
            parts = title_raw.split("—", 1)
            job_title = parts[0].strip()
            company = parts[1].strip()
        elif " - " in title_raw:
            parts = title_raw.rsplit(" - ", 1)
            tail = parts[1].strip() if len(parts) > 1 else ""
            loc_like = bool(re.search(
                r"(?:CA|OR|NY|TX|WA|DC|Remote|LinkedIn|Indeed|Idealist)\b", tail
            ))
            if loc_like:
                head = parts[0].strip()
                location = tail
                if " - " in head:
                    hp = head.split(" - ", 1)
                    job_title = hp[0].strip()
                    company = hp[1].strip()
                else:
                    job_title = head
            else:
                job_title = parts[0].strip()
                company = tail

    # --- Step 3: Post-parse cleanup ---
    # Separate trailing location from company name
    if company and not location:
        loc_tail = re.search(
            r"\s*[-–]\s*((?:San Francisco|Berkeley|Oakland|Portland|Sacramento|"
            r"Los Angeles|New York|Seattle|Denver|Austin|Chicago|Boston|Remote|"
            r"Washington\s*,?\s*D\.?C\.?|[\w\s]+,\s*(?:CA|OR|NY|TX|WA|DC|CO|MA|IL)))\s*$",
            company, re.IGNORECASE
        )
        if loc_tail:
            location = loc_tail.group(1).strip()
            company = company[:loc_tail.start()].strip()

    # If company is just a location word or city name, move it to location
    if company.lower() in ("remote", "hybrid", "on-site"):
        location = location or company
        company = ""
    if company.lower().strip(" ,") in _CITIES:
        if not location:
            location = company
        company = ""

    # Try to extract location from content
    if not location and content:
        for pat in [
            r"(Remote\s+in\s+[\w\s]+,\s*[A-Z]{2})",
            r"(Berkeley|San Francisco|Oakland|Portland|Sacramento|Remote|Washington\s*,?\s*D\.?C\.?)",
            r"([\w\s]+,\s*(?:CA|OR|NY|TX|WA|DC))\b",
        ]:
            m = re.search(pat, content, re.IGNORECASE)
            if m:
                location = m.group(1).strip()
                break

    # Try to extract company from content if still unknown
    if not company and content:
        m = re.match(r"^([A-Z][\w\s&\'.,-]+?)\s+(?:is|was|has|are|seeks|hiring|looking)\b", content)
        if m:
            company = m.group(1).strip()

    # Clean up suffixes
    for suffix in [" | LinkedIn", " - LinkedIn", " - Indeed", " | Indeed.com",
                   " - Idealist", " | Climatebase", " - USAJobs"]:
        job_title = job_title.replace(suffix, "").strip()
        company = company.replace(suffix, "").strip()

    return {
        "title": job_title,
        "company": company or "(unknown)",
        "location": location,
        "url": url,
        "description": content,
        "source": "tavily",
        "posted_date": published[:10] if published else "",
        "discovered_date": dt.date.today().isoformat(),
    }


def normalize_apify_result(result: dict) -> dict:
    """Convert an Apify LinkedIn Jobs Scraper result into the standard format."""
    return {
        "title": result.get("title", ""),
        "company": result.get("companyName", result.get("company", "")),
        "location": result.get("location", ""),
        "url": result.get("link", result.get("url", "")),
        "description": result.get("descriptionText", result.get("description", "")),
        "salary": result.get("salary", ""),
        "applicants_count": result.get("applicantsCount", ""),
        "employment_type": result.get("employmentType", ""),
        "posted_date": result.get("postedAt", result.get("postedDate", "")),
        "source": "apify_linkedin",
        "discovered_date": dt.date.today().isoformat(),
        "companyName": result.get("companyName", ""),
        "descriptionText": result.get("descriptionText", ""),
        "link": result.get("link", ""),
        "postedAt": result.get("postedAt", ""),
    }


def load_and_normalize(path: Path, source: str) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raw = [raw]
    results = []
    for item in raw:
        if source == "tavily":
            norm = normalize_tavily_result(item)
        elif source == "apify":
            norm = normalize_apify_result(item)
        else:
            norm = item
        if norm and norm.get("title"):
            results.append(norm)
    return results


def deduplicate(jobs: list[dict], seen: dict, skip_dedup: bool = False) -> tuple[list[dict], dict]:
    if skip_dedup:
        return jobs, seen
    new_jobs = []
    today = dt.date.today().isoformat()
    for job in jobs:
        key = dedup_key(
            job.get("title", ""),
            job.get("company", job.get("companyName", "")),
            job.get("location", ""),
        )
        if key not in seen:
            seen[key] = today
            new_jobs.append(job)
    return new_jobs, seen


def write_summary(jobs: list[dict], path: Path) -> None:
    today = dt.date.today().isoformat()
    lines = [
        f"# Job Discovery Summary — {today}\n",
        f"**New jobs found:** {len(jobs)}\n",
    ]
    if not jobs:
        lines.append("No new jobs discovered today.\n")
    else:
        by_source: dict[str, list] = {}
        for j in jobs:
            src = j.get("source", "unknown")
            by_source.setdefault(src, []).append(j)
        for source, source_jobs in sorted(by_source.items()):
            lines.append(f"\n## {source.replace('_', ' ').title()} ({len(source_jobs)} jobs)\n")
            for j in source_jobs:
                title = j.get("title", "Unknown")
                company = j.get("company", j.get("companyName", "Unknown"))
                loc = j.get("location", "")
                url = j.get("url", j.get("link", ""))
                loc_str = f" — {loc}" if loc else ""
                if url:
                    lines.append(f"- [{title}]({url}) @ {company}{loc_str}")
                else:
                    lines.append(f"- {title} @ {company}{loc_str}")
            lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  summary: {path}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge and deduplicate discovery results.")
    ap.add_argument("--tavily", help="Path to Tavily raw results JSON")
    ap.add_argument("--apify", help="[DEPRECATED/IGNORED — Apify removed 2026-08-17] Path to Apify LinkedIn raw results JSON")
    ap.add_argument("--out", required=True, help="Output path for new_jobs.json")
    ap.add_argument("--no-dedup", action="store_true", help="Skip deduplication")
    ap.add_argument("--summary", help="Path to write a markdown summary")
    args = ap.parse_args()

    all_jobs: list[dict] = []

    if args.tavily:
        tavily_path = Path(args.tavily)
        if tavily_path.exists():
            tavily_jobs = load_and_normalize(tavily_path, "tavily")
            all_jobs.extend(tavily_jobs)
            print(f"[tavily] Loaded {len(tavily_jobs)} results from {tavily_path}")
        else:
            print(f"[tavily] File not found: {tavily_path}")

    if args.apify:
        # Apify was removed 2026-08-17 (it now charges per LinkedIn scraper run).
        # The flag is accepted for backward compatibility but intentionally ignored
        # so no Apify data can re-enter the pipeline. LinkedIn/Indeed/Idealist
        # coverage now comes from the Tavily + WebSearch discovery step.
        print("[apify] IGNORED — Apify was disabled on 2026-08-17. "
              "Discovery now uses Tavily + WebSearch only.")

    if not all_jobs:
        print("[warn] No jobs loaded from any source.")
        Path(args.out).write_text("[]", encoding="utf-8")
        return 0

    seen = load_seen()
    seen_before = len(seen)
    new_jobs, seen = deduplicate(all_jobs, seen, skip_dedup=args.no_dedup)
    save_seen(seen)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(new_jobs, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n[result] {len(new_jobs)} new jobs (of {len(all_jobs)} total; {len(seen) - seen_before} added to dedup tracker)")
    print(f"  output: {out_path}")

    if args.summary:
        write_summary(new_jobs, Path(args.summary))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
