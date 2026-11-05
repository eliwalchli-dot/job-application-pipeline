#!/usr/bin/env python3
"""
generate_cover_letter.py — Format a Cowork-generated body into a submission-ready .docx.

Reads body paragraphs from a text file (written by Cowork), applies Eli's exact cover
letter template, and outputs a properly formatted .docx.

Document structure (matches Eli's existing cover letters exactly):
  [Header]   Eli Walchli — bold, centered, 20pt, Times New Roman
  [Contact]  XXX-XXX-XXXX | Portland, OR | eliwalchli@berkeley.edu | ...
  [Rule]     horizontal line
  [Date]
  [Blank line]
  [Recipient name / team]
  [Address lines]
  [Blank line]
  [Salutation]  Dear ...,
  [Blank line]
  [P1 — P4, each separated by a blank line]
  [Blank line]
  Sincerely,
  [Signature image, or blank space if none found]
  Eli Walchli

Usage:
    # Recommended — job file supplies company, title, address, hiring manager:
    python scripts/generate_cover_letter.py \\
        --body-file data/uploads/u-s-climate-alliance-secretariat_body.txt \\
        --job handoff_queue/processing/u-s-climate-alliance-secretariat_research-intern.json

    # With explicit address and hiring manager:
    python scripts/generate_cover_letter.py \\
        --body-file data/uploads/usca_body.txt \\
        --company "U.S. Climate Alliance Secretariat" \\
        --title "Intern, Policy" \\
        --hiring-manager "Policy Internship Hiring Team" \\
        --address "United Nations Foundation,1750 Pennsylvania Ave NW,Washington, DC 20006"

    # Dry run — preview text only, no file written:
    python scripts/generate_cover_letter.py \\
        --body-file data/uploads/usca_body.txt --job ... --dry-run

Prerequisites:
    pip install python-docx

Adding address / hiring manager to a handoff file:
    Edit the handoff JSON and add these top-level fields:
        "hiring_manager": "Jane Smith",
        "address": ["United Nations Foundation", "1750 Pennsylvania Ave NW", "Washington, DC 20006"]
    This avoids passing --address and --hiring-manager every time.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

try:
    from docx import Document
    from docx.shared import Pt, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
except ImportError:
    print("ERROR: python-docx is required.")
    print("  Install with: pip install python-docx")
    sys.exit(1)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
QUEUE = ROOT / "handoff_queue"
UPLOADS = ROOT / "data" / "uploads"

# ── Eli's fixed personal details ────────────────────────────────────────────────
FULL_NAME = "Eli Walchli"
CONTACT_LINE = (
    "XXX-XXX-XXXX | Portland, OR | eliwalchli@berkeley.edu"
    " | www.linkedin.com/in/eli-walchli"
)

# Signature image — searched in order; first match is used
SIG_SEARCH = [
    UPLOADS / "signature.png",
    UPLOADS / "signature.jpg",
    UPLOADS / "signature.jpeg",
    ROOT / "data" / "signature.png",
    ROOT / "data" / "signature.jpg",
]


# ── Helpers ─────────────────────────────────────────────────────────────────────

def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "company"


def load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(p: Path, data: dict) -> None:
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def today_string() -> str:
    """Return today as 'June 9, 2026' — cross-platform (no %-d)."""
    t = dt.date.today()
    return f"{t.strftime('%B')} {t.day}, {t.year}"


def find_signature() -> Path | None:
    for p in SIG_SEARCH:
        if p.exists():
            return p
    return None


# ── Body parsing ────────────────────────────────────────────────────────────────

def parse_body(body_file: Path) -> list[str]:
    """Parse body file into 4 paragraph strings. Fails clearly on bad input."""
    text = body_file.read_text(encoding="utf-8")

    if "PASTE_GENERATED_BODY_HERE" in text:
        print("ERROR: Body file still contains placeholder text.")
        print("  Cowork needs to generate the cover letter body first.")
        print(f"  File: {body_file}")
        sys.exit(1)

    # Strip comment lines (start with #)
    lines = [ln for ln in text.splitlines() if not ln.startswith("#")]
    cleaned = "\n".join(lines).strip()

    if not cleaned:
        print("ERROR: Body file is empty after stripping comments.")
        sys.exit(1)

    # Split on blank lines
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]

    if len(paragraphs) != 4:
        print(f"WARNING: Expected 4 paragraphs, found {len(paragraphs)}.")
        print("  Ensure paragraphs are separated by blank lines in the body file.")
        print("  Proceeding — review the output carefully before submitting.")

    # Validate P4 fixed sentences
    if len(paragraphs) >= 4:
        p4 = paragraphs[3]
        if not p4.startswith("Thank you for your time and consideration."):
            print("WARNING: P4 does not open with the required fixed sentence.")
            print('  Expected start: "Thank you for your time and consideration."')
            print(f'  Got:            "{p4[:70]}..."')
        contact_ok = "XXX-XXX-XXXX" in p4 and "eliwalchli@berkeley.edu" in p4
        if not contact_ok:
            print("WARNING: P4 closing sentence is missing the required phone / email.")

    return paragraphs


# ── Document helpers ────────────────────────────────────────────────────────────

def _para(doc: Document, text: str = "", font_size: float = 11.0,
          bold: bool = False, align=WD_ALIGN_PARAGRAPH.LEFT,
          space_before: float = 0.0, space_after: float = 0.0,
          font: str = "Georgia"):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        run = p.add_run(text)
        run.bold = bold
        run.font.name = font
        run.font.size = Pt(font_size)
    return p


def _blank(doc: Document):
    return _para(doc, "")


def _add_horizontal_rule(paragraph) -> None:
    """Add a bottom border to a paragraph, rendering as a horizontal rule."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pBdr.append(bottom)
    pPr.append(pBdr)


# ── Document builder ────────────────────────────────────────────────────────────

def build_docx(
    paragraphs: list[str],
    date_str: str,
    hiring_manager: str,
    address_lines: list[str],
    out_path: Path,
    sig_path: Path | None,
) -> None:
    doc = Document()

    # Page margins — tighter vertical to guarantee single-page fit
    for section in doc.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    # Clear default paragraph spacing from Normal style
    normal = doc.styles["Normal"]
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.space_after = Pt(0)
    normal.font.name = "Georgia"
    normal.font.size = Pt(11)

    # ── Name header — Playfair Display Bold ─────────────────────
    _para(doc, FULL_NAME, font_size=20.0, bold=True,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4.0,
          font="Playfair Display")

    # ── Contact line — Playfair Display Regular ──────────────────
    contact_p = _para(doc, CONTACT_LINE, font_size=10.0,
                      align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6.0,
                      font="Playfair Display")
    _add_horizontal_rule(contact_p)

    # ── Date ────────────────────────────────────────────────────
    _para(doc, date_str, space_before=12.0)

    # ── Blank ────────────────────────────────────────────────────
    _blank(doc)

    # ── Recipient block ──────────────────────────────────────────
    _para(doc, hiring_manager)
    for line in address_lines:
        _para(doc, line)

    # ── Blank ────────────────────────────────────────────────────
    _blank(doc)

    # ── Salutation ───────────────────────────────────────────────
    _para(doc, f"Dear {hiring_manager},")

    # ── Body paragraphs — blank line before each ─────────────────
    for para_text in paragraphs:
        # Safety: strip any em dashes that slipped through
        para_text = para_text.replace("—", ", ").replace("–", "-")
        _blank(doc)
        _para(doc, para_text)

    # ── Blank before sign-off ────────────────────────────────────
    _blank(doc)

    # ── Sincerely ────────────────────────────────────────────────
    _para(doc, "Sincerely,")

    # ── Signature image or blank space ───────────────────────────
    if sig_path:
        sig_p = doc.add_paragraph()
        sig_p.paragraph_format.space_before = Pt(4)
        sig_p.paragraph_format.space_after = Pt(0)
        sig_p.add_run().add_picture(str(sig_path), height=Inches(0.6))
    else:
        _blank(doc)
        _blank(doc)
        _blank(doc)

    # ── Printed name ─────────────────────────────────────────────
    _para(doc, FULL_NAME)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))


# ── Main ────────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Format a Cowork cover letter body into a .docx."
    )
    ap.add_argument("--body-file", required=True,
                    help="Path to body text file (Cowork output)")
    ap.add_argument("--job",
                    help="Path to handoff JSON — supplies company, title, address, hiring_manager")
    ap.add_argument("--company",
                    help="Company name (overrides handoff file)")
    ap.add_argument("--title",
                    help="Job title (overrides handoff file)")
    ap.add_argument("--hiring-manager",
                    help='Recipient line e.g. "Jane Smith" or "CBRE Hiring Team"')
    ap.add_argument("--address",
                    help='Address lines separated by commas. '
                         'e.g. "1750 Pennsylvania Ave NW,Washington, DC 20006"')
    ap.add_argument("--date",
                    help="Date string (default: today, e.g. 'June 9, 2026')")
    ap.add_argument("--signature",
                    help="Path to signature image (PNG/JPG). "
                         "Default: auto-detect signature.png in data/uploads/")
    ap.add_argument("--out",
                    help="Output .docx path "
                         "(default: data/uploads/<company-slug>_cover_letter.docx)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print text preview only — do not write any files")
    args = ap.parse_args()

    # ── Resolve body file ────────────────────────────────────────
    body_file = Path(args.body_file)
    if not body_file.exists():
        body_file = ROOT / args.body_file
    if not body_file.exists():
        print(f"ERROR: Body file not found: {args.body_file}")
        return 1

    paragraphs = parse_body(body_file)

    # ── Load handoff JSON ────────────────────────────────────────
    handoff: dict | None = None
    handoff_path: Path | None = None
    if args.job:
        handoff_path = Path(args.job)
        if not handoff_path.exists():
            handoff_path = ROOT / args.job
        if handoff_path.exists():
            handoff = load_json(handoff_path)
        else:
            print(f"WARNING: Handoff file not found: {args.job}")

    # ── Resolve metadata ─────────────────────────────────────────
    company = args.company
    title = args.title
    if handoff:
        job = handoff.get("job", {})
        company = company or job.get("company", "")
        title = title or job.get("title", "")
    company = company or "Company"
    title = title or "Position"

    # Hiring manager
    hiring_manager = args.hiring_manager
    if not hiring_manager and handoff:
        hiring_manager = handoff.get("hiring_manager")
    if not hiring_manager:
        hiring_manager = f"{company} Hiring Team"

    # Address lines
    address_lines: list[str] = []
    if args.address:
        address_lines = [ln.strip() for ln in args.address.split(",") if ln.strip()]
    elif handoff:
        raw = handoff.get("address")
        if isinstance(raw, list):
            address_lines = raw
        elif isinstance(raw, str) and raw:
            address_lines = [ln.strip() for ln in raw.split(",") if ln.strip()]

    if not address_lines:
        address_lines = [company, "[Street Address]", "[City, State ZIP]"]
        print("WARNING: No address found. Placeholder inserted.")
        print("  Fix: add 'address' list to the handoff JSON, or pass --address 'Line1,Line2'")

    # Date
    date_str = args.date or today_string()

    # Signature
    sig_path: Path | None = None
    if args.signature:
        candidate = Path(args.signature)
        sig_path = candidate if candidate.exists() else None
        if not sig_path:
            print(f"WARNING: Signature image not found: {args.signature}")
    else:
        sig_path = find_signature()
        if not sig_path:
            print("INFO: No signature image found.")
            print("  Drop signature.png into data/uploads/ to embed it automatically.")
            print("  Three blank lines will be left for a manual signature.")

    # Output path
    out_path = Path(args.out) if args.out else UPLOADS / f"{slug(company)}_cover_letter.docx"

    # ── Dry run ──────────────────────────────────────────────────
    if args.dry_run:
        bar = "-" * 64
        print(f"\n{bar}")
        print(f"{FULL_NAME:^64}")
        print(f"{CONTACT_LINE:^64}")
        print(bar)
        print(f"\n{date_str}\n")
        print(hiring_manager)
        for line in address_lines:
            print(line)
        print(f"\nDear {hiring_manager},\n")
        for i, para in enumerate(paragraphs, 1):
            print(f"[P{i}] {para}\n")
        sig_label = f"[signature: {sig_path.name}]" if sig_path else "[blank space for signature]"
        print(f"Sincerely,\n{sig_label}\n{FULL_NAME}")
        print(f"\n{bar}")
        print(f"Would write: {out_path}")
        return 0

    # ── Build .docx ──────────────────────────────────────────────
    build_docx(
        paragraphs=paragraphs,
        date_str=date_str,
        hiring_manager=hiring_manager,
        address_lines=address_lines,
        out_path=out_path,
        sig_path=sig_path,
    )

    print(f"\nCover letter: {title} @ {company}")
    print(f"  Written to:  {out_path}")
    print(f"  Signature:   {sig_path.name if sig_path else 'not embedded (blank space left)'}")

    # ── Update handoff file ──────────────────────────────────────
    if handoff is not None and handoff_path is not None:
        try:
            rel = str(out_path.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            rel = str(out_path).replace("\\", "/")
        handoff["cover_letter"] = rel
        handoff["status"] = "ready"
        save_json(handoff_path, handoff)
        print(f"  Handoff:     {handoff_path.name} → status=ready")

    print(f"\nNext: python scripts/apply.py --job {handoff_path or '[handoff file path]'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

