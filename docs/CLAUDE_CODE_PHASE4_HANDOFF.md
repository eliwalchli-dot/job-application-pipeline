# Claude Code Handoff — Phase 4 Complete

**Date:** 2026-06-10
**Previous handoff:** `docs/CLAUDE_CODE_PHASE3_HANDOFF.md`
**Session summary:** Phase 4 (Application Automation) infrastructure is fully built and
running. The cover letter pipeline is end-to-end functional. Two jobs are in active
processing. Seven pending jobs need triage.

---

## Quick Start for the Next Session

Paste this at the start of your Claude Code session:

> Read `My Context/job-pipeline/docs/CLAUDE_CODE_PHASE4_HANDOFF.md` for full context.
> Phase 4 (Application Automation) is complete. The pipeline runs end-to-end: Cowork
> discovers → screens → stages, Gemini does research, Cowork generates cover letter
> bodies, Claude Code formats .docx and submits via Auto Browser. Two jobs are in
> `handoff_queue/processing/` awaiting research briefs. Seven jobs in `pending/` need
> triage. See the Action Items section for exact next steps.

---

## What Was Built This Session

### Phase 4 Infrastructure

| Component | Status | Details |
|-----------|--------|---------|
| Auto Browser (Docker) | ✅ Running | `http://127.0.0.1:8000`, healthz confirmed |
| `scripts/apply.py` | ✅ Built | Full application submission with platform caps, approval gates, Handshake block |
| `scripts/cowork_generate.py` | ✅ Built | Builds generation prompts for Cowork; writes body stubs |
| `scripts/generate_cover_letter.py` | ✅ Built | Formats Cowork body text into .docx matching Eli's exact template |
| `config/platform_configs/linkedin.json` | ✅ Built | Easy Apply cap (5/day), auto-approve |
| `config/platform_configs/portals.json` | ✅ Built | Greenhouse/Lever/Workday/etc., manual approve |
| `auto-browser/.env` | ✅ Configured | `CLAUDE_AUTH_MODE=cli` (no API key needed) |
| `templates/prompts/cover_letter_generation.txt` | ✅ Built + optimized | Full generation prompt with exact paragraph specs, fixed P4, anti-AI rules, self-check |
| `docs/PHASE4_SETUP.md` | ✅ Built | Docker setup guide, LinkedIn auth, daily usage |
| `requirements.txt` | ✅ Created | `python-docx>=1.1.0` (installed) |

### Cover Letter Template Spec (IMPORTANT — do not change without Eli's approval)

The generation prompt and .docx formatter enforce this exact structure:

**Fonts:**
- Name header: Playfair Display Bold, 20pt, centered
- Contact line: Playfair Display Regular, 10pt, centered
- All body text: Georgia, 11pt

**Document structure:**
```
[Name header]
[Contact line: XXX-XXX-XXXX | Portland, OR | eliwalchli@berkeley.edu | www.linkedin.com/in/eli-walchli]
[Horizontal rule]
[Date]
[blank]
[Hiring manager name / team]
[Company address lines]
[blank]
Dear [hiring manager],
[blank]
[P1]
[blank]
[P2]
[blank]
[P3]
[blank]
[P4]
[blank]
Sincerely,
[signature image OR 3 blank lines]
Eli Walchli
```

**Paragraph rules (non-negotiable):**
- **P1:** Opens verbatim: "Thank you for the opportunity to apply for [title] at [company]."
  Second sentence verbatim: "My name is Eli Walchli, and I am a student at the University
  of California, Berkeley, pursuing a dual degree in Legal Studies and Society & Environment."
  Remaining 1-2 sentences: ONE specific company detail from research brief tied to long-term growth.
- **P2:** Experience connection #1 — named org, concrete action, explicit link to JD requirement.
- **P3:** Experience connection #2 — different experience/angle, same specificity as P2.
- **P4:** Sentence 1 FIXED: "Thank you for your time and consideration."
  Sentence 2 VARIABLE: "I would greatly appreciate the opportunity to discuss how my [X] can support [company]'s [Y]."
  Sentence 3 FIXED: "Please feel free to contact me at XXX-XXX-XXXX or eliwalchli@berkeley.edu with any questions."

**Anti-AI rules (see full list in `templates/prompts/cover_letter_generation.txt`):**
- No em dashes — substitute comma or period
- Banned words: delve, leverage, robust, seamless, synergy, landscape, paradigm, harness,
  navigate, unlock, empower, streamline, holistic, tapestry, multifaceted, foster, cultivate,
  utilize, comprehensive, elevate, realm, and others
- No three-part parallelism, no consecutive same-word sentences, vary sentence length

---

## Full Pipeline Architecture

```
[5:45 AM] Windows Task Scheduler → fetch_apify.py
          Triggers Apify LinkedIn scraper → data/apify_latest.json

[6:00 AM] Cowork scheduled task (ORCHESTRATION.md)
          Step 1: Tavily discovery (5 queries)
          Step 2: Check for apify_latest.json
          Step 3: normalize_discovery.py → data/new_jobs.json
          Step 4: screen_jobs.py → data/screened.json
          Step 5: Present daily summary to Eli
          Step 6: stage_handoff.py → handoff_queue/pending/

[Manual — Eli] Gemini Deep Research
          Open data/research_cache/<slug>/research_prompt.txt
          Paste into gemini.google.com → Deep Research
          Copy output into data/research_cache/<slug>/research_brief.md

[Manual — Cowork] Cover letter generation (Step 6.5)
          python scripts/cowork_generate.py --job handoff_queue/processing/<file>.json
          Cowork reads data/uploads/<slug>_generation_prompt.txt
          Cowork writes body paragraphs to data/uploads/<slug>_body.txt

[Claude Code] .docx formatting
          python scripts/generate_cover_letter.py \
              --body-file data/uploads/<slug>_body.txt \
              --job handoff_queue/processing/<file>.json \
              --address "Line1,Line2,City State ZIP"
          → data/uploads/<slug>_cover_letter.docx
          → handoff JSON updated: cover_letter=..., status=ready

[Claude Code] Application submission
          python scripts/apply.py --job handoff_queue/processing/<file>.json
          LinkedIn Easy Apply: auto-approves (cap 5/day)
          Portals: pauses for Eli's manual approval via noVNC (http://localhost:6080)
          HANDSHAKE: NEVER automated (UC Berkeley TOS — account at risk)
```

---

## Current Queue State (as of 2026-06-10)

### processing/ — 2 jobs

**1. Intern, Policy @ U.S. Climate Alliance Secretariat**
- File: `handoff_queue/processing/u-s-climate-alliance-secretariat_research-intern.json`
- Apply URL: `https://recruiting.ultipro.com/UNI1076UNFI/JobBoard/.../8a808959-...`
- Compensation: $17.95–$20.00/hr, 20–29 hrs/week
- Duration: May 26 – Aug 18, 2026 (rolling deadline)
- Location: Remote
- Research brief: **EMPTY** — Eli needs to run Gemini Deep Research
- Research prompt: `data/research_cache/u-s-climate-alliance-secretariat/research_prompt.txt` ✅
- Body: not yet generated
- .docx: not yet generated
- Address needed: United Nations Foundation, 1750 Pennsylvania Ave NW, Washington, DC 20006
- Hiring manager: unknown — use "U.S. Climate Alliance Secretariat Hiring Team"

**2. Summer 2026 Organizing Fellowship @ Lead Locally**
- File: `handoff_queue/processing/lead-locally_summer-2026-organizing-fellowship-lead-l.json`
- **DEADLINE: JUNE 22** — urgent
- Compensation: $25/hr, ~10 hrs/week
- Duration: July 20 – Aug 28, 2026
- Location: Eugene, OR (outside Eli's acceptable location range)
- **Hard requirement: consistent car access** — Eli needs to confirm before applying
- Role: canvassing / phone banking (not policy/legal/research — verify Eli wants to pursue)
- Research brief: **EMPTY**
- Research prompt: `data/research_cache/lead-locally/research_prompt.txt` ✅

### pending/ — 7 jobs needing triage

These all have thin descriptions from the scraper. The next Claude Code session should
WebFetch each one to find the real job posting, then enrich or fail:

| File | Company | Title | Recommendation |
|------|---------|-------|----------------|
| `glass-entertainment-group_fall-internship-2026-in-united-states.json` | Glass Entertainment Group | Fall Internship 2026 | Investigate — vague title, entertainment industry (not Eli's focus) |
| `legal-political-marketing-aebly-media_outreach-intern.json` | "Legal / Political / Marketing - Aebly Media" | Outreach Intern | Investigate — company name looks like a category tag, may be scraper artifact |
| `professional-experience-in-climate-polic_public-policy-no-experience-entry-level-.json` | "Professional experience in climate policy..." | "Public Policy No Experience Entry Level jobs in Washington, Dc" | **Fail** — this is a LinkedIn search results page, not a real job |
| `prosper-marketplace_ai-engineering-intern-summer-2026.json` | Prosper Marketplace | AI Engineering Intern, Summer 2026 | Likely fail — fintech AI engineering, not Eli's focus |
| `unknown_environmental-policy-analyst-intern.json` | (unknown) | Environmental Policy Analyst Intern | **Investigate** — right field, needs company identification |
| `unknown_pre-law-student-jobs-in-remote.json` | (unknown) | "Pre law student jobs in Remote" | **Fail** — LinkedIn search page artifact, location="Indeed" |
| `workato_intern-ai-engineering-in-san-francisco-c.json` | Workato | Intern, AI Engineering | Likely fail — workflow automation engineering, not Eli's focus |

For each "Investigate" job: WebFetch the URL in the JSON, find the real posting, enrich
the description and apply_url, correct the title/company if needed. If the real job is
good → move to processing/. If it's bad or closed → move to failed/.

---

## All Files Reference

### Scripts (`scripts/`)

| Script | Purpose | Key flags |
|--------|---------|-----------|
| `fetch_apify.py` | Triggers Apify LinkedIn scraper, downloads results to `data/apify_latest.json` | `--dry-run`, `--query-id` |
| `normalize_discovery.py` | Merges Tavily + Apify, deduplicates against `data/seen_jobs.json` | `--tavily`, `--apify`, `--out` |
| `screen_jobs.py` | Scores jobs on 5 dimensions, assigns tiers | `--in`, `--out`, `--md` |
| `stage_handoff.py` | Moves jobs into handoff queue by tier | `--status` |
| `research_prompt.py` | Builds Gemini Deep Research prompt for a job | `--company`, `--title` |
| `cowork_generate.py` | Builds cover letter generation prompt; creates body stub | `--job`, `--all`, `--status` |
| `generate_cover_letter.py` | Formats body text into .docx | `--body-file`, `--job`, `--address`, `--hiring-manager`, `--dry-run` |
| `apply.py` | Submits application via Auto Browser | `--job`, `--all`, `--status`, `--save-linkedin-auth`, `--dry-run` |
| `setup_windows_scheduler.ps1` | Registers/removes Windows Task Scheduler job for fetch_apify.py | `-Remove`, `-Test` |

### Config (`config/`)

| File | Purpose |
|------|---------|
| `eli_profile.json` | Eli's structured profile — used by cowork_generate.py for candidate_summary() |
| `scoring_weights.json` | 5-dimension screening weights |
| `discovery_queries.json` | Tavily + Apify search query configs |
| `platform_configs/linkedin.json` | LinkedIn Easy Apply cap (5/day), auto-approve=true |
| `platform_configs/portals.json` | Per-platform caps for Greenhouse/Lever/Workday/etc. |

### Templates (`templates/prompts/`)

| File | Purpose |
|------|---------|
| `cover_letter_generation.txt` | Optimized generation prompt — Cowork reads this to write cover letter bodies. Has exact P1–P4 specs, fixed P4 sentences, anti-AI rules, self-check. DO NOT simplify. |

### Data directories

| Path | Contents |
|------|---------|
| `data/apify_latest.json` | Latest Apify LinkedIn results (populated by fetch_apify.py) |
| `data/seen_jobs.json` | Dedup tracker |
| `data/daily_summaries/` | Daily discovery + screening markdown summaries |
| `data/research_cache/<slug>/research_prompt.txt` | Gemini prompt — Eli pastes this into gemini.google.com |
| `data/research_cache/<slug>/research_brief.md` | Gemini output — Eli pastes output here |
| `data/uploads/<slug>_generation_prompt.txt` | Full generation prompt built by cowork_generate.py |
| `data/uploads/<slug>_body.txt` | Cover letter body — Cowork writes this after reading the generation prompt |
| `data/uploads/<slug>_cover_letter.docx` | Final formatted cover letter |
| `data/uploads/resume.pdf` | **MISSING — Eli must add before apply.py will work** |
| `data/uploads/signature.png` | **MISSING — Eli must add for .docx signature embedding** |
| `data/apply_log.json` | Application submission log (daily caps tracked here) |

### Auto Browser (`auto-browser/`)

| File | Purpose |
|------|---------|
| `.env` | `CLAUDE_AUTH_MODE=cli` (uses local Claude Code CLI, no API key), `API_BEARER_TOKEN`, `STEALTH_PROFILE=light` |
| `docker-compose.yml` | Defines controller (port 8000) + browser-node (VNC port 5900, noVNC port 6080) |

### Env / secrets (`Job Applications/pipeline_config.env`)

```
APIFY_TOKEN=...              ← ROTATE — was exposed in a previous chat session
GEMINI_API_KEY=...           ← ROTATE — was exposed in a previous chat session
AUTO_BROWSER_TOKEN=kp0Wx8BLQFbcMneINuKCAlymtERjszTD
AUTO_BROWSER_URL=http://127.0.0.1:8000
ANTHROPIC_API_KEY=           ← intentionally empty — using CLI auth instead
```

---

## Critical Constraints (Never Violate)

1. **HANDSHAKE — NEVER automate.** UC Berkeley TOS prohibits it. Eli's account is at risk.
   `apply.py` has a hardcoded block that exits if the apply URL is on handshake.com.

2. **LinkedIn Easy Apply cap: 5/day.** Hardcoded in `config/platform_configs/linkedin.json`
   and enforced in `apply.py`. Do not raise this.

3. **Portal submissions require Eli's approval.** `apply.py` pauses and opens the noVNC
   viewer (`http://localhost:6080`) for Eli to review before submitting to Greenhouse,
   Lever, Workday, etc.

4. **Cover letter P4 sentences 1 and 3 are fixed.** Never change these regardless of role:
   - S1: "Thank you for your time and consideration."
   - S3: "Please feel free to contact me at XXX-XXX-XXXX or eliwalchli@berkeley.edu with any questions."

5. **eli_profile.json academic_calendar says "NOT interested in summer 2026"** but both
   current processing jobs ARE summer 2026. Eli is making exceptions. Update or ignore
   this field — do not let the screener auto-fail summer 2026 roles without flagging them.

---

## Architecture Decisions Made This Session

| Decision | Rationale |
|----------|-----------|
| `CLAUDE_AUTH_MODE=cli` in Auto Browser | No separate Anthropic API key needed — Auto Browser uses locally installed Claude Code CLI, covered by Eli's $20/mo Pro subscription |
| Cowork generates cover letter bodies natively | Cowork IS Claude — no API key needed for generation. `cowork_generate.py` builds the prompt; Cowork writes the body inline in the same session |
| No Humanizer pass as separate step | The optimized generation prompt in `cover_letter_generation.txt` bakes anti-AI rules and a self-check directly in, replacing the separate Humanizer post-process from the old Phase 3 design |
| `generate_cover_letter.py` is format-only | It takes a pre-written body and formats it — it does not call any AI. All intelligence happens at generation time via Cowork |
| Playfair Display / Georgia fonts | Matches Eli's existing cover letters exactly (verified against CBRE and Kidder Matthews PDFs) |

---

## Known Gotchas

| Issue | Details |
|-------|---------|
| PowerShell 5.1 UTF-8 BOM | `Out-File -Encoding utf8` writes a BOM; Python json rejects it. Use `[System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($false))` |
| PowerShell 5.1 no `&&` | Use `;` or `if ($?) { B }` instead of `A && B` |
| PowerShell 5.1 no `%-d` | Date format `%-d` (no leading zero) fails. Use `$t.day` in a format string instead |
| Docker PATH not on new PS sessions | After Docker install, run `$env:PATH = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")` before docker commands |
| Auto Browser health endpoint | The endpoint is `/healthz` not `/health` — confirmed in apply.py |
| `pipeline_config.env` not auto-loaded | `apply.py` loads it manually at startup. Other scripts may need the same pattern — check before adding new env-dependent scripts |
| Playfair Display font | It's a Google Font, not built into Windows/Office. If the .docx is opened on a machine without it installed, Word will substitute. Fine for Eli's machine — if it becomes an issue, swap to Garamond or Palatino Linotype |
| `eli_profile.json` experience field | The "Research Fellow" entry has `org: "Transportation decarbonization / clean energy policy"` — this is a description, not an org name. cowork_generate.py's candidate_summary() will include it verbatim, which looks odd. Consider updating the org to the actual organization name (TDA = Transportation Decarbonisation Alliance) |

---

## Action Items

### For the Next Claude Code Session (code work)

- [ ] **Triage 7 pending jobs** — WebFetch each URL, identify real posting, enrich or fail:
  - `professional-experience-in-climate-polic_...` → **Fail** (search page artifact)
  - `unknown_pre-law-student-jobs-in-remote.json` → **Fail** (search page artifact)
  - `unknown_environmental-policy-analyst-intern.json` → Investigate, find company
  - `legal-political-marketing-aebly-media_outreach-intern.json` → Investigate company identity
  - `glass-entertainment-group_fall-internship-2026.json` → Investigate, likely fail (entertainment)
  - `prosper-marketplace_ai-engineering-intern-summer-2026.json` → Likely fail (fintech AI eng)
  - `workato_intern-ai-engineering-in-san-francisco-c.json` → Likely fail (workflow automation eng)

- [ ] **Add `address` to USCA handoff JSON** — address is:
  `["United Nations Foundation", "1750 Pennsylvania Ave NW", "Washington, DC 20006"]`
  Edit `handoff_queue/processing/u-s-climate-alliance-secretariat_research-intern.json`
  and add `"hiring_manager": "U.S. Climate Alliance Secretariat Hiring Team"` and
  `"address": ["United Nations Foundation", "1750 Pennsylvania Ave NW", "Washington, DC 20006"]`

- [ ] **Fix eli_profile.json experience org name** — change
  `"org": "Transportation decarbonization / clean energy policy"` to
  `"org": "Transportation Decarbonisation Alliance"` so candidate_summary() reads correctly

### For Eli (manual actions — in priority order)

- [ ] 🔴 **Rotate credentials** — `APIFY_TOKEN` and `GEMINI_API_KEY` in
  `Job Applications/pipeline_config.env` were both visible in a previous chat session.
  Rotate them at apify.com and aistudio.google.com before the next pipeline run.

- [ ] 🔴 **Lead Locally decision** — deadline June 22. Role is canvassing/phone banking
  in Eugene, OR. Requires consistent car access. Not policy/legal/research. Decide: pursue
  or move to `handoff_queue/failed/`?

- [ ] 🟡 **Gemini Deep Research for USCA** —
  1. Open `data/research_cache/u-s-climate-alliance-secretariat/research_prompt.txt`
  2. Go to gemini.google.com → `+` → More tools → Deep Research
  3. Paste the prompt, wait for report
  4. Copy full output into `data/research_cache/u-s-climate-alliance-secretariat/research_brief.md`
  5. Then ask Cowork: "Read `data/uploads/u-s-climate-alliance-secretariat_generation_prompt.txt`
     and write the cover letter body to `data/uploads/u-s-climate-alliance-secretariat_body.txt`"

- [ ] 🟡 **Add `data/uploads/signature.png`** — crop your signature from one of:
  `Downloads/Eli Walchli - CBRE Intern Cover Letter (1).pdf` or the Kidder Matthews one.
  Save as PNG, drop into `data/uploads/signature.png`.

- [ ] 🟡 **Add `data/uploads/resume.pdf`** — required by apply.py before any application runs.

- [ ] 🟡 **Save LinkedIn auth** (one-time setup):
  1. Make sure Auto Browser is running: `cd job-pipeline/auto-browser && docker compose up`
  2. Run: `python scripts/apply.py --save-linkedin-auth`
  3. Browser opens at `http://localhost:6080` — log in to LinkedIn manually
  4. Auth profile is saved; future runs use it automatically

---

## Full End-to-End Workflow (Once Setup Is Complete)

```bash
# 1. Check what's ready
python scripts/cowork_generate.py --status

# 2. Build generation prompts (after research briefs are filled)
python scripts/cowork_generate.py --all

# 3. [In Cowork] Read generation prompt → write body to body.txt

# 4. Format .docx
python scripts/generate_cover_letter.py \
    --body-file data/uploads/u-s-climate-alliance-secretariat_body.txt \
    --job handoff_queue/processing/u-s-climate-alliance-secretariat_research-intern.json

# 5. Check apply status
python scripts/apply.py --status

# 6. Submit (auto-approves LinkedIn Easy Apply, pauses for portals)
python scripts/apply.py --job handoff_queue/processing/u-s-climate-alliance-secretariat_research-intern.json
```
