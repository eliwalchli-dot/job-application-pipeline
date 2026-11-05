#!/usr/bin/env python3
"""Tests for screen_jobs scoring. Run: python tests/test_screening.py  (or pytest)."""
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import screen_jobs as s  # noqa: E402

PROFILE = s.load_profile()
W = s.load_weights()
TODAY = dt.date(2026, 6, 8)


def _score(raw):
    return s.score_job(s.normalize_job(raw), PROFILE, W, TODAY, use_llm=False)


def test_word_boundary_no_false_hr():
    # "hours" must NOT trigger the "HR" negative keyword.
    r = _score({"title": "Policy Intern", "companyName": "Evolve CA",
                "location": "Remote", "descriptionText": "40 hours per week researching policy."})
    assert "HR" not in r["breakdown"]["field_alignment"]["note"], r["breakdown"]["field_alignment"]


def test_strong_legal_clean_energy_match_is_high():
    r = _score({"title": "Clean Energy Policy & Legal Intern", "companyName": "CLEE",
                "location": "Berkeley, CA",
                "descriptionText": "Sustainability law, climate policy, energy regulation, advocacy. Paid.",
                "deadline": "2026-06-20"})
    assert r["composite_score"] >= 30, r
    assert r["tier"] == "auto_apply", r


def test_irrelevant_role_low():
    r = _score({"title": "Sales Development Representative", "companyName": "Acme",
                "location": "Austin, TX", "descriptionText": "Hit sales quota, cold calls. Unpaid."})
    assert r["composite_score"] < 20, r
    assert r["tier"] == "skip", r


def test_remote_scores_high_on_location():
    r = _score({"title": "Legal Intern", "companyName": "X", "location": "Remote",
                "descriptionText": "legal research"})
    assert r["breakdown"]["location_fit"]["score"] >= 9, r


def test_expired_deadline_zero_timing():
    r = _score({"title": "Energy Intern", "companyName": "X", "location": "Berkeley, CA",
                "descriptionText": "energy", "deadline": "2026-01-01"})
    assert r["breakdown"]["timing"]["score"] == 0, r


def test_dedup_key_stable():
    a = s.normalize_job({"title": "Intern", "companyName": "SB Energy", "location": "SF, CA"})
    b = s.normalize_job({"jobTitle": "intern ", "company": " SB ENERGY", "location": "sf, ca"})
    assert s.dedup_key(a) == s.dedup_key(b)


def test_bay_area_location_tier():
    """Greater Bay Area cities should score bay_area_points (7), not preferred (10)."""
    for city in ["Emeryville, CA", "Walnut Creek, CA", "Fremont, CA", "Palo Alto, CA"]:
        r = _score({"title": "Legal Intern", "companyName": "X", "location": city,
                     "descriptionText": "legal research"})
        score = r["breakdown"]["location_fit"]["score"]
        note = r["breakdown"]["location_fit"]["note"]
        assert score == 7, f"{city}: expected 7 got {score} ({note})"
        assert "bay area" in note.lower(), f"{city}: note should mention Bay Area, got: {note}"


def test_generic_bay_area_label():
    """'East Bay' / 'Peninsula' / 'Bay Area' should also get bay_area_points."""
    for loc in ["East Bay, CA", "South Bay, CA", "Bay Area"]:
        r = _score({"title": "Policy Intern", "companyName": "X", "location": loc,
                     "descriptionText": "policy"})
        score = r["breakdown"]["location_fit"]["score"]
        assert score == 7, f"{loc}: expected 7 got {score}"


def test_california_outside_bay_area():
    """CA cities outside the Bay Area should score ca_other_points (3)."""
    r = _score({"title": "Legal Intern", "companyName": "X", "location": "Sacramento, CA",
                 "descriptionText": "legal"})
    score = r["breakdown"]["location_fit"]["score"]
    assert score == 3, f"Sacramento: expected 3 got {score}"


def test_portland_scores_low():
    """Portland should score as US non-preferred (2), not preferred."""
    r = _score({"title": "Legal Intern", "companyName": "X", "location": "Portland, OR",
                 "descriptionText": "legal"})
    score = r["breakdown"]["location_fit"]["score"]
    assert score == 2, f"Portland: expected 2 got {score}"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    return 0 if passed == len(fns) else 1


if __name__ == "__main__":
    raise SystemExit(_run())
