# Job Application Pipeline

An AI-assisted pipeline I built to run my own internship search: it discovers postings, scores them against my profile, builds research prompts, and drafts tailored cover letters as formatted Word documents. I designed it with Claude Code and use it alongside Claude (Cowork) as the orchestrator.

## Why I built it
Searching and applying for legal, policy, and clean-energy internships by hand took hours each week, and most of that time went to repetitive steps: scanning job boards, judging fit, researching each organization, and formatting letters. I wanted a system that handles the repetitive parts and leaves the judgment calls to me.

## How it works

| Stage | What it does | Code |
|-------|--------------|------|
| Discover | Searches LinkedIn, Indeed, Idealist, and Climatebase (via Tavily, with web search as a fallback) and normalizes results | `scripts/normalize_discovery.py` |
| Screen | Scores each posting out of 40 (field fit, location, timing, compensation, growth) and sorts it into auto-apply, review, or skip tiers | `scripts/screen_jobs.py`, `config/scoring_weights.json` |
| Research | Builds a structured research prompt for each organization, run through Gemini Deep Research | `scripts/research_prompt.py` |
| Generate | Drafts a cover letter with Claude Sonnet, runs a mandatory "humanizer" pass to strip AI-sounding language, and outputs a formatted .docx | `scripts/generate_cover_letter.py` |
| Orchestrate | Stages screened jobs into a handoff queue (pending, processing, done) and schedules daily runs | `scripts/stage_handoff.py`, `scripts/setup_windows_scheduler.ps1`, `ORCHESTRATION.md` |
| Apply | Browser-automation handoff for application portals (in progress) | `scripts/apply.py` |

## Design decisions
- **Cover letters use Claude Sonnet instead of Gemini.** It was cheaper and faster for drafting, while Gemini handles research.
- **Research uses the free Gemini Deep Research web app, not the paid API.** The API bills $1-7 per task, so research stays a deliberate manual step that produces a `research_brief.md`.
- **Scoring is deterministic and free by default.** An optional `--llm` flag upgrades field-alignment scoring to Claude.
- **I removed the Apify LinkedIn scraper** once it switched to per-run pricing, and moved discovery to Tavily plus web search.
- **Handshake is intentionally excluded from automation** to respect its terms of service.

## Run it
```bash
pip install -r requirements.txt          # python-docx; add `anthropic` for generation
cp .env.example .env                     # add your own keys; .env is gitignored

python scripts/screen_jobs.py --in data/new_jobs.json --out data/screened.json --md data/screened.md
python scripts/research_prompt.py --from data/screened.json --company "Org Name" --website "https://example.org"
python scripts/generate_cover_letter.py --company "Org Name" --title "Policy Intern" \
    --research data/research_cache/org-name/research_brief.md --jd jd.txt
```

## Tests
```bash
python tests/test_screening.py   # 10/10 passing
```

## Notes
- Personal job data, generated letters, research briefs, and API keys are excluded from this repository.
- Contact details in templates are replaced with placeholders.
