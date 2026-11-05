#!/usr/bin/env python3
"""
research_prompt.py — Stage 3 helper (free, Gemini Deep Research web-app workflow).

Eli runs company research by prompting Gemini Deep Research directly (no custom gem),
which is free under the Pro subscription. The paid Deep Research *API* is intentionally
NOT used. This script:

  1. Builds the exact research prompt to paste into Deep Research (one job per conversation).
  2. Writes a research_brief.md stub for that company where the Deep Research output gets pasted.
  3. Honors a 30-day research cache (Section 5.3): if a recent brief exists for the
     company, it tells you to reuse it instead of re-running.

Usage:
    # From a single job's fields:
    python research_prompt.py --title "Policy Intern" --company "Evolve California" \
        --location "Remote" --website "https://www.evolve-ca.org" --description-file jd.txt

    # From one record of a screened.json (by index or company match):
    python research_prompt.py --from data/screened.json --company "SB Energy"

Outputs (under data/research_cache/<company-slug>/):
    research_prompt.txt   <- paste this into Gemini Deep Research
    research_brief.md      <- paste the Deep Research output here; consumed by generate_cover_letter.py

Activate Deep Research first: + -> More tools -> Deep research (see docs/GEMINI_DEEP_RESEARCH.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = ROOT / "config"
CACHE = ROOT / "data" / "research_cache"
PROMPT_TEMPLATE = ROOT / "templates" / "prompts" / "research_prompt.txt"
GEMINI_URL = "https://gemini.google.com/app"
CACHE_TTL_DAYS = 30


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "company"


def candidate_summary() -> str:
    p = json.loads((CONFIG / "eli_profile.json").read_text(encoding="utf-8"))
    exp = "; ".join(f"{e['title']} ({e['org']})" for e in p["experience"])
    return (
        f"{p['identity']['name']} — {', '.join(p['education']['majors'])} at "
        f"{p['education']['school']}. Experience: {exp}. "
        f"Focus areas: {', '.join(p['interests'])}."
    )


def cache_status(company_dir: Path) -> str | None:
    brief = company_dir / "research_brief.md"
    if not brief.exists():
        return None
    age = (dt.date.today() - dt.date.fromtimestamp(brief.stat().st_mtime)).days
    if age <= CACHE_TTL_DAYS and brief.stat().st_size > 200:
        return f"cached brief is {age}d old (< {CACHE_TTL_DAYS}d TTL) — reuse it"
    return None


def load_description(args) -> str:
    if args.description_file:
        return Path(args.description_file).read_text(encoding="utf-8")
    return args.description or "(paste the full job description here)"


def from_screened(path: Path, company: str | None, index: int | None) -> dict:
    records = json.loads(path.read_text(encoding="utf-8"))
    if index is not None:
        return records[index]
    if company:
        for r in records:
            if company.lower() in r.get("company", "").lower():
                return r
        raise SystemExit(f"No record matching company '{company}' in {path}")
    raise SystemExit("--from requires --company or --index")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Gemini research prompt + brief stub.")
    ap.add_argument("--from", dest="src", help="screened.json to pull a job from")
    ap.add_argument("--index", type=int, help="record index in --from file")
    ap.add_argument("--title")
    ap.add_argument("--company")
    ap.add_argument("--location", default="")
    ap.add_argument("--website", default="(find the company website)")
    ap.add_argument("--description")
    ap.add_argument("--description-file")
    args = ap.parse_args()

    if args.src:
        rec = from_screened(Path(args.src), args.company, args.index)
        title = args.title or rec.get("title", "")
        company = args.company or rec.get("company", "")
        location = args.location or rec.get("location", "")
        website = args.website
        description = load_description(args)
        if description.startswith("(paste") and rec.get("breakdown"):
            description = rec.get("rationale", description)
    else:
        if not (args.title and args.company):
            raise SystemExit("Provide --title and --company (or --from + --company).")
        title, company, location = args.title, args.company, args.location
        website, description = args.website, load_description(args)

    company_dir = CACHE / slug(company)
    company_dir.mkdir(parents=True, exist_ok=True)

    reuse = cache_status(company_dir)
    if reuse:
        print(f"[cache] {company}: {reuse}")
        print(f"        {company_dir / 'research_brief.md'}")

    prompt = PROMPT_TEMPLATE.read_text(encoding="utf-8").format(
        candidate_summary=candidate_summary(),
        title=title, company=company, location=location,
        website=website, description=description,
    )
    (company_dir / "research_prompt.txt").write_text(prompt, encoding="utf-8")

    brief = company_dir / "research_brief.md"
    if not brief.exists():
        brief.write_text(
            f"# Research brief — {company}\n"
            f"<!-- Paste the Gemini Deep Research output below this line. "
            f"Generated prompt: research_prompt.txt -->\n\n",
            encoding="utf-8",
        )

    print(f"\nResearch prompt for: {title} @ {company}")
    print(f"  prompt  -> {company_dir / 'research_prompt.txt'}")
    print(f"  brief   -> {brief}  (paste Deep Research output here)")
    print("\nNext steps:")
    print(f"  1. Open Gemini (new chat): {GEMINI_URL}")
    print( "     Turn ON Deep Research: + -> More tools -> Deep research")
    print( "     (full guide: docs/GEMINI_DEEP_RESEARCH.md)")
    print( "  2. Paste research_prompt.txt; wait for the research panel to finish")
    print(f"  3. Paste the result into research_brief.md")
    print( "  4. Run: python scripts/generate_cover_letter.py --company "
          f"\"{company}\" --research \"{brief}\"")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
