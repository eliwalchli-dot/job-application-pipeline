#!/usr/bin/env python3
"""
fetch_apify.py — DISABLED 2026-08-17.

Apify changed its pricing so every LinkedIn Jobs Scraper run now costs money.
Per Eli's instruction, Apify has been removed from the pipeline. This script no
longer calls the Apify API. LinkedIn/Indeed/Idealist coverage is now handled by
the Tavily + WebSearch discovery step (see ORCHESTRATION.md), which already
searches those domains at no cost.

The original implementation is preserved at:
    scripts/fetch_apify.py.disabled-2026-08-17

If you ever move to a different (free) LinkedIn source, replace this stub.
This stub intentionally exits without doing anything so no scheduled run,
cron job, or manual invocation can incur Apify charges.
"""
from __future__ import annotations

import sys

MESSAGE = (
    "fetch_apify.py is DISABLED (Apify removed 2026-08-17 — it now costs money).\n"
    "No Apify API call was made. Discovery now relies on Tavily + WebSearch.\n"
    "Original preserved at scripts/fetch_apify.py.disabled-2026-08-17."
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
