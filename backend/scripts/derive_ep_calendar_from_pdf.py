#!/usr/bin/env python3.12
"""
Derive the EP parliamentary-activities calendar from the European Parliament's
own published annual calendar PDF.

WHY THIS EXISTS
---------------
The EP publishes its annual calendar as a colour-coded grid. The week type is
encoded ONLY as the cell fill colour:

    red    (255,0,0)     Sessions (plenary)
    pink   (255,153,204) Committee meetings
    blue   (153,204,255) Political group meetings
    teal   (85,203,192)  External parliamentary activities (constituency weeks)
    white                Recess

`pdftotext` extracts the day numbers but SILENTLY DROPS the colour, so any
text-only parse of this PDF loses the entire signal. The hand-maintained
`ep_calendar_2026.json` that preceded this script had 33 of 53 weeks wrong,
including 10 of the 15 plenary weeks, and classified zero constituency weeks.

On 20 July 2026 that bad data caused Brubru to tell a paying subscriber that a
constituency week was an "EP Committee Week", via a proactive briefing Brubru
itself generated from the bad calendar row. See the audit in
docs/morning_routine/2026/07_july/2026-07-21-Tuesday.md.

METHOD
------
1. Render the PDF to a 300 dpi PNG (pdftoppm).
2. Extract every day-number's bounding box (pdftotext -bbox).
3. Map each number to (month-block, month-column) by page position.
4. Sample the interior of each day's cell and classify its fill against the
   legend colours.
5. Reduce Mon-Fri day classifications to a week label, plenary taking
   precedence (a week containing a session day IS a session week).
6. Emit per-day detail alongside the week label, because EP weeks are NOT
   always homogeneous (e.g. 7-11 Sep 2026 is committee/group/group/committee).

VERIFICATION (run automatically, script aborts on failure)
----------------------------------------------------------
Every derived plenary day is cross-checked against the EP's own published list
of session dates, which is maintained independently of the PDF. Both the
"every official session was found" and the "no red day outside an official
session" directions must hold.

USAGE
-----
    python3.12 scripts/derive_ep_calendar_from_pdf.py --year 2026
    python3.12 scripts/derive_ep_calendar_from_pdf.py --year 2026 --dry-run

Requires poppler (`pdftoppm`, `pdftotext`) and Pillow.
"""

from __future__ import annotations

import argparse
import calendar as calmod
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    print("[ERROR] Pillow is required: pip install Pillow")
    sys.exit(1)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

CALENDAR_PDF_URLS = {
    2026: "https://www.europarl.europa.eu/cmsdata/298340/EP%20Calendar%202026_EN.pdf",
}

# Exact legend swatch colours, sampled from the PDF's own legend block.
LEGEND = {
    (255, 0, 0): "plenary_session",
    (255, 153, 204): "committee_week",
    (153, 204, 255): "group_week",
    (85, 203, 192): "external_activities",
}

# A week containing any session day is a session week; otherwise the most
# frequent Mon-Fri activity wins, ties broken by this order.
PRECEDENCE = [
    "plenary_session",
    "committee_week",
    "group_week",
    "external_activities",
    "recess",
]

# Page-fraction bands for the 4 month-block rows and 3 month columns.
BLOCK_BANDS = [(0.125, 0.29), (0.29, 0.455), (0.455, 0.62), (0.62, 0.79)]
COLUMN_BANDS = [(0.070, 0.360), (0.360, 0.645), (0.645, 0.935)]

RENDER_DPI = 300
PDF_POINTS_PER_INCH = 72

# The EP publishes its session dates separately from the calendar PDF. This is
# the independent control used to verify the colour extraction.
# Source: europarl.europa.eu press release 20250310IPR27231.
OFFICIAL_SESSIONS = {
    2026: [
        ("2026-01-19", "2026-01-22"),
        ("2026-01-27", "2026-01-27"),  # Holocaust Remembrance, Art 229 TFEU
        ("2026-02-09", "2026-02-12"),
        ("2026-03-09", "2026-03-12"),
        ("2026-03-25", "2026-03-26"),
        ("2026-04-27", "2026-04-30"),
        ("2026-05-18", "2026-05-21"),
        ("2026-06-15", "2026-06-18"),
        ("2026-07-06", "2026-07-09"),
        ("2026-09-14", "2026-09-17"),
        ("2026-10-05", "2026-10-08"),
        ("2026-10-19", "2026-10-22"),
        ("2026-11-11", "2026-11-12"),
        ("2026-11-23", "2026-11-26"),
        ("2026-12-14", "2026-12-17"),
    ],
}

SPECIAL_DATES = {
    2026: {"europe_day": {"date": "2026-05-09", "description": "Europe Day"}},
}

MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]


# --------------------------------------------------------------------------
# PDF handling
# --------------------------------------------------------------------------

def _run(cmd: List[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {result.stderr.strip()}")


def fetch_pdf(year: int, workdir: str, pdf_path: Optional[str]) -> str:
    """Return a local path to the calendar PDF, downloading it if needed."""
    if pdf_path:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(pdf_path)
        return pdf_path

    url = CALENDAR_PDF_URLS.get(year)
    if not url:
        raise ValueError(
            f"No calendar PDF URL known for {year}. Pass --pdf with a local copy."
        )
    dest = os.path.join(workdir, f"ep_calendar_{year}.pdf")
    print(f"[INFO] Downloading {url}")
    _run(["curl", "-sL", "-A", "Mozilla/5.0", "-o", dest, url])
    if not os.path.exists(dest) or os.path.getsize(dest) < 10_000:
        raise RuntimeError("Downloaded calendar PDF looks empty or truncated")
    return dest


def render_and_extract(pdf: str, workdir: str) -> Tuple["Image.Image", str]:
    """Render page 1 to PNG at RENDER_DPI and extract word bounding boxes."""
    png_prefix = os.path.join(workdir, "page")
    _run(["pdftoppm", "-png", "-r", str(RENDER_DPI), "-f", "1", "-l", "1",
          pdf, png_prefix])
    pngs = sorted(f for f in os.listdir(workdir) if f.startswith("page")
                  and f.endswith(".png"))
    if not pngs:
        raise RuntimeError("pdftoppm produced no PNG")
    image = Image.open(os.path.join(workdir, pngs[0])).convert("RGB")

    bbox_path = os.path.join(workdir, "words.xhtml")
    _run(["pdftotext", "-bbox", pdf, bbox_path])
    with open(bbox_path, "r", encoding="utf-8") as handle:
        return image, handle.read()


# --------------------------------------------------------------------------
# Colour classification
# --------------------------------------------------------------------------

def _cluster(values: List[float], tolerance: float) -> List[float]:
    """Group nearby coordinates into their mean positions."""
    values = sorted(values)
    groups: List[List[float]] = [[values[0]]]
    for value in values[1:]:
        if value - groups[-1][-1] <= tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(g) / len(g) for g in groups]


def classify_days(image: "Image.Image", bbox_xml: str,
                  year: int) -> Dict[dt.date, str]:
    """Return {date: activity_type} for every day of the year."""
    width, height = image.size
    scale = RENDER_DPI / PDF_POINTS_PER_INCH

    pattern = (r'<word xMin="([\d.]+)" yMin="([\d.]+)" '
               r'xMax="([\d.]+)" yMax="([\d.]+)">(\d{1,2})</word>')
    cells: Dict[Tuple[int, int], List[Tuple[float, float, int]]] = defaultdict(list)
    for match in re.finditer(pattern, bbox_xml):
        x0, y0, x1, y1 = (float(match.group(i)) * scale for i in range(1, 5))
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        block = next((i for i, (a, b) in enumerate(BLOCK_BANDS)
                      if a <= cy / height < b), None)
        column = next((i for i, (a, b) in enumerate(COLUMN_BANDS)
                       if a <= cx / width < b), None)
        if block is not None and column is not None:
            cells[(block, column)].append((cx, cy, int(match.group(5))))

    day_activity: Dict[dt.date, str] = {}
    for (block, column), items in sorted(cells.items()):
        month = block * 3 + column + 1
        days_in_month = calmod.monthrange(year, month)[1]

        xs = _cluster([c[0] for c in items], 20)
        ys = _cluster([c[1] for c in items], 10)
        # The topmost row holds ISO week numbers, not days. Always drop it.
        header_y = ys[0]
        cell_w = (xs[1] - xs[0]) if len(xs) > 1 else 80
        row_h = (ys[2] - ys[1]) if len(ys) > 2 else 28

        for cx, cy, number in items:
            if abs(cy - header_y) < row_h * 0.5:
                continue
            if not 1 <= number <= days_in_month:
                continue
            x0, x1 = int(cx - cell_w * 0.42), int(cx + cell_w * 0.42)
            y0, y1 = int(cy - row_h * 0.40), int(cy + row_h * 0.40)
            pixels = [
                image.getpixel((x, y))
                for x in range(max(0, x0), min(width, x1))
                for y in range(max(0, y0), min(height, y1))
            ]
            hits = [p for p in pixels if p in LEGEND]
            if hits and len(hits) / max(1, len(pixels)) > 0.15:
                activity = LEGEND[Counter(hits).most_common(1)[0][0]]
            else:
                activity = "recess"
            day_activity[dt.date(year, month, number)] = activity

    return day_activity


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

def apply_official_sessions(day_activity: Dict[dt.date, str], year: int) -> int:
    """Force the EP's published session days to plenary_session.

    The PDF renders a day that changes activity mid-week as a diagonally split
    cell (half committee pink, half session red). Sampling picks whichever
    colour dominates the cell, so the first day of a short session can read as
    committee or group. The EP publishes its session dates separately, and for
    the question "is this specific day a sitting day" that list is
    authoritative. Overlaying it fixes the split cells without weakening the
    verification below, which still checks the PDF found every session week.
    """
    corrected = 0
    for start_s, end_s in OFFICIAL_SESSIONS.get(year, []):
        start, end = dt.date.fromisoformat(start_s), dt.date.fromisoformat(end_s)
        for offset in range((end - start).days + 1):
            day = start + dt.timedelta(days=offset)
            if day_activity.get(day) != "plenary_session":
                day_activity[day] = "plenary_session"
                corrected += 1
    if corrected:
        print(f"[INFO] Overlaid {corrected} published session day(s) onto "
              f"split PDF cells")
    return corrected


def verify(day_activity: Dict[dt.date, str], year: int) -> None:
    """Cross-check derived session days against the EP's published dates.

    Aborts the run on any mismatch. This is the guard that makes the output
    trustworthy: the colour extraction and the published session list are
    independent sources, so agreement between them is meaningful.
    """
    expected_days = calmod.isleap(year) and 366 or 365
    if len(day_activity) != expected_days:
        raise AssertionError(
            f"classified {len(day_activity)} days, expected {expected_days}"
        )

    sessions = OFFICIAL_SESSIONS.get(year)
    if not sessions:
        print(f"[WARN] No official session list for {year}; skipping cross-check")
        return

    derived = {d for d, a in day_activity.items() if a == "plenary_session"}

    missing = []
    official_days = set()
    for start_s, end_s in sessions:
        start, end = dt.date.fromisoformat(start_s), dt.date.fromisoformat(end_s)
        span = {start + dt.timedelta(i) for i in range((end - start).days + 1)}
        official_days |= span
        if not span & derived:
            missing.append(f"{start_s}..{end_s}")

    stray = sorted(d.isoformat() for d in derived - official_days)

    if missing:
        raise AssertionError(f"official sessions not found in PDF: {missing}")
    if stray:
        raise AssertionError(f"session days outside the official list: {stray}")

    print(f"[OK] Verified: {len(sessions)}/{len(sessions)} official sessions "
          f"located, 0 stray session days")


# --------------------------------------------------------------------------
# Week reduction + JSON assembly
# --------------------------------------------------------------------------

def week_label(weekday_activities: List[str]) -> str:
    """Reduce Mon-Fri day activities to a single week label."""
    working = [a for a in weekday_activities if a]
    if not working:
        return "recess"
    if "plenary_session" in working:
        return "plenary_session"
    counts = Counter(a for a in working if a != "recess")
    if not counts:
        return "recess"
    return min(counts, key=lambda k: (-counts[k], PRECEDENCE.index(k)))


def build_calendar(day_activity: Dict[dt.date, str], year: int) -> dict:
    """Assemble the calendar JSON, keyed by month then week."""
    first = dt.date(year, 1, 1)
    monday = first - dt.timedelta(days=first.weekday())
    last = dt.date(year, 12, 31)

    weeks = []
    while monday <= last:
        days = [monday + dt.timedelta(i) for i in range(7)]
        activities = [day_activity.get(d) for d in days]
        label = week_label(activities[:5])

        entry = {
            "week_number": monday.isocalendar()[1],
            "dates": f"{days[0]} to {days[6]}",
            "activity_type": label,
        }

        # Plenary weeks record their exact session days so the loader can emit
        # per-day events rather than a blanket multi-day block.
        if label == "plenary_session":
            entry["session_days"] = [
                DAY_NAMES[i] for i in range(5)
                if activities[i] == "plenary_session"
            ]

        # Per-day detail: EP weeks are not always homogeneous. Consumers that
        # need to answer "what is on TODAY" must read this, not the week label.
        daily = {
            DAY_NAMES[i]: activities[i]
            for i in range(5)
            if activities[i] and activities[i] != "recess"
        }
        if daily and set(daily.values()) != {label}:
            entry["daily"] = daily

        weeks.append((monday, entry))
        monday += dt.timedelta(days=7)

    months: Dict[str, dict] = {}
    for start, entry in weeks:
        # A week belongs to the month(s) it touches; mirror the PDF layout by
        # listing it under every month it overlaps.
        end = start + dt.timedelta(days=6)
        for month in sorted({start.month, end.month}):
            if start.year != year and end.year != year:
                continue
            name = MONTH_NAMES[month - 1]
            bucket = months.setdefault(name, {"month_number": month, "weeks": []})
            if entry not in bucket["weeks"]:
                bucket["weeks"].append(entry)

    ordered = {name: months[name] for name in MONTH_NAMES if name in months}

    return {
        "year": year,
        "institution": "European Parliament",
        "calendar_type": "Parliamentary Activities Calendar",
        "source": {
            "pdf": CALENDAR_PDF_URLS.get(year),
            "derived_by": "backend/scripts/derive_ep_calendar_from_pdf.py",
            "method": (
                "Cell fill colours sampled from a 300 dpi render of the EP's "
                "official calendar PDF. Week type is encoded only as colour and "
                "is not recoverable from pdftotext output."
            ),
            "verified_against": (
                "EP published session dates (press release 20250310IPR27231): "
                "all official sessions located, no session days outside the list."
            ),
            "generated": dt.date.today().isoformat(),
        },
        "special_dates": SPECIAL_DATES.get(year, {}),
        "activity_types": {
            "plenary_session": "Plenary sessions (Article 229 TFEU)",
            "committee_week": "Committee meetings",
            "group_week": "Political group meetings",
            "external_activities": (
                "External parliamentary activities (constituency weeks)"
            ),
            "recess": "Recess",
        },
        "months": ordered,
        "notes": {
            "scrutiny_sessions": (
                "The Conference of Presidents can schedule scrutiny sessions in "
                "group and committee weeks on Wednesday afternoon"
            ),
            "article_229_tfeu": (
                "EP session according to Article 229 of the Treaty on the "
                "Functioning of the European Union"
            ),
            "calendar_flexibility": (
                "Calendar is subject to changes by decision of the Conference "
                "of Presidents"
            ),
            "mixed_weeks": (
                "Weeks are not always homogeneous. Where a week mixes activity "
                "types, the 'daily' key carries the per-day breakdown and the "
                "'activity_type' is the dominant Mon-Fri label. Anything that "
                "answers a question about a SPECIFIC DAY must read 'daily'."
            ),
        },
    }


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--pdf", help="Path to a local calendar PDF")
    parser.add_argument("--out", help="Output JSON path")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the diff without writing")
    args = parser.parse_args()

    out_path = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "knowledge_base", "calendars", f"ep_calendar_{args.year}.json",
    )

    with tempfile.TemporaryDirectory() as workdir:
        pdf = fetch_pdf(args.year, workdir, args.pdf)
        image, bbox_xml = render_and_extract(pdf, workdir)
        day_activity = classify_days(image, bbox_xml, args.year)
        # Verify FIRST, on the untouched PDF-derived data. Overlaying the
        # published session list before verifying would make the check
        # tautological: it would be validating the overlay against itself.
        verify(day_activity, args.year)
        apply_official_sessions(day_activity, args.year)

    payload = build_calendar(day_activity, args.year)

    # Report the delta against whatever is on disk today.
    if os.path.exists(out_path):
        with open(out_path, "r", encoding="utf-8") as handle:
            previous = json.load(handle)
        old_weeks = {}
        for month in previous.get("months", {}).values():
            for week in month.get("weeks", []):
                old_weeks[week["dates"]] = week["activity_type"]
        new_weeks = {}
        for month in payload["months"].values():
            for week in month["weeks"]:
                new_weeks[week["dates"]] = week["activity_type"]
        changed = [(k, old_weeks.get(k, "(absent)"), v)
                   for k, v in sorted(new_weeks.items())
                   if old_weeks.get(k) != v]
        print(f"[INFO] {len(changed)} of {len(new_weeks)} weeks change:")
        for dates, old, new in changed:
            print(f"       {dates}  {old:22} -> {new}")

    # Boundary weeks are listed under both months they touch, so count uniques.
    unique_weeks = {
        week["dates"]: week["activity_type"]
        for month in payload["months"].values()
        for week in month["weeks"]
    }
    distribution = Counter(unique_weeks.values())
    print(f"[INFO] {len(unique_weeks)} distinct weeks: {dict(distribution)}")

    if args.dry_run:
        print("[INFO] Dry run: nothing written")
        return 0

    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"[OK] Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
