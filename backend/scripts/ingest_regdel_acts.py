"""
Ingest delegated + implementing acts from the Commission Register of
Delegated Acts (RegDel) Excel export.

Source URLs (no auth, no CSRF):
  https://webgate.ec.europa.eu/regdel/web/delegatedActs/excel?lang=en&filter=...
  https://webgate.ec.europa.eu/regdel/web/implementingActs/excel?lang=en&filter=...

Each row carries: Complete title, CCode (e.g. C(2026)876), Celex number,
Policy area, Leading Service Commission (DG), status, phase, planned
adoption date, basic legislative act (parent law title), empowerment
article.

This wipes the 7 fictitious seed rows that were sitting in secondary_acts
and replaces them with real data.

Run:
    python3.12 backend/scripts/ingest_regdel_acts.py            # dry-run, fetch only
    python3.12 backend/scripts/ingest_regdel_acts.py --apply
    python3.12 backend/scripts/ingest_regdel_acts.py --apply --type delegated
    python3.12 backend/scripts/ingest_regdel_acts.py --apply --type implementing
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0) Chrome/126.0.0.0"

REGDEL_BASE = "https://webgate.ec.europa.eu/regdel/web"
EXPORT_FILTER = urllib.parse.quote('{"rowsPerPage":6,"firstRowOffset":0,"language":"en"}')


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_excel(act_type: str) -> bytes:
    """Download the Excel export. act_type ∈ {'delegated', 'implementing'}."""
    path = "delegatedActs" if act_type == "delegated" else "implementingActs"
    url = f"{REGDEL_BASE}/{path}/excel?lang=en&filter={EXPORT_FILTER}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


# Regex helpers for parsing the "Basic legislative act" free-text column
# into a CELEX number.
_BASIC_REGULATION_RE = re.compile(r"Regulation\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)
_BASIC_REGULATION_LEGACY_RE = re.compile(r"Regulation\s*\(EU\)(?:\s*No)?\s*(\d{1,4})/(\d{4})", re.IGNORECASE)
_BASIC_DIRECTIVE_RE = re.compile(r"Directive\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)
_BASIC_DIRECTIVE_OLD_RE = re.compile(r"Directive\s*(\d{4})/(\d{1,3})/(?:EU|EC|EEC)", re.IGNORECASE)
_BASIC_DECISION_RE = re.compile(r"Decision\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)


def derive_parent_celex(basic_text: Any) -> Optional[str]:
    """Extract a CELEX from the free-text 'Basic legislative act' column."""
    if not isinstance(basic_text, str) or not basic_text.strip():
        return None
    m = _BASIC_REGULATION_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}R{int(m.group(2)):04d}"
    m = _BASIC_DIRECTIVE_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}L{int(m.group(2)):04d}"
    m = _BASIC_DIRECTIVE_OLD_RE.search(basic_text)
    if m and 1950 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}L{int(m.group(2)):04d}"
    m = _BASIC_DECISION_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}D{int(m.group(2)):04d}"
    m = _BASIC_REGULATION_LEGACY_RE.search(basic_text)
    if m and 1950 <= int(m.group(2)) <= 2099 and "Regulation (EU)" in basic_text:
        # legacy "(EU) No N/YYYY" form
        return f"3{m.group(2)}R{int(m.group(1)):04d}"
    return None


_STATUS_MAP = {
    "Published": "adopted",
    "Adoption": "adopted",
    "Adopted": "adopted",
    "Draft": "draft",
    "Empowerment": "draft",
    "Withdrawn": "withdrawn",
}


def normalise_row(row: Dict[str, Any], act_type: str) -> Optional[Dict[str, Any]]:
    """Convert one Excel row into a secondary_acts record."""
    status_col = "Delegated act status" if act_type == "delegated" else "Implementing act status"
    title = row.get("Complete title")
    ccode = row.get("CCode")
    # pandas gives float NaN for empty cells; treat as missing
    if isinstance(title, float) and pd.isna(title):
        title = None
    if isinstance(ccode, float) and pd.isna(ccode):
        ccode = None
    title = title.strip() if isinstance(title, str) else None
    ccode = ccode.strip() if isinstance(ccode, str) else None
    if not title or not ccode or ccode.lower() == "nan":
        return None

    celex = row.get("Celex number")
    celex = celex.strip() if isinstance(celex, str) else None
    if celex == "" or celex is None or (isinstance(celex, float) and pd.isna(celex)):
        celex = None

    policy = row.get("Policy area")
    policy_areas = []
    if isinstance(policy, str) and policy.strip():
        policy_areas = [p.strip() for p in policy.split(",") if p.strip()]

    dg = row.get("Leading Service Commission")
    dg = dg.strip() if isinstance(dg, str) and dg.strip() else None

    raw_status = row.get(status_col)
    status = _STATUS_MAP.get(str(raw_status).strip(), "draft") if raw_status else "draft"

    parent_celex = derive_parent_celex(row.get("Basic legislative act"))

    # source_url is NOT NULL on the table. Prefer the EUR-Lex CELEX URL when
    # we have a CELEX. Otherwise fall back to the RegDel deep-link by CCode
    # (the public register is the authoritative source for draft / pending
    # acts that haven't yet received a CELEX).
    if celex:
        source_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    else:
        # RegDel uses the CCode without parens in its deep links.
        # Example: C(2026)876 → https://webgate.ec.europa.eu/regdel/#/{type}/{CCODE}
        slug_path = "delegatedActs" if act_type == "delegated" else "implementingActs"
        source_url = f"https://webgate.ec.europa.eu/regdel/#/{slug_path}?lang=en&search={urllib.parse.quote(str(ccode))}"

    return {
        "id": str(uuid.uuid4()),
        "act_type": act_type,
        "reference": str(ccode).strip(),
        "title": str(title).strip()[:1000],
        "parent_celex": parent_celex,
        "celex": celex,
        "status": status,
        "proposing_dg": dg,
        "source_url": source_url,
        "policy_areas": policy_areas,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--type",
        choices=("delegated", "implementing", "both"),
        default="both",
    )
    ap.add_argument("--limit", type=int, default=None, help="Truncate after N rows (debug)")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    targets = ("delegated", "implementing") if args.type == "both" else (args.type,)
    all_rows: List[Dict[str, Any]] = []

    for act_type in targets:
        print(f"[INFO] fetching RegDel {act_type} export...")
        bytes_ = fetch_excel(act_type)
        df = pd.read_excel(io.BytesIO(bytes_), engine="xlrd")
        print(f"  {len(df)} rows in Excel")
        for _, row in df.iterrows():
            rec = normalise_row(row.to_dict(), act_type)
            if rec:
                all_rows.append(rec)
        if args.limit:
            all_rows = all_rows[: args.limit]
            break

    print(f"[INFO] {len(all_rows)} records normalised (apply={args.apply})")

    if not args.apply:
        for r in all_rows[:5]:
            print(f"  {r['act_type']:13s} {r['reference']:14s} celex={(r['celex'] or '-'):12s} dg={(r['proposing_dg'] or '-'):8s} parent={(r['parent_celex'] or '-'):12s} status={r['status']:10s} policy={r['policy_areas'][:1]}")
        print("[NOTE] dry-run — pass --apply to write to DB")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    # Wipe the original 10 fictitious seed rows. These were inserted by an
    # earlier hand-curated dev fixture and never matched any real RegDel
    # entry — keeping them would mean the API returns wrong title↔CELEX
    # pairs (e.g. seed CELEX 32026R0178 was labelled "MiCA crypto-asset
    # RTS" but actually points at a regulation about eucalyptus tincture).
    SEED_REFS = (
        # delegated
        "C(2026)2456", "C(2026)2345", "C(2026)1789", "C(2026)1234",
        "C(2026)0567", "C(2025)9012", "C(2025)8745",
        # implementing
        "C(2026)0234", "C(2026)1456", "C(2026)2890",
    )
    cur.execute("DELETE FROM secondary_acts WHERE reference IN %s", (SEED_REFS,))
    print(f"  wiped {cur.rowcount} seed rows")

    inserted = updated = errors = 0
    for r in all_rows:
        try:
            cur.execute(
                """
                INSERT INTO secondary_acts
                  (id, act_type, reference, title, parent_celex, celex, status,
                   proposing_dg, source_url, policy_areas, scraped_at, first_seen, last_updated)
                VALUES
                  (%(id)s, %(act_type)s, %(reference)s, %(title)s, %(parent_celex)s,
                   %(celex)s, %(status)s, %(proposing_dg)s, %(source_url)s, %(policy_areas)s,
                   NOW(), NOW(), NOW())
                ON CONFLICT (reference) DO UPDATE SET
                  title = EXCLUDED.title,
                  parent_celex = EXCLUDED.parent_celex,
                  celex = EXCLUDED.celex,
                  status = EXCLUDED.status,
                  proposing_dg = EXCLUDED.proposing_dg,
                  source_url = EXCLUDED.source_url,
                  policy_areas = EXCLUDED.policy_areas,
                  last_updated = NOW()
                """,
                r,
            )
            inserted += 1
        except Exception as exc:
            print(f"  [ERR] {r['reference']}: {exc}")
            conn.rollback()
            errors += 1
        if inserted % 200 == 0 and inserted > 0:
            conn.commit()
    conn.commit()
    conn.close()
    print(f"[DONE] upserted {inserted} errors={errors}")


if __name__ == "__main__":
    main()
