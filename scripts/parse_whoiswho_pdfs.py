"""
Parse EU Who Is Who PDF directories into structured JSON organigrammes.

Uses PyMuPDF (fitz) to extract text with formatting metadata (bold/italic)
to distinguish person names, titles, emails, phones, and org structure.

Usage:
    python3.12 scripts/parse_whoiswho_pdfs.py
    python3.12 scripts/parse_whoiswho_pdfs.py --file ecb
    python3.12 scripts/parse_whoiswho_pdfs.py --stats
"""
import argparse
import json
import os
import re
import sys
import fitz  # PyMuPDF

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "euwhoiswho")
OUTPUT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "backend", "knowledge_base", "ec_organigrammes", "json"
)

# Map PDF filenames to institution codes
PDF_TO_CODE = {
    "euwhoiswho_commission.pdf": "COMMISSION",
    "euwhoiswho_ep.pdf": "EP",
    "euwhoiswho_councileu.pdf": "COUNCIL_EU",
    "euwhoiswho_europeancouncil.pdf": "EUROPEAN_COUNCIL",
    "euwhoiswho_ecb.pdf": "ECB",
    "euwhoiswho_ecj.pdf": "ECJ",
    "euwhoiswho_eca.pdf": "ECA",
    "euwhoiswho_eeas.pdf": "EEAS",
    "euwhoiswho_cor.pdf": "COR",
    "euwhoiswho_eesc.pdf": "EESC",
    "euwhoiswho_eib.pdf": "EIB",
    "euwhoiswho_eif.pdf": "EIF",
    "euwhoiswho_edps.pdf": "EDPS",
    "euwhoiswho_ombudsman.pdf": "OMBUDSMAN",
    "euwhoiswho_agencies.pdf": "AGENCIES",
}

# Email domains per institution
INSTITUTION_DOMAINS = {
    "COMMISSION": "ec.europa.eu",
    "EP": "europarl.europa.eu",
    "COUNCIL_EU": "consilium.europa.eu",
    "EUROPEAN_COUNCIL": "consilium.europa.eu",
    "ECB": "ecb.europa.eu",
    "ECJ": "curia.europa.eu",
    "ECA": "eca.europa.eu",
    "EEAS": "eeas.europa.eu",
    "COR": "cor.europa.eu",
    "EESC": "eesc.europa.eu",
    "EIB": "eib.org",
    "EIF": "eif.org",
    "EDPS": "edps.europa.eu",
    "OMBUDSMAN": "ombudsman.europa.eu",
}

# Regex patterns
EMAIL_RE = re.compile(r'[\w.\-]+@[\w.\-]+\.\w+')
PHONE_RE = re.compile(r'(?:Tel\.?\s*)?(\+[\d\s\-().]+)')
NAME_PREFIX_RE = re.compile(r'^(Mr|Ms|Mrs|Dr|Prof\.?)\s+')
# Person name: "Mr/Ms Firstname LASTNAME" or "Firstname LASTNAME" with at least one ALL-CAPS word
PERSON_NAME_RE = re.compile(
    r'^(?:(?:Mr|Ms|Mrs|Dr|Prof\.?)\s+)?'
    r'([A-Z\u00C0-\u017E][\w\u00C0-\u017E\'\-]+(?:\s+[A-Z\u00C0-\u017E][\w\u00C0-\u017E\'\-]*)*)\s+'
    r'([A-Z\u00C0-\u017E][A-Z\u00C0-\u017E\'\-\s]+)$'
)


def is_bold(span):
    """Check if a text span is bold based on font flags."""
    flags = span.get("flags", 0)
    return bool(flags & 2**4)  # bit 4 = bold


def is_italic(span):
    """Check if a text span is italic based on font flags."""
    flags = span.get("flags", 0)
    return bool(flags & 2**1)  # bit 1 = italic


def extract_blocks(pdf_path):
    """Extract text blocks with formatting from a PDF using PyMuPDF dict output."""
    doc = fitz.open(pdf_path)
    all_lines = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        for block in blocks:
            if block["type"] != 0:  # skip images
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
                if re.match(r'^\d+\s*[-–]\s*\d{2}/\d{2}/\d{4}', line_text):
                    continue
                if "OFFICIAL DIRECTORY OF THE EUROPEAN UNION" in line_text:
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


def is_section_header(line):
    """Detect section/unit headers (blue text, larger font, or ALL CAPS non-person text)."""
    text = line["text"]
    fontsize = line["fontsize"]

    # Skip very short text
    if len(text) < 3:
        return False

    # Blue-colored headers (color != 0 and != black)
    color = line["color"]
    if color != 0 and color != 0x000000 and fontsize >= 9:
        return True

    # Large font size headers (title page sections)
    if fontsize >= 14 and line["bold"]:
        return True

    return False


def is_subsection_header(line):
    """Detect subsection headers: bold text with em-dash or unit keywords."""
    text = line["text"]
    if not line["bold"]:
        return False
    # Bold text with " — " or " -- " is a subsection (e.g., "SE — Supervision and Enforcement")
    if " — " in text or " -- " in text or " \u2014 " in text:
        return True
    return False


# Words that should never be detected as person names
FALSE_POSITIVE_NAMES = {
    "EUROPEAN", "UNION", "COUNCIL", "PARLIAMENT", "COMMISSION",
    "DIRECTORATE", "GENERAL", "SERVICE", "OFFICE", "DIVISION",
    "DEPARTMENT", "UNIT", "SECTION", "CABINET", "BUREAU",
    "AGENCY", "COMMITTEE", "BOARD", "COURT", "BANK",
}


def is_person_name(line):
    """Detect person names: bold text matching name pattern."""
    text = line["text"]
    if not line["bold"]:
        return False
    if line["italic"]:
        return False
    # Must not be a header (large font / blue)
    if is_section_header(line):
        return False
    # Must not be a subsection header
    if is_subsection_header(line):
        return False
    # Must not contain email or phone
    if "@" in text or "Tel." in text or text.startswith("+"):
        return False
    # Must not be a known non-name pattern
    if text.startswith("http") or text.startswith("www"):
        return False
    # Must not start with a false positive word
    first_word = text.split()[0].upper() if text.split() else ""
    if first_word in FALSE_POSITIVE_NAMES:
        return False
    # Check for person name pattern (has at least one uppercase-only word as surname)
    clean = NAME_PREFIX_RE.sub("", text).strip()
    if not clean:
        return False
    words = clean.split()
    if len(words) < 2:
        return False
    # At least one word should be ALL CAPS (surname) - allowing for diacritics
    has_caps = any(
        len(w) >= 2 and w == w.upper() and any(c.isalpha() for c in w)
        for w in words
    )
    return has_caps


def is_title_line(line):
    """Detect title/function lines (italic text)."""
    return line["italic"] and not line["bold"] and line["fontsize"] < 12


def parse_name(text):
    """Parse 'Mr Firstname LASTNAME' into (firstname, lastname)."""
    clean = NAME_PREFIX_RE.sub("", text).strip()
    words = clean.split()
    if not words:
        return text, ""

    # Find where surnames begin (first ALL-CAPS word)
    surname_start = -1
    for i, w in enumerate(words):
        if len(w) >= 2 and w == w.upper() and any(c.isalpha() for c in w):
            surname_start = i
            break

    if surname_start <= 0:
        # Fallback: last word is surname
        firstname = " ".join(words[:-1])
        lastname = words[-1]
    else:
        firstname = " ".join(words[:surname_start])
        lastname = " ".join(words[surname_start:])

    # Title-case the surname for consistency
    lastname = lastname.title()
    return firstname, lastname


def parse_pdf(pdf_path, institution_code):
    """Parse a single PDF into structured data."""
    lines = extract_blocks(pdf_path)

    sections = []
    current_section = None
    current_subsection = None
    current_person = None
    persons = []

    def flush_person():
        nonlocal current_person
        if current_person:
            # Assign to current subsection or section
            section_name = current_subsection or (current_section if current_section else "General")
            current_person["unit"] = section_name
            persons.append(current_person)
            current_person = None

    for line in lines:
        text = line["text"]

        # Skip boilerplate
        if "Note to the reader" in text or "strictly forbidden" in text:
            continue
        if "whoiswho@publications" in text or "Managed by the Publications" in text:
            continue
        if "Reproduction is authorised" in text:
            continue
        if text.startswith("Photo:"):
            continue

        # Section header (blue/large)
        if is_section_header(line):
            flush_person()
            header_text = text.strip()
            # Skip short codes like "BLMT", "isl"
            if len(header_text) <= 6 and header_text.isupper():
                continue
            current_section = header_text
            current_subsection = None
            if current_section not in sections:
                sections.append(current_section)
            continue

        # Subsection header (bold with em-dash, e.g., "SE — Supervision and Enforcement")
        if is_subsection_header(line):
            flush_person()
            current_subsection = text.strip()
            continue

        # Person name
        if is_person_name(line):
            flush_person()
            firstname, lastname = parse_name(text)
            current_person = {
                "name": f"{firstname} {lastname}".strip(),
                "firstname": firstname,
                "lastname": lastname,
                "title": "",
                "email": "",
                "phone": "",
                "unit": "",
            }
            continue

        # If we have a current person, check for title/email/phone
        if current_person:
            # Email
            email_match = EMAIL_RE.search(text)
            if email_match:
                current_person["email"] = email_match.group()
                continue

            # Phone
            phone_match = PHONE_RE.search(text)
            if phone_match and not email_match:
                phone = phone_match.group(1).strip()
                if len(phone) > 6:
                    current_person["phone"] = phone
                    continue

            # Title (italic text or known title patterns)
            if is_title_line(line):
                if current_person["title"]:
                    current_person["title"] += " -- " + text
                else:
                    current_person["title"] = text
                continue

            # Known title keywords even if not italic
            title_keywords = [
                "Director", "Head of", "President", "Vice-President",
                "Secretary", "Governor", "Member of", "Chair",
                "Commissioner", "Adviser", "Officer", "Administrator",
                "Coordinator", "Manager", "Inspector", "Legal officer",
                "Counsellor", "Chef de", "Expert", "Supervisor",
                "Executive Director", "Deputy", "Acting",
            ]
            if any(text.startswith(kw) or text == kw for kw in title_keywords):
                if current_person["title"]:
                    current_person["title"] += " -- " + text
                else:
                    current_person["title"] = text
                continue

        # Subsection / unit name (non-bold, non-italic, medium font, not a person)
        if not line["bold"] and not line["italic"] and line["fontsize"] >= 8:
            clean = text.strip()
            # Looks like a unit/division name
            unit_keywords = [
                "Division", "Unit", "Section", "Department", "Service",
                "Office", "Directorate", "Cabinet", "Bureau", "Team",
                "Sector", "Cell", "Branch", "Delegation",
            ]
            if any(kw in clean for kw in unit_keywords) and len(clean) > 5 and len(clean) < 120:
                flush_person()
                current_subsection = clean
                continue

    flush_person()

    return {
        "institution": institution_code,
        "source": os.path.basename(pdf_path),
        "data_date": "2026-02-27",
        "total_persons": len(persons),
        "sections": sections,
        "persons": persons,
    }


def build_organigramme_tree(parsed_data):
    """Build a tree-structured organigramme from flat parsed data."""
    institution = parsed_data["institution"]
    tree = {
        "institution": institution,
        "source": parsed_data["source"],
        "data_date": parsed_data["data_date"],
        "total_persons": parsed_data["total_persons"],
        "units": {},
    }

    for person in parsed_data["persons"]:
        unit = person["unit"]
        if unit not in tree["units"]:
            tree["units"][unit] = {
                "name": unit,
                "persons": [],
            }

        entry = {
            "name": person["name"],
            "title": person["title"],
        }
        if person["email"]:
            entry["email"] = person["email"]
        if person["phone"]:
            entry["phone"] = person["phone"]

        tree["units"][unit]["persons"].append(entry)

    return tree


def print_stats(data):
    """Print statistics for parsed data."""
    print(f"\n  Institution: {data['institution']}")
    print(f"  Source: {data['source']}")
    print(f"  Total persons: {data['total_persons']}")
    print(f"  Sections: {len(data.get('units', data.get('sections', [])))}")

    if "units" in data:
        # Count persons with emails
        emails = sum(
            1 for unit in data["units"].values()
            for p in unit["persons"]
            if p.get("email")
        )
        phones = sum(
            1 for unit in data["units"].values()
            for p in unit["persons"]
            if p.get("phone")
        )
        print(f"  With email: {emails}")
        print(f"  With phone: {phones}")

        # Top units by size
        unit_sizes = sorted(
            [(u["name"], len(u["persons"])) for u in data["units"].values()],
            key=lambda x: -x[1]
        )
        print(f"  Top units:")
        for name, count in unit_sizes[:10]:
            print(f"    {count:4d}  {name[:80]}")


def main():
    parser = argparse.ArgumentParser(description="Parse EU Who Is Who PDFs into JSON")
    parser.add_argument("--file", help="Parse a single PDF (e.g., 'ecb', 'commission')")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    parser.add_argument("--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Select files to process
    if args.file:
        matching = [f for f in PDF_TO_CODE if args.file.lower() in f.lower()]
        if not matching:
            print(f"[ERROR] No PDF matching '{args.file}'. Available: {list(PDF_TO_CODE.keys())}")
            sys.exit(1)
        files_to_process = {f: PDF_TO_CODE[f] for f in matching}
    else:
        files_to_process = PDF_TO_CODE

    total_persons = 0
    total_emails = 0

    for filename, code in files_to_process.items():
        pdf_path = os.path.join(PDF_DIR, filename)
        if not os.path.exists(pdf_path):
            print(f"[WARN] Missing: {pdf_path}")
            continue

        print(f"[INFO] Parsing {filename} -> {code}...")
        parsed = parse_pdf(pdf_path, code)
        tree = build_organigramme_tree(parsed)

        # Save JSON
        output_path = os.path.join(OUTPUT_DIR, f"{code}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(tree, f, indent=2, ensure_ascii=False)

        emails_count = sum(
            1 for unit in tree["units"].values()
            for p in unit["persons"]
            if p.get("email")
        )
        total_persons += tree["total_persons"]
        total_emails += emails_count

        print(f"[OK] {code}: {tree['total_persons']} persons, {emails_count} emails -> {output_path}")

        if args.stats or args.verbose:
            print_stats(tree)

    print(f"\n[DONE] Total: {total_persons} persons, {total_emails} emails across {len(files_to_process)} institutions")


if __name__ == "__main__":
    main()
