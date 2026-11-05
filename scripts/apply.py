#!/usr/bin/env python3
"""
apply.py — Phase 4: Application Submission via Auto Browser.

Reads a handoff_queue/processing/*.json file, confirms a cover letter exists,
then drives Auto Browser to apply to the job:
  - LinkedIn Easy Apply: auto-approved (up to daily cap)
  - Company portals (Workday, Greenhouse, Lever): pause for manual approval

Prerequisites:
  1. Docker Desktop installed and running
  2. Auto Browser running: cd job-pipeline/auto-browser && docker compose up
  3. LinkedIn auth profile saved (run: python scripts/apply.py --save-linkedin-auth)
  4. ANTHROPIC_API_KEY set (for the agent step)

Usage:
    # Apply to a specific handoff file:
    python scripts/apply.py --job handoff_queue/processing/u-s-climate-alliance-secretariat_research-intern.json

    # Apply to all processing jobs (respects daily caps):
    python scripts/apply.py --all

    # Save LinkedIn auth profile (one-time setup):
    python scripts/apply.py --save-linkedin-auth

    # Check status / daily cap:
    python scripts/apply.py --status

Config:
    config/platform_configs/linkedin.json   — Easy Apply settings + daily cap
    config/platform_configs/portals.json    — Workday/Greenhouse/Lever settings
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

try:
    import urllib.request as req
    import urllib.error as uerr
except ImportError:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUEUE = ROOT / "handoff_queue"
CONFIG = ROOT / "config" / "platform_configs"
DATA = ROOT / "data"
UPLOADS = DATA / "uploads"
APPLY_LOG = DATA / "apply_log.json"

# Load pipeline_config.env if present (fallback for env vars not set in shell)
_cfg_file = ROOT.parent / "pipeline_config.env"
if _cfg_file.exists():
    for _line in _cfg_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            if _k.strip() not in os.environ:
                os.environ[_k.strip()] = _v.strip()

# Auto Browser base URL (docker-compose default)
AB_BASE = os.environ.get("AUTO_BROWSER_URL", "http://127.0.0.1:8000")
AB_TOKEN = os.environ.get("AUTO_BROWSER_TOKEN", "")

# Platform detection keywords (URL-based)
PLATFORM_HINTS = {
    "linkedin.com": "linkedin_easy_apply",
    "greenhouse.io": "greenhouse",
    "lever.co": "lever",
    "workday.com": "workday",
    "myworkdayjobs.com": "workday",
    "icims.com": "icims",
    "idealist.org": "idealist",
    "indeed.com": "indeed",
}


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #

def load_json(p: Path) -> dict | list:
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p: Path, data) -> None:
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _ab_post(path: str, body: dict) -> dict:
    url = f"{AB_BASE}{path}"
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if AB_TOKEN:
        headers["Authorization"] = f"Bearer {AB_TOKEN}"
    r = req.urlopen(req.Request(url, data=data, headers=headers), timeout=60)
    return json.loads(r.read().decode())


def _ab_get(path: str) -> dict:
    url = f"{AB_BASE}{path}"
    headers = {}
    if AB_TOKEN:
        headers["Authorization"] = f"Bearer {AB_TOKEN}"
    r = req.urlopen(req.Request(url, headers=headers), timeout=30)
    return json.loads(r.read().decode())


def check_auto_browser() -> bool:
    try:
        _ab_get("/healthz")
        return True
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# Daily cap tracking
# --------------------------------------------------------------------------- #

def load_apply_log() -> dict:
    if APPLY_LOG.exists():
        return load_json(APPLY_LOG)
    return {"applications": []}


def save_apply_log(log: dict) -> None:
    APPLY_LOG.parent.mkdir(exist_ok=True)
    save_json(APPLY_LOG, log)


def today_count(log: dict, platform: str) -> int:
    today = dt.date.today().isoformat()
    return sum(
        1 for a in log["applications"]
        if a.get("date") == today and a.get("platform") == platform
        and a.get("status") == "submitted"
    )


def log_application(log: dict, job: dict, platform: str, status: str, session_id: str = "") -> None:
    log["applications"].append({
        "date": dt.date.today().isoformat(),
        "company": job.get("company", ""),
        "title": job.get("title", ""),
        "platform": platform,
        "status": status,
        "session_id": session_id,
        "url": job.get("url", ""),
    })


# --------------------------------------------------------------------------- #
# Platform detection
# --------------------------------------------------------------------------- #

def detect_platform(url: str) -> str:
    for hint, platform in PLATFORM_HINTS.items():
        if hint in url.lower():
            return platform
    return "unknown"


def daily_cap(platform: str) -> int:
    caps = {
        "linkedin_easy_apply": 5,
        "greenhouse": 10,
        "lever": 10,
        "workday": 5,
        "idealist": 10,
        "indeed": 3,
        "unknown": 2,
    }
    return caps.get(platform, 2)


def needs_manual_approval(platform: str) -> bool:
    """True if this platform requires Eli to approve before submission."""
    # LinkedIn Easy Apply is auto-approved; everything else gets a manual gate.
    return platform != "linkedin_easy_apply"


# --------------------------------------------------------------------------- #
# Core application flow
# --------------------------------------------------------------------------- #

def apply_to_job(handoff_path: Path, dry_run: bool = False) -> str:
    """
    Drive Auto Browser to apply to one job.
    Returns: 'submitted', 'pending_approval', 'skipped', 'error'
    """
    handoff = load_json(handoff_path)
    job = handoff["job"]
    title = job.get("title", "")
    company = job.get("company", "")
    job_url = job.get("apply_url") or job.get("url", "")

    # 1. Require cover letter
    cl_path = handoff.get("cover_letter")
    if not cl_path:
        print(f"  [skip] No cover letter for {title} @ {company}. Generate it first.")
        return "skipped"
    cl_file = ROOT / cl_path
    if not cl_file.exists():
        print(f"  [skip] Cover letter file not found: {cl_file}")
        return "skipped"

    # 2. Detect platform + check daily cap
    platform = detect_platform(job_url)
    log = load_apply_log()
    cap = daily_cap(platform)
    count = today_count(log, platform)
    if count >= cap:
        print(f"  [cap] Daily limit reached for {platform} ({count}/{cap}). Skipping {company}.")
        return "skipped"

    print(f"\n  Applying: {title} @ {company}")
    print(f"  Platform: {platform} | cap {count+1}/{cap} | URL: {job_url[:70]}")

    if dry_run:
        print("  [dry-run] Would submit — skipping")
        return "skipped"

    # 3. Build agent goal
    resume_path = UPLOADS / "resume.pdf"
    goal = f"""Apply to this job on behalf of Eli Walchli.

Job: {title} at {company}
URL: {job_url}

Files to upload:
- Resume: {resume_path}
- Cover letter: {cl_file}

Applicant info (use for any form fields):
{json.dumps(load_json(ROOT / "config" / "eli_profile.json"), indent=2)}

Instructions:
1. Navigate to the job URL.
2. Click the apply/Easy Apply button.
3. Upload the resume and cover letter when prompted.
4. Fill required form fields using the applicant info above.
5. Do NOT submit. Stop at the final review/submit page and request human approval.
6. Take a screenshot of the final form before pausing.

If you encounter a CAPTCHA or login prompt, request human takeover immediately.
"""

    try:
        # 4. Create session
        auth_profile = "linkedin-default" if "linkedin" in platform else None
        session_body = {"name": f"{company[:20]}-{dt.date.today()}", "start_url": job_url}
        if auth_profile:
            session_body["auth_profile"] = auth_profile
        session = _ab_post("/sessions", session_body)
        session_id = session["id"]
        print(f"  Session: {session_id}")

        # 5. Run agent
        agent_resp = _ab_post(f"/sessions/{session_id}/agent/run", {
            "provider": "claude",
            "goal": goal,
            "max_steps": 20,
        })
        status = agent_resp.get("status", "unknown")
        print(f"  Agent status: {status}")

        # 6. Handle approval
        if needs_manual_approval(platform) or status == "approval_required":
            print(f"\n  APPROVAL REQUIRED for {company}")
            print(f"  Review at: {AB_BASE}/sessions/{session_id}")
            print(f"  noVNC:     http://127.0.0.1:6080")
            print(f"  To approve: POST {AB_BASE}/approvals/{{approval_id}}/approve")
            log_application(log, job, platform, "pending_approval", session_id)
            save_apply_log(log)
            _update_handoff(handoff_path, handoff, "pending_approval", session_id)
            return "pending_approval"

        # 7. Auto-approve for LinkedIn Easy Apply
        approval_id = agent_resp.get("approval_id")
        if approval_id:
            _ab_post(f"/approvals/{approval_id}/approve", {})
            _ab_post(f"/approvals/{approval_id}/execute", {})
            print(f"  Auto-approved and submitted.")

        # 8. Capture confirmation screenshot
        obs = _ab_get(f"/sessions/{session_id}/observe")
        screenshot_url = obs.get("screenshot_url", "")
        print(f"  Confirmation screenshot: {screenshot_url}")

        # 9. Update log + handoff
        log_application(log, job, platform, "submitted", session_id)
        save_apply_log(log)
        _update_handoff(handoff_path, handoff, "submitted", session_id)

        # 10. Move to done/
        done_dir = QUEUE / "done"
        done_dir.mkdir(exist_ok=True)
        dest = done_dir / handoff_path.name
        handoff_path.rename(dest)
        print(f"  Moved to done/: {dest.name}")
        return "submitted"

    except uerr.URLError as e:
        print(f"  [error] Auto Browser unreachable: {e}", file=sys.stderr)
        print(f"  Is it running? cd job-pipeline/auto-browser && docker compose up")
        return "error"
    except Exception as e:
        print(f"  [error] {e}", file=sys.stderr)
        log_application(load_apply_log(), job, platform, "error")
        save_apply_log(load_apply_log())
        return "error"


def _update_handoff(path: Path, handoff: dict, status: str, session_id: str) -> None:
    handoff["status"] = status
    handoff["apply_session_id"] = session_id
    handoff["applied_date"] = dt.date.today().isoformat()
    # Only update if still at original path (may have been moved)
    if path.exists():
        save_json(path, handoff)


# --------------------------------------------------------------------------- #
# Save LinkedIn auth profile
# --------------------------------------------------------------------------- #

def save_linkedin_auth() -> None:
    print("=== Save LinkedIn Auth Profile ===")
    print()
    print("1. Making sure Auto Browser is running at", AB_BASE)
    if not check_auto_browser():
        print("   ERROR: Auto Browser is not reachable. Start it first:")
        print("   cd job-pipeline/auto-browser && docker compose up")
        return

    session = _ab_post("/sessions", {
        "name": "linkedin-auth-setup",
        "start_url": "https://www.linkedin.com/login",
    })
    session_id = session["id"]
    print(f"2. Session created: {session_id}")
    print(f"3. Open noVNC: http://127.0.0.1:6080")
    print(f"   Log in to LinkedIn manually in the browser window.")
    input("\n   Press ENTER after you have logged in successfully... ")

    result = _ab_post(f"/sessions/{session_id}/save_storage_state", {
        "profile_name": "linkedin-default",
    })
    print(f"4. Auth profile saved: {result}")
    print()
    print("Done. Future sessions will reuse this profile without re-login.")


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #

def show_status() -> None:
    log = load_apply_log()
    today = dt.date.today().isoformat()
    print(f"=== Apply Log — {today} ===")

    today_apps = [a for a in log["applications"] if a.get("date") == today]
    if not today_apps:
        print("  No applications today.")
    else:
        for a in today_apps:
            print(f"  {a['status']:20} {a['title']} @ {a['company']} ({a['platform']})")

    print(f"\nDaily caps:")
    for platform, cap in [("linkedin_easy_apply", 5), ("greenhouse", 10), ("workday", 5)]:
        count = today_count(log, platform)
        print(f"  {platform:25} {count}/{cap}")

    ab_ok = check_auto_browser()
    print(f"\nAuto Browser: {'RUNNING at ' + AB_BASE if ab_ok else 'NOT RUNNING'}")
    if not ab_ok:
        print("  Start with: cd job-pipeline/auto-browser && docker compose up")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="Apply to jobs via Auto Browser.")
    ap.add_argument("--job", help="Path to a specific handoff_queue/processing/*.json file")
    ap.add_argument("--all", action="store_true", help="Apply to all processing jobs in order")
    ap.add_argument("--save-linkedin-auth", action="store_true", help="One-time LinkedIn auth profile setup")
    ap.add_argument("--status", action="store_true", help="Show today's application log and caps")
    ap.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = ap.parse_args()

    if args.status:
        show_status()
        return 0

    if args.save_linkedin_auth:
        save_linkedin_auth()
        return 0

    if args.job:
        path = Path(args.job)
        if not path.exists():
            path = ROOT / args.job
        result = apply_to_job(path, dry_run=args.dry_run)
        print(f"\nResult: {result}")
        return 0 if result in ("submitted", "pending_approval") else 1

    if args.all:
        processing_dir = QUEUE / "processing"
        jobs = sorted(processing_dir.glob("*.json"))
        if not jobs:
            print("No jobs in processing/ queue.")
            return 0
        print(f"Applying to {len(jobs)} jobs...")
        for job_path in jobs:
            result = apply_to_job(job_path, dry_run=args.dry_run)
            print(f"  {job_path.name}: {result}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
