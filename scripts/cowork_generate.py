#!/usr/bin/env python3
"""
cowork_generate.py — Cowork-side cover letter generation (no API key required).

This script is called from inside a Cowork scheduled task. It reads a handoff file
from processing/, builds the cover letter generation prompt, and writes it to
data/uploads/<company-slug>_generation_prompt.txt so Cowork can run the generation
inline and save the result.

After Cowork generates the body and saves it to data/uploads/<company-slug>_body.txt,
Claude Code runs:
    python scripts/generate_cover_letter.py --company "..." --body-file data/uploads/..._body.txt

This avoids any Anthropic API key requirement — Cowork IS Claude.

Usage (from inside a Cowork task):
    python scripts/cowork_generate.py --status
    python scripts/cowork_generate.py --job handoff_queue/processing/<file>.json
    python scripts/cowork_generate.py --all   # generates prompts for all processing jobs

Output per job:
    data/uploads/<slug>_generation_prompt.txt  ← paste into Cowork to generate body
    data/uploads/<slug>_body.txt               ← Cowork pastes generated body here
    (handoff file updated with body_file path)
"""
from __future__ import annotations

import argparse
import json
import re
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUEUE = ROOT / "handoff_queue"
UPLOADS = ROOT / "data" / "uploads"
CONFIG = ROOT / "config"
TEMPLATES = ROOT / "templates" / "prompts"
CACHE = ROOT / "data" / "research_cache"
PROMPT_TEMPLATE = TEMPLATES / "cover_letter_generation.txt"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "company"


def load_json(p: Path) -> dict | list:
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p: Path, data) -> None:
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def candidate_summary() -> str:
    p = load_json(CONFIG / "eli_profile.json")
    exp = "; ".join(f"{e['title']} ({e['org']})" for e in p["experience"])
    return (
        f"{p['identity']['name']} — {', '.join(p['education']['majors'])} at "
        f"{p['education']['school']}. Experience: {exp}. "
        f"Focus areas: {', '.join(p['interests'])}."
    )


def build_prompt(handoff: dict) -> str:
    job = handoff["job"]
    company = job.get("company", "")
    title = job.get("title", "")
    description = job.get("description", "(no description available)")

    # Load research brief if it exists
    brief_path_rel = handoff.get("research_brief")
    research_brief = "(no research brief available — run research_prompt.py first)"
    if brief_path_rel:
        brief_path = ROOT / brief_path_rel
        if brief_path.exists() and brief_path.stat().st_size > 200:
            research_brief = brief_path.read_text(encoding="utf-8")

    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")
    return template.format(
        candidate_summary=candidate_summary(),
        title=title,
        company=company,
        description=description,
        research_brief=research_brief,
    )


def process_job(handoff_path: Path) -> None:
    handoff = load_json(handoff_path)
    job = handoff["job"]
    company = job.get("company", "")
    title = job.get("title", "")
    company_slug = slug(company)

    UPLOADS.mkdir(parents=True, exist_ok=True)

    # Check if body already exists
    body_file = UPLOADS / f"{company_slug}_body.txt"
    if body_file.exists() and body_file.stat().st_size > 100:
        print(f"  [skip] Body already exists: {body_file.name}")
        return

    # Build and save the generation prompt
    prompt = build_prompt(handoff)
    prompt_file = UPLOADS / f"{company_slug}_generation_prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8")

    # Create body stub for Cowork to fill in
    body_file.write_text(
        f"# Cover letter body — {title} @ {company}\n"
        f"# Generated: {dt.date.today().isoformat()}\n"
        f"# INSTRUCTIONS FOR COWORK:\n"
        f"#   1. Read {prompt_file.name}\n"
        f"#   2. Generate the cover letter body following those instructions\n"
        f"#   3. Replace ALL content in this file with ONLY the body paragraphs\n"
        f"#   4. No headers, no Dear, no Sincerely — body paragraphs only\n\n"
        f"PASTE_GENERATED_BODY_HERE\n",
        encoding="utf-8",
    )

    # Update handoff with body file path
    handoff["body_file"] = f"data/uploads/{company_slug}_body.txt"
    handoff["generation_prompt"] = f"data/uploads/{company_slug}_generation_prompt.txt"
    save_json(handoff_path, handoff)

    print(f"\n  {title} @ {company}")
    print(f"  Prompt  -> {prompt_file}")
    print(f"  Body    -> {body_file}  (Cowork fills this in)")
    print(f"\n  COWORK NEXT STEP:")
    print(f"  Read {prompt_file.name} and generate the cover letter body.")
    print(f"  Save ONLY the body paragraphs to {body_file.name}.")
    print(f"\n  CLAUDE CODE NEXT STEP (after body is filled):")
    print(f"  python scripts/generate_cover_letter.py \\")
    print(f"    --company \"{company}\" --title \"{title}\" \\")
    print(f"    --body-file \"{body_file}\"")


def show_status() -> None:
    print("=== Cover Letter Generation Status ===\n")
    processing = list((QUEUE / "processing").glob("*.json"))
    if not processing:
        print("No jobs in processing/")
        return

    for p in sorted(processing):
        h = load_json(p)
        job = h["job"]
        company = job.get("company", "")
        title = job.get("title", "")
        company_slug = slug(company)

        has_research = bool(h.get("research_brief") and
                           (ROOT / h["research_brief"]).exists() and
                           (ROOT / h["research_brief"]).stat().st_size > 200)
        has_prompt = (UPLOADS / f"{company_slug}_generation_prompt.txt").exists()
        body_file = UPLOADS / f"{company_slug}_body.txt"
        has_body = body_file.exists() and "PASTE_GENERATED_BODY_HERE" not in body_file.read_text(encoding="utf-8")
        has_docx = bool(h.get("cover_letter"))

        print(f"  {title} @ {company}")
        print(f"    research brief : {'YES' if has_research else 'NO - run research_prompt.py'}")
        print(f"    gen prompt     : {'YES' if has_prompt else 'NO - run cowork_generate.py'}")
        print(f"    body (Cowork)  : {'YES' if has_body else 'NO - Cowork needs to generate'}")
        print(f"    .docx          : {'YES - ' + str(h['cover_letter']) if has_docx else 'NO - run generate_cover_letter.py --body-file'}")
        print()


def main() -> int:
    ap = argparse.ArgumentParser(description="Build cover letter generation prompts for Cowork.")
    ap.add_argument("--job", help="Path to a specific processing/*.json handoff file")
    ap.add_argument("--all", action="store_true", help="Process all jobs in processing/")
    ap.add_argument("--status", action="store_true", help="Show generation status for all processing jobs")
    args = ap.parse_args()

    if args.status:
        show_status()
        return 0

    if args.job:
        p = Path(args.job)
        if not p.exists():
            p = ROOT / args.job
        process_job(p)
        return 0

    if args.all:
        jobs = sorted((QUEUE / "processing").glob("*.json"))
        if not jobs:
            print("No jobs in processing/")
            return 0
        print(f"Building generation prompts for {len(jobs)} jobs...")
        for j in jobs:
            process_job(j)
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
