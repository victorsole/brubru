"""
Parse the Commission EU Who Is Who PDF into per-DG JSON organigrammes.

Detects DG-level headers (e.g., "DG TRADE -- Directorate-General for Trade")
and outputs one JSON file per DG in the format expected by the context builder.

Usage:
    python3.12 scripts/parse_commission_pdf.py
    python3.12 scripts/parse_commission_pdf.py --stats
"""
import argparse
import json
import os
import re
import fitz  # PyMuPDF

PDF_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "euwhoiswho", "euwhoiswho_commission.pdf"
)
OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "backend", "knowledge_base", "ec_organigrammes", "json"
)

# Regex to detect DG-level header: "DG CODE -- Name" or "CODE -- Name"
DG_HEADER_RE = re.compile(
    r'^(?:DG\s+)?([A-Z][A-Z0-9.\s/]+?)\s*(?:\u2014|—|--)\s*(.+)$'
)

# Regex to detect directorate header: "Dir X -- Name" or "DIR X -- Name"
DIR_HEADER_RE = re.compile(
    r'^(?:Dir|DIR)\s+([A-Z0-9/.\-]+(?:\s*[A-Z0-9/.\-]+)*)\s*(?:\u2014|—|--)\s*(.+)$'
)

# Person name patterns
NAME_PREFIX_RE = re.compile(r'^(Mr|Ms|Mrs|Dr|Prof\.?)\s+')
EMAIL_RE = re.compile(r'[\w.\-]+@[\w.\-]+\.\w+')
PHONE_RE = re.compile(r'(?:Tel\.?\s*)?(\+[\d\s\-().]+)')

# Known Commission DG/service codes (from TOC of the PDF)
# Only these codes should be detected as DG-level headers
KNOWN_DG_CODES = {
    "REFOR", "SG", "SJ", "COMM", "IDEA", "BUDG", "HR", "DIGIT", "IAS",
    "OLAF", "ECFIN", "GROW", "DEFIS", "COMP", "EMPL", "MOVE", "ENER",
    "ENV", "CLIMA", "RTD", "CNECT", "CONNECT", "JRC", "MARE", "FISMA",
    "REGIO", "EAC", "SANTE", "HERA", "HOME", "JUST", "TRADE", "NEAR",
    "ENEST", "INTPA", "ECHO", "ESTAT", "SCIC", "DGT", "OP", "FPI",
    "PMO", "OIL", "EPSO", "MENA", "TAXUD",
}

# Words that should never be detected as person names
FALSE_POSITIVE_NAMES = {
    'EUROPEAN', 'UNION', 'COUNCIL', 'PARLIAMENT', 'COMMISSION',
    'DIRECTORATE', 'GENERAL', 'SERVICE', 'OFFICE', 'DIVISION',
    'DEPARTMENT', 'UNIT', 'SECTION', 'CABINET', 'BUREAU',
    'AGENCY', 'COMMITTEE', 'BOARD', 'COURT', 'BANK',
    'LIST', 'BUILDINGS', 'BRUSSELS', 'LUXEMBOURG', 'STRASBOURG',
}


def is_bold(span):
    return bool(span.get("flags", 0) & 2**4)


def is_italic(span):
    return bool(span.get("flags", 0) & 2**1)


def extract_lines(pdf_path):
    """Extract text lines with formatting from Commission PDF."""
    doc = fitz.open(pdf_path)
    all_lines = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        for block in blocks:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                line_text = ""
                line_bold = False
                line_italic = False
                line_fontsize = 0
                line_color = 0

                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    line_text += (" " if line_text else "") + text
                    if is_bold(span):
                        line_bold = True
                    if is_italic(span):
                        line_italic = True
                    line_fontsize = max(line_fontsize, span["size"])
                    line_color = span.get("color", 0)

                line_text = line_text.strip()
                if not line_text:
                    continue
                # Skip page footers
                if re.match(r'^\d+\s*[-\u2013]\s*\d{2}/\d{2}/\d{4}', line_text):
                    continue
                if "OFFICIAL DIRECTORY OF THE EUROPEAN UNION" in line_text:
                    continue
                if "EUROPEAN COMMISSION" in line_text and len(line_text) < 40:
                    continue

                all_lines.append({
                    "text": line_text,
                    "bold": line_bold,
                    "italic": line_italic,
                    "fontsize": round(line_fontsize, 1),
                    "color": line_color,
                    "page": page_num + 1,
                })

    doc.close()
    return all_lines


def is_blue(color):
    """Check if a color value is blue-ish (non-zero, non-black)."""
    return color != 0 and color != 0x000000


def is_dg_header(line):
    """Detect DG-level headers matching 'DG CODE -- Name' pattern.

    Matches two formats:
    - TOC entries: blue text at 11pt (pages 11-18)
    - Content section headers: black text at 22pt (pages 29+)

    Only matches known DG codes from KNOWN_DG_CODES to avoid false positives
    from directorate headers (Dir A, Dir B, etc.) which share the same format.
    """
    text = line["text"].strip()
    if not text or text.startswith("Dir "):
        return False
    # Two valid formats: blue TOC headers (>=9pt) or large content headers (>=15pt)
    is_valid_format = (
        (is_blue(line["color"]) and line["fontsize"] >= 9)
        or (line["fontsize"] >= 15)
    )
    if not is_valid_format:
        return False
    m = DG_HEADER_RE.match(text)
    if m:
        code = m.group(1).strip().replace(" ", "")
        if code in KNOWN_DG_CODES:
            # Reject false positives like "HR — Croatian" (language codes)
            name = m.group(2).strip().lower()
            if len(name) < 30 and name in {
                "croatian", "hungarian", "german", "french", "english",
                "spanish", "italian", "dutch", "polish", "romanian",
            }:
                return False
            return True
    return False


def extract_dg_code(text):
    """Extract DG code and name from header text."""
    m = DG_HEADER_RE.match(text.strip())
    if m:
        code = m.group(1).strip().replace(" ", "")
        # Normalize some codes
        code_map = {
            "ENEST": "NEAR",  # Old name
            "CNECT": "CONNECT",
        }
        code = code_map.get(code, code)
        name = m.group(2).strip()
        return code, name
    return None, None


def is_dir_header(line):
    """Detect directorate headers: 'Dir X -- Name' or 'DIR X -- Name' pattern."""
    text = line["text"].strip()
    if not text.upper().startswith("DIR "):
        return False
    return bool(DIR_HEADER_RE.match(text))


def is_person_name(line):
    """Detect person names: bold text with at least one ALL-CAPS surname word."""
    text = line["text"]
    if not line["bold"]:
        return False
    if line["italic"]:
        return False
    if is_blue(line["color"]) and line["fontsize"] >= 9:
        return False  # Likely a section header
    if "@" in text or "Tel." in text or text.startswith("+") or text.startswith("http"):
        return False
    # Check for subsection header (em-dash)
    if "\u2014" in text or " -- " in text:
        return False
    first_word = text.split()[0].upper() if text.split() else ""
    if first_word in FALSE_POSITIVE_NAMES:
        return False
    clean = NAME_PREFIX_RE.sub("", text).strip()
    if not clean:
        return False
    words = clean.split()
    if len(words) < 2:
        return False
    has_caps = any(
        len(w) >= 2 and w == w.upper() and any(c.isalpha() for c in w)
        for w in words
    )
    return has_caps


def parse_name(text):
    """Parse 'Mr Firstname LASTNAME' into (firstname, lastname)."""
    clean = NAME_PREFIX_RE.sub("", text).strip()
    words = clean.split()
    if not words:
        return text, ""
    surname_start = -1
    for i, w in enumerate(words):
        if len(w) >= 2 and w == w.upper() and any(c.isalpha() for c in w):
            surname_start = i
            break
    if surname_start <= 0:
        firstname = " ".join(words[:-1])
        lastname = words[-1]
    else:
        firstname = " ".join(words[:surname_start])
        lastname = " ".join(words[surname_start:])
    lastname = lastname.title()
    return firstname, lastname


def is_unit_header(line):
    """Detect unit/section headers within a directorate."""
    text = line["text"].strip()
    if not text:
        return False
    # Blue sub-headers
    if is_blue(line["color"]) and line["fontsize"] >= 8:
        return True
    # Bold text with unit keywords (not a person name)
    if line["bold"] and not is_person_name(line):
        unit_keywords = [
            "Unit", "Sector", "Team", "Cell", "Division",
            "Adviser", "Coordination", "Communication",
        ]
        if any(kw in text for kw in unit_keywords) and len(text) < 120:
            return True
    return False


def parse_commission_pdf():
    """Parse Commission PDF into per-DG structures."""
    lines = extract_lines(PDF_PATH)
    print(f"[INFO] Extracted {len(lines)} text lines from Commission PDF")

    dgs = {}  # code -> {name, directorates, persons}
    current_dg_code = None
    current_dg_name = None
    current_dir_code = None
    current_dir_name = None
    current_unit = None
    current_person = None

    # Pre-DG sections (Cabinets, etc.)
    cabinets_code = "CABINETS"

    def flush_person():
        nonlocal current_person
        if not current_person:
            return
        dg = current_dg_code or cabinets_code
        if dg not in dgs:
            dgs[dg] = {"name": current_dg_name or "Cabinets of Commissioners", "directorates": {}, "persons": []}
        # Store person with directorate/unit context
        current_person["directorate_code"] = current_dir_code or ""
        current_person["directorate_name"] = current_dir_name or ""
        current_person["unit"] = current_unit or ""
        dgs[dg]["persons"].append(current_person)
        current_person = None

    for line in lines:
        text = line["text"]

        # Skip boilerplate
        if any(skip in text for skip in [
            "Note to the reader", "strictly forbidden", "whoiswho@publications",
            "Managed by the Publications", "Reproduction is authorised",
            "Photo:", "http://ec.europa.eu"
        ]):
            continue

        # DG-level header
        if is_dg_header(line):
            flush_person()
            code, name = extract_dg_code(text)
            if code:
                current_dg_code = code
                current_dg_name = name
                current_dir_code = None
                current_dir_name = None
                current_unit = None
                if code not in dgs:
                    dgs[code] = {"name": name, "directorates": {}, "persons": []}
            continue

        # Cabinet header (special: "Cabinet of Commissioner/President...")
        if is_blue(line["color"]) and "Cabinet of" in text:
            flush_person()
            current_dg_code = cabinets_code
            current_dg_name = "Cabinets of Commissioners"
            current_dir_code = None
            current_dir_name = None
            current_unit = text.strip()
            if cabinets_code not in dgs:
                dgs[cabinets_code] = {"name": "Cabinets of Commissioners", "directorates": {}, "persons": []}
            continue

        # Directorate header
        if is_dir_header(line):
            flush_person()
            m = DIR_HEADER_RE.match(text.strip())
            if m:
                current_dir_code = f"Dir {m.group(1).strip()}"
                current_dir_name = m.group(2).strip()
                current_unit = None
            continue

        # Person name
        if is_person_name(line):
            flush_person()
            firstname, lastname = parse_name(text)
            current_person = {
                "name": f"{firstname} {lastname}".strip(),
                "title": "",
                "email": "",
                "phone": "",
            }
            continue

        # Email
        if current_person:
            email_match = EMAIL_RE.search(text)
            if email_match:
                current_person["email"] = email_match.group()
                continue

            phone_match = PHONE_RE.search(text)
            if phone_match and "@" not in text:
                phone = phone_match.group(1).strip()
                if len(phone) > 6:
                    current_person["phone"] = phone
                    continue

            if line["italic"] and not line["bold"]:
                if current_person["title"]:
                    current_person["title"] += " -- " + text
                else:
                    current_person["title"] = text
                continue

            title_starts = [
                "Director", "Head of", "Adviser", "Deputy", "Acting",
                "Commissioner", "Chief", "Coordinator", "Manager",
                "Secretary", "President", "Chef de", "Officer",
            ]
            if any(text.startswith(kw) for kw in title_starts):
                if current_person["title"]:
                    current_person["title"] += " -- " + text
                else:
                    current_person["title"] = text
                continue

        # Unit/section name within directorate
        if not line["bold"] and not line["italic"] and line["fontsize"] >= 7.5:
            clean = text.strip()
            if len(clean) > 3 and len(clean) < 120 and not EMAIL_RE.search(clean):
                # Check if it looks like a unit name
                if any(kw in clean for kw in ["Unit", "Section", "Team", "Sector", "Office"]):
                    flush_person()
                    current_unit = clean

    flush_person()
    return dgs


def build_dg_json(code, dg_data):
    """Build a DG JSON in the format expected by the context builder."""
    # Group persons by directorate
    dir_map = {}
    dg_leader = None
    deputy_dgs = []

    for person in dg_data["persons"]:
        title = person.get("title", "").lower()
        dir_code = person.get("directorate_code", "")
        dir_name = person.get("directorate_name", "")

        # Detect DG leadership
        if "director-general" in title or "director general" in title:
            if not dg_leader and "deputy" not in title:
                dg_leader = person
                continue
            elif "deputy" in title:
                deputy_dgs.append(person)
                continue

        # Group into directorates
        key = dir_code or "General"
        if key not in dir_map:
            dir_map[key] = {
                "code": dir_code,
                "name": dir_name or key,
                "director": "",
                "director_email": "",
                "units": [],
            }

        # First person in a directorate is likely the director
        if not dir_map[key]["director"] and ("director" in title or not dir_map[key]["units"]):
            if "director" in title and "deputy" not in title:
                dir_map[key]["director"] = person["name"]
                dir_map[key]["director_email"] = person.get("email", "")
                continue

        dir_map[key]["units"].append({
            "code": person.get("unit", ""),
            "name": person.get("unit", person.get("title", "")),
            "head": person["name"],
            "head_email": person.get("email", ""),
            "head_phone": person.get("phone", ""),
        })

    return {
        "dg_code": code,
        "dg_name": dg_data["name"],
        "commissioner": "",
        "director_general": dg_leader["name"] if dg_leader else "",
        "director_general_email": dg_leader.get("email", "") if dg_leader else "",
        "deputy_directors_general": [
            {"name": d["name"], "email": d.get("email", ""), "responsibilities": ""}
            for d in deputy_dgs
        ],
        "directorates": list(dir_map.values()),
        "num_directorates": len(dir_map),
        "num_units": sum(len(d["units"]) for d in dir_map.values()),
        "source": "euwhoiswho_commission.pdf",
        "data_date": "2026-03-02",
    }


def main():
    parser = argparse.ArgumentParser(description="Parse Commission PDF into per-DG JSONs")
    parser.add_argument("--stats", action="store_true")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    dgs = parse_commission_pdf()
    print(f"\n[INFO] Found {len(dgs)} DGs/services")

    total_persons = 0
    total_emails = 0

    for code in sorted(dgs.keys()):
        dg_data = dgs[code]
        persons = dg_data["persons"]
        emails = sum(1 for p in persons if p.get("email"))
        total_persons += len(persons)
        total_emails += emails

        # Build and save per-DG JSON
        dg_json = build_dg_json(code, dg_data)
        output_path = os.path.join(OUTPUT_DIR, f"{code}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(dg_json, f, indent=2, ensure_ascii=False)

        print(f"[OK] {code:12s} {dg_data['name'][:50]:52s} {len(persons):4d} persons  {emails:4d} emails -> {code}.json")

    print(f"\n[DONE] {total_persons} persons, {total_emails} emails across {len(dgs)} DGs/services")


if __name__ == "__main__":
    main()
