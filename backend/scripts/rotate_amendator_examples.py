"""
Rotate Amendator Featured Examples.

Used by /news to add new "Hot files this week" entries to the Amendator panel.
Soft-deactivates the oldest active item when active count exceeds 10. Items are
NEVER deleted -- they remain in the table with is_active=FALSE for audit.

Usage:
    python3.12 scripts/rotate_amendator_examples.py \\
        --celex 52026DC0380 \\
        --url "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:52026DC0380" \\
        --title "Better Regulation Communication COM(2026) 380" \\
        --description "Annex I 12-area Regulatory Deep Cleaning Action Plan" \\
        --source news

Repeat the flags per call. ALWAYS use --action append-style flags one per item.
"""

import argparse
import sys
from pathlib import Path

# Make backend/ importable when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from core.database import SessionLocal


MAX_ACTIVE = 10


AMENDABLE_TYPES = {
    "regulation", "directive", "decision_legislative",
    "proposal_cod", "proposal_app", "proposal_cns",
}

MIN_RECITALS = 5
MIN_ARTICLES = 3
VERIFY_ENDPOINT = "http://127.0.0.1:8000/api/documents/fetch-eurlex"


def verify_amendable(url: str, language: str = "EN") -> tuple[bool, str]:
    """Probe the /api/documents/fetch-eurlex endpoint with the candidate URL.

    Returns (ok, message). Only counts as ok if the parser returns at least
    MIN_RECITALS recitals AND MIN_ARTICLES articles — i.e. the document has
    real legislative structure that the Amendator can manipulate.
    """
    import json as _json
    import urllib.request as _ur

    body = _json.dumps({"url": url, "format": "html", "language": language}).encode()
    req = _ur.Request(VERIFY_ENDPOINT, data=body,
                      headers={"Content-Type": "application/json"}, method="POST")
    try:
        with _ur.urlopen(req, timeout=60) as resp:
            data = _json.load(resp)
    except Exception as e:
        return False, f"verify HTTP error: {e}"

    els = ((data.get("structure") or {}).get("legislative_structure") or {}).get("elements", [])
    rec = sum(1 for e in els if e.get("type") == "recital")
    art = sum(1 for e in els if e.get("type") in ("article", "article_title"))
    if rec >= MIN_RECITALS and art >= MIN_ARTICLES:
        return True, f"parsed rec={rec} art={art}"
    return False, f"parser returned rec={rec} art={art} (need ≥{MIN_RECITALS}/{MIN_ARTICLES})"


def add_example(celex: str | None, url: str, title: str, description: str | None,
                source: str | None, document_type: str | None = None,
                skip_verify: bool = False) -> tuple[bool, str]:
    """Insert one new example. Returns (added, message).

    `document_type` should be one of AMENDABLE_TYPES for the entry to surface
    in the UI. Non-amendable types are stored but filtered out by the API.
    """
    if document_type and document_type not in AMENDABLE_TYPES:
        return False, (f"refused: document_type={document_type!r} is not amendable. "
                       f"Allowed: {sorted(AMENDABLE_TYPES)}")

    # Verify the URL actually parses before exposing to users. This catches
    # CELEX mistakes (wrong document) and dead URLs (404 from Cellar + EP RegData).
    if not skip_verify:
        ok, msg = verify_amendable(url)
        if not ok:
            return False, f"verify failed: {msg}"

    db = SessionLocal()
    try:
        # Find next position (max position of active + 1, or use displaced slot)
        active_count = db.execute(text(
            "SELECT COUNT(*) FROM amendator_featured_examples WHERE is_active = TRUE"
        )).scalar() or 0

        # If at cap, soft-deactivate oldest active
        displaced = None
        if active_count >= MAX_ACTIVE:
            row = db.execute(text(
                """
                SELECT id, title FROM amendator_featured_examples
                 WHERE is_active = TRUE
              ORDER BY added_at ASC
                 LIMIT 1
                """
            )).first()
            if row:
                db.execute(text(
                    "UPDATE amendator_featured_examples "
                    "SET is_active = FALSE, deactivated_at = NOW() WHERE id = :id"
                ), {"id": row[0]})
                displaced = row[1]

        # Determine new position (use 0..N order; new entry takes top)
        # Shift everyone else down, new one becomes position 0.
        db.execute(text(
            "UPDATE amendator_featured_examples SET position = position + 1 WHERE is_active = TRUE"
        ))

        # Insert; if URL collides (re-promotion), reactivate + reset position
        existing = db.execute(text(
            "SELECT id FROM amendator_featured_examples WHERE eurlex_url = :url"
        ), {"url": url}).first()
        if existing:
            db.execute(text(
                """
                UPDATE amendator_featured_examples
                   SET is_active = TRUE,
                       position = 0,
                       title = :title,
                       description = :desc,
                       source = :src,
                       celex = COALESCE(:celex, celex),
                       document_type = COALESCE(:dt, document_type),
                       added_at = NOW(),
                       deactivated_at = NULL
                 WHERE id = :id
                """
            ), {"id": existing[0], "title": title, "desc": description,
                "src": source, "celex": celex, "dt": document_type})
            db.commit()
            return True, f"reactivated existing entry: {title}" + (
                f" (displaced: {displaced})" if displaced else "")

        db.execute(text(
            """
            INSERT INTO amendator_featured_examples
                (celex, eurlex_url, title, description, source, position, is_active, added_at, document_type)
            VALUES (:celex, :url, :title, :desc, :src, 0, TRUE, NOW(), :dt)
            """
        ), {"celex": celex, "url": url, "title": title,
            "desc": description, "src": source, "dt": document_type})
        db.commit()
        return True, f"added: {title}" + (f" (displaced: {displaced})" if displaced else "")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Rotate amendator featured examples")
    parser.add_argument("--celex", required=False, help="CELEX or procedure ref (optional)")
    parser.add_argument("--url", required=True, help="Full EUR-Lex URL or intcom URL")
    parser.add_argument("--title", required=True, help="Short label shown to user")
    parser.add_argument("--description", required=False, help="One-line context")
    parser.add_argument("--source", default="news",
                        choices=["news", "manual", "skill", "carriage"],
                        help="Where the example came from")
    parser.add_argument("--document-type", required=False,
                        choices=sorted(AMENDABLE_TYPES),
                        help="Type of legal instrument. Required for the entry to surface in the UI.")
    parser.add_argument("--skip-verify", action="store_true",
                        help="Skip pre-flight parse verification (NOT recommended).")
    args = parser.parse_args()

    ok, msg = add_example(args.celex, args.url, args.title, args.description,
                          args.source, args.document_type,
                          skip_verify=args.skip_verify)
    prefix = "[OK]" if ok else "[ERROR]"
    print(f"{prefix} {msg}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
