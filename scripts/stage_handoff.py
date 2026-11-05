#!/usr/bin/env python3
"""
stage_handoff.py — Stage screened jobs into the handoff queue for processing.

Takes screened.json output from screen_jobs.py and creates individual handoff files
for jobs that meet the specified tier threshold.

Usage:
    # Stage all auto-apply jobs:
    python stage_handoff.py --in data/screened.json --tier auto_apply

    # Stage all auto-apply + review jobs:
    python stage_handoff.py --in data/screened.json --tier review

    # Stage a specific job by company name:
    python stage_handoff.py --in data/screened.json --company "SB Energy"

    # List current handoff queue status:
    python stage_handoff.py --status

Handoff queue structure:
    handoff_queue/pending/     — waiting to be processed
    handoff_queue/processing/  — currently being worked on
    handoff_queue/done/        — research + cover letter complete
    handoff_queue/failed/      — needs manual review
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUEUE = ROOT / "handoff_queue"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "job"


def handoff_filename(job: dict) -> str:
    company = slug(job.get("company", job.get("companyName", "unknown")))
    title = slug(job.get("title", "role"))
    return f"{company}_{title}.json"


def create_handoff(job: dict, screening: dict) -> dict:
    """Create a handoff record from a screened job."""
    return {
        "job": {
            "title": job.get("title", ""),
            "company": job.get("company", job.get("companyName", "")),
            "location": job.get("location", ""),
            "url": job.get("url", job.get("link", "")),
            "description": job.get("description", job.get("descriptionText", "")),
            "salary": job.get("salary", ""),
            "posted_date": job.get("posted_date", job.get("postedAt", "")),
            "source": job.get("source", ""),
        },
        "screening": {
            "composite_score": screening.get("composite_score", 0),
            "tier": screening.get("tier", ""),
            "breakdown": screening.get("breakdown", {}),
        },
        "status": "pending",
        "created": dt.date.today().isoformat(),
        "research_prompt": None,
        "research_brief": None,
        "cover_letter": None,
        "notes": "",
    }


def stage_jobs(screened_path: Path, tier_threshold: str | None, company_filter: str | None) -> int:
    """Stage jobs from screened results into the handoff queue."""
    records = json.loads(screened_path.read_text(encoding="utf-8"))
    pending_dir = QUEUE / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)

    tier_order = {"auto_apply": 0, "review": 1, "skip": 2}
    threshold_rank = tier_order.get(tier_threshold, 2) if tier_threshold else 2

    staged = 0
    for rec in records:
        # rec may be the full screening output or just the job
        if "screening" in rec:
            job = rec.get("job", rec)
            screening = rec["screening"]
        elif "composite_score" in rec:
            job = rec
            screening = rec
        else:
            job = rec
            screening = {"composite_score": 0, "tier": "unknown", "breakdown": {}}

        tier = screening.get("tier", "skip")
        company = job.get("company", job.get("companyName", ""))

        # Filter by tier
        if tier_threshold and tier_order.get(tier, 2) > threshold_rank:
            continue

        # Filter by company
        if company_filter and company_filter.lower() not in company.lower():
            continue

        filename = handoff_filename(job)
        filepath = pending_dir / filename

        if filepath.exists():
            print(f"  [skip] Already queued: {filename}")
            continue

        handoff = create_handoff(job, screening)
        filepath.write_text(json.dumps(handoff, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [staged] {filename} (score: {screening.get('composite_score', '?')}, tier: {tier})")
        staged += 1

    return staged


def show_status() -> None:
    """Print the current handoff queue status."""
    for status_dir in ["pending", "processing", "done", "failed"]:
        path = QUEUE / status_dir
        if path.exists():
            files = list(path.glob("*.json"))
            print(f"\n{status_dir.upper()} ({len(files)}):")
            for f in sorted(files):
                data = json.loads(f.read_text(encoding="utf-8"))
                job = data.get("job", {})
                score = data.get("screening", {}).get("composite_score", "?")
                print(f"  {job.get('title', '?')} @ {job.get('company', '?')} — score {score}")
        else:
            print(f"\n{status_dir.upper()} (0):")


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage screened jobs into the handoff queue.")
    ap.add_argument("--in", dest="src", help="Path to screened.json")
    ap.add_argument("--tier", choices=["auto_apply", "review", "skip"],
                    help="Stage all jobs at this tier or higher")
    ap.add_argument("--company", help="Stage jobs matching this company name")
    ap.add_argument("--status", action="store_true", help="Show current queue status")
    args = ap.parse_args()

    if args.status:
        show_status()
        return 0

    if not args.src:
        print("Error: provide --in (screened.json path) or --status")
        return 1

    src_path = Path(args.src)
    if not src_path.exists():
        print(f"Error: {src_path} not found")
        return 1

    print(f"Staging from: {src_path}")
    if args.tier:
        print(f"Tier threshold: {args.tier} (and higher)")
    if args.company:
        print(f"Company filter: {args.company}")

    staged = stage_jobs(src_path, args.tier, args.company)
    print(f"\n{staged} jobs staged to handoff_queue/pending/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
