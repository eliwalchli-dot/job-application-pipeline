# Claude Code Handoff — Phase 3 Complete, Here's What You Need

**Date:** 2026-06-08
**Context:** Cowork just finished Phase 3 (Orchestration & Scheduling). This document briefs the Claude Code session on what changed, what it needs to do, and how the two environments now interact.

---

## What Cowork Built (Phase 3)

Cowork now runs a **daily scheduled task at 6:00 AM** that:

1. Runs 5 Tavily searches across LinkedIn, Indeed, Idealist, Climatebase, USAJobs
2. Checks for `data/apify_latest.json` (Apify LinkedIn results — **your job to populate**)
3. Normalizes + deduplicates all results via `scripts/normalize_discovery.py`
4. Screens them via `scripts/screen_jobs.py` (the script you built in Phase 2)
5. Stages review-tier+ jobs into `handoff_queue/pending/`
6. Presents Eli with a daily summary

### New files you should know about

| File | What it does |
|------|-------------|
| `scripts/normalize_discovery.py` | Merges Tavily + Apify raw results, normalizes to standard job format, deduplicates against `data/seen_jobs.json` |
| `scripts/stage_handoff.py` | Moves screened jobs into the handoff queue by tier. Run `--status` to see queue state. |
| `config/discovery_queries.json` | Search query configs for both Tavily (Cowork) and Apify LinkedIn (Claude Code) |
| `data/seen_jobs.json` | Dedup tracker — hash of (company\|title\|location) → first-seen date |
| `ORCHESTRATION.md` | Full workflow doc for the daily pipeline |
| `handoff_queue/` | pending/ → processing/ → done/ → failed/ |

---

## Task 1: Set Up Apify LinkedIn Scheduled Runs

The Apify MCP connector is already configured (see `docs/APIFY_MCP_SETUP.md`). You need to:

### Option A: Apify Platform Scheduling (Recommended)

Set up the Apify Actor `curious_coder/linkedin-jobs-scraper` to run daily on a schedule via the Apify platform. Configure 3 runs with these search parameters (from `config/discovery_queries.json`):

```json
[
  {
    "keywords": "clean energy intern",
    "location": "Berkeley, California",
    "experience_level": "1",
    "date_posted": "past24hours"
  },
  {
    "keywords": "legal policy intern",
    "location": "San Francisco Bay Area",
    "experience_level": "1",
    "date_posted": "past24hours"
  },
  {
    "keywords": "sustainability intern",
    "location": "Berkeley, California",
    "experience_level": "1",
    "date_posted": "past24hours"
  }
]
```

After each run completes, the results should be saved to:
```
job-pipeline/data/apify_latest.json
```

Cowork's daily task checks for this file and includes it in the merge step if it exists and was modified today.

### Option B: Manual Trigger

If Apify platform scheduling is too complex, just run the scraper manually when Eli asks. The MCP connector supports triggering Actor runs directly. Save output to `data/apify_latest.json`.

---

## Task 2: Understand the Handoff Queue Protocol

The handoff queue is the bridge between Cowork (discovery/screening) and Claude Code (research/generation/application).

### Queue structure

```
handoff_queue/
  pending/      ← Cowork puts screened jobs here
  processing/   ← Move a job here when you start working on it
  done/         ← Move here when research + cover letter are complete
  failed/       ← Move here if something went wrong
```

### Each handoff file looks like this

```json
{
  "job": {
    "title": "Research Intern",
    "company": "U.S. Climate Alliance Secretariat",
    "location": "Remote",
    "url": "https://...",
    "description": "The U.S. Climate Alliance Secretariat is seeking...",
    "salary": "",
    "posted_date": "2026-06-04",
    "source": "tavily"
  },
  "screening": {
    "composite_score": 29.0,
    "tier": "review",
    "breakdown": { ... }
  },
  "status": "pending",
  "created": "2026-06-08",
  "research_prompt": null,
  "research_brief": null,
  "cover_letter": null,
  "notes": ""
}
```

### Processing a pending job

When Eli says "process the pending jobs" or "generate cover letters for the top jobs":

1. **Move** the file from `pending/` to `processing/`
2. **Build the research prompt:**
   ```bash
   python scripts/research_prompt.py --company "U.S. Climate Alliance Secretariat" \
       --title "Research Intern" --location "Remote" \
       --website "(find the company website)"
   ```
   This creates `data/research_cache/<company-slug>/research_prompt.txt`

3. **Tell Eli to run Gemini Deep Research** — this is a manual step. Eli opens gemini.google.com, activates Deep Research (+ → More tools → Deep research), pastes the prompt, waits for the report, and copies it into `data/research_cache/<company-slug>/research_brief.md`. See `docs/GEMINI_DEEP_RESEARCH.md` for the full flow.

4. **Generate the cover letter** (once the research brief exists):
   ```bash
   python scripts/generate_cover_letter.py \
       --company "U.S. Climate Alliance Secretariat" \
       --title "Research Intern" \
       --research data/research_cache/u-s-climate-alliance-secretariat/research_brief.md \
       --jd <path-to-job-description.txt> \
       --recipient-org "U.S. Climate Alliance Secretariat"
   ```
   This runs Claude Sonnet generation + mandatory Humanizer pass + .docx formatting.

5. **Update the handoff file** with paths to the research brief and cover letter
6. **Move** to `done/`

### Check queue status anytime

```bash
python scripts/stage_handoff.py --status
```

---

## Task 3: Phase 4 Prep (Application Automation)

This is the next major build. Per the architecture doc Section 7 and Phase 4:

1. **Auto Browser Docker setup** — Clone https://github.com/LvcidPsyche/auto-browser, run `docker compose up`
2. **Save LinkedIn auth profile** via Auto Browser's noVNC interface (manual one-time login)
3. **Build LinkedIn Easy Apply agent script** — uses Auto Browser's agent API to navigate job pages, upload resume + cover letter, fill form fields, pause before submission for approval
4. **Build company portal agent scripts** (Workday, Greenhouse, Lever) — highly variable, start simple
5. **Configure approval gates** — auto-approve for Easy Apply, manual approve for complex portals
6. **Add per-platform daily caps** — max 5 LinkedIn Easy Apply/day (hardcoded in config)

**Do NOT automate Handshake.** The TOS explicitly prohibits it, and Eli's UC Berkeley account is at risk.

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `Job_Application_Pipeline_Architecture.md` | Master architecture doc (v2, updated) |
| `job-pipeline/ORCHESTRATION.md` | Daily workflow and handoff protocol |
| `job-pipeline/config/eli_profile.json` | Eli's structured applicant profile |
| `job-pipeline/config/scoring_weights.json` | 5-dimension screening weights |
| `job-pipeline/config/discovery_queries.json` | Tavily + Apify search configs |
| `job-pipeline/scripts/screen_jobs.py` | Screening (you built this) |
| `job-pipeline/scripts/research_prompt.py` | Research prompt builder (you built this) |
| `job-pipeline/scripts/generate_cover_letter.py` | CL generation (you built this) |
| `job-pipeline/scripts/normalize_discovery.py` | Tavily/Apify merge + dedup (Cowork built this) |
| `job-pipeline/scripts/stage_handoff.py` | Handoff queue management (Cowork built this) |
| `Job Applications/pipeline_config.env` | API keys — **need rotation** |
| `job-pipeline/docs/APIFY_MCP_SETUP.md` | Apify MCP connector config |
| `job-pipeline/docs/GEMINI_DEEP_RESEARCH.md` | How to run Deep Research manually |

---

## Quick Start for Claude Code Session

Paste this at the start of your Claude Code session:

> Read `My Context/job-pipeline/docs/CLAUDE_CODE_PHASE3_HANDOFF.md` for full context. Phase 3 (Orchestration) is complete — Cowork runs daily discovery + screening + handoff staging. Your tasks: (1) set up Apify LinkedIn scheduled runs so `data/apify_latest.json` gets populated daily, (2) understand the `handoff_queue/` protocol for processing jobs through research → cover letter generation, (3) when ready, begin Phase 4 (Application Automation with Auto Browser).
