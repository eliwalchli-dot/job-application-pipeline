# Daily Pipeline Orchestration — Cowork

This document defines the daily automated workflow that Cowork runs as a scheduled task.
It implements Section 10 of the architecture doc: discovery → screening → presentation.

## Scheduled Task Prompt

The scheduled task runs at **6:00 AM daily** and executes the following steps:

---

### Step 1: Tavily Discovery

Run 5 search queries from `config/discovery_queries.json`. For each query, call Tavily search
and collect all results into a single array.

**Queries:**
1. Clean energy internships (LinkedIn, Indeed, Climatebase, Idealist) — past day
2. Legal/policy internships (LinkedIn, Indeed, Idealist) — past day
3. Sustainability law internships (LinkedIn, Indeed, Idealist) — past day
4. Real estate legal internships (LinkedIn, Indeed) — past day
5. Broad clean energy/sustainability (USAJobs, Climatebase) — past week

Save all raw Tavily results to: `data/tavily_raw_YYYY-MM-DD.json`

### Step 2: (Removed) Apify LinkedIn scraper

**Apify was removed on 2026-08-17** — it changed pricing so every LinkedIn Jobs
Scraper run costs money. Do NOT use it. LinkedIn/Indeed/Idealist coverage is now
handled entirely by the Tavily + WebSearch discovery step in Step 1, which already
searches those domains at no cost. `fetch_apify.py` is disabled and
`data/apify_latest.json` is no longer produced or consumed.

### Step 3: Normalize & Deduplicate

Run the normalize script to normalize all sources and deduplicate against `data/seen_jobs.json`:

```bash
python scripts/normalize_discovery.py \
    --tavily data/tavily_raw_YYYY-MM-DD.json \
    --out data/new_jobs.json \
    --summary data/daily_summaries/YYYY-MM-DD_discovery.md
```

> Note: If Tavily is unavailable in a given session, use WebSearch as the fallback
> and write results in the same Tavily format to `data/websearch_raw_YYYY-MM-DD.json`,
> then pass that file to `--tavily`. Do not re-enable Apify.

### Step 4: Screen Jobs

Run the screening script on new discoveries:

```bash
python scripts/screen_jobs.py \
    --in data/new_jobs.json \
    --out data/screened.json \
    --md data/daily_summaries/YYYY-MM-DD_screened.md
```

### Step 5: Present Results to Eli

Generate and present a daily summary including:
- Number of new jobs found (by source)
- Auto-apply tier jobs (score ≥ 30): these need research + cover letter generation
- Review tier jobs (score 20-29): Eli decides
- Skip tier jobs (score < 20): logged only

For auto-apply jobs, stage them in the handoff queue for research + generation.

### Step 6: Stage Handoff

For each auto-apply job, create a handoff file at:
`handoff_queue/pending/{company-slug}_{title-slug}.json`

The handoff file contains all the job data plus the screening results, ready for
the research → generate → apply pipeline.

### Step 6.5: Cover Letter Generation (Cowork-native, no API key)

Once a job has been moved to `handoff_queue/processing/` and Eli has pasted the
Gemini Deep Research output into `data/research_cache/<slug>/research_brief.md`,
Cowork generates the cover letter body inline (Cowork IS Claude — no API key needed).

**Trigger:** Eli asks Cowork to run generation for a job, or Cowork notices a processing
job whose research brief is populated but `body_file` is missing.

**Steps Cowork runs:**

1. Run the generation prompt builder:
   ```bash
   python scripts/cowork_generate.py --job handoff_queue/processing/<slug>.json
   ```
   This writes `data/uploads/<slug>_generation_prompt.txt` and a stub `data/uploads/<slug>_body.txt`.

2. Read the generation prompt from `data/uploads/<slug>_generation_prompt.txt`.

3. Generate the cover letter body following the template rules (no em dashes, banned words,
   concrete references to the research brief, Eli's actual experience, 3-4 paragraphs).

4. Write ONLY the body paragraphs to `data/uploads/<slug>_body.txt` — no headers, no salutation,
   no sign-off.

5. Confirm the file is saved. Claude Code then runs:
   ```bash
   python scripts/generate_cover_letter.py \
       --company "<company>" --title "<title>" \
       --body-file "data/uploads/<slug>_body.txt"
   ```
   to format the body into a submission-ready .docx and update the handoff file.

**Check generation status at any time:**
```bash
python scripts/cowork_generate.py --status
```

---

## File Locations

| What | Path |
|------|------|
| Discovery query config | `config/discovery_queries.json` |
| Raw Tavily results | `data/tavily_raw_YYYY-MM-DD.json` |
| WebSearch fallback results | `data/websearch_raw_YYYY-MM-DD.json` (used when Tavily is down) |
| Dedup tracker | `data/seen_jobs.json` |
| Normalized new jobs | `data/new_jobs.json` |
| Screened results | `data/screened.json` |
| Daily discovery summary | `data/daily_summaries/YYYY-MM-DD_discovery.md` |
| Daily screening summary | `data/daily_summaries/YYYY-MM-DD_screened.md` |
| Handoff queue | `handoff_queue/pending/`, `handoff_queue/processing/`, `handoff_queue/done/` |
| Research briefs | `data/research_cache/<slug>/research_brief.md` |
| Generation prompt template | `templates/prompts/cover_letter_generation.txt` |
| Per-job generation prompt | `data/uploads/<slug>_generation_prompt.txt` |
| Per-job body text (Cowork fills) | `data/uploads/<slug>_body.txt` |
| Rendered .docx cover letters | `data/uploads/<slug>_cover_letter.docx` |

## Handoff Queue Protocol

Cowork stages jobs in `handoff_queue/pending/`. Claude Code (or Cowork itself for research)
processes them through the pipeline:

```
pending/   → job needs: research prompt built, Gemini Deep Research run, cover letter generated
processing/ → currently being worked on
done/      → research + cover letter complete, ready for application
failed/    → something went wrong; needs manual review
```

Each handoff file is a JSON object:
```json
{
  "job": { ... },
  "screening": { "score": 32, "tier": "auto_apply", "breakdown": { ... } },
  "status": "pending",
  "created": "2026-06-08",
  "research_brief": null,
  "cover_letter": null,
  "notes": ""
}
```

## Manual Intervention Points

1. **Gemini Deep Research** — still requires a human to paste the prompt and copy the output.
   The scheduled task generates the research prompt; Eli runs it in Gemini, pastes the result to
   `data/research_cache/<slug>/research_brief.md`.
2. **Cover letter generation** — Cowork generates the body inline (Step 6.5). No API key.
   Eli reviews the body text before the .docx is built; adjust if needed.
3. **Review-tier jobs** — Eli promotes or demotes these during the daily summary review.
4. **Application submission (LinkedIn Easy Apply)** — Auto Browser (Phase 4). Runs via:
   ```bash
   python scripts/apply.py --all   # auto-approves LinkedIn Easy Apply up to 5/day
   ```
5. **Application submission (portals)** — Greenhouse, Lever, Workday etc. require Eli's
   manual approval via the noVNC browser window before submitting.
6. **Handshake** — NEVER automated. UC Berkeley TOS prohibits it. Submit manually.
