#!/usr/bin/env python3.12
"""Fill what every stored TED notice already says: its currency, type, buyer level and lot values.

20 Oct 2026, from a partner session's read of /api/v2/funding/tenders:
  * the currency of 1,070 of 3,325 valued notices in a week was SEK, RON, CZK, PLN, NOK, DKK...
    stored as EUR (fetch_tenders.py read the parser's result under the wrong key);
  * form_type and notice_subtype were empty on 56,526 of 57,135 notices (never copied);
  * no buyer level, although every eForms XML names the buyer's legal type (BT-11);
  * 260 notices a week with no notice-level value list a value on every lot.

Everything is read from `xml_content` and `lots` INSIDE Postgres, by regular expression, in
chunks of ids: the XML never leaves the database (57,000 notices at ~59 kB would be 3.4 GB of
Supabase egress through the Python parser). The patterns pick what the parser picks (the
first NoticeTypeCode, the first ContractingParty's buyer-legal-type, the currencyID of the
first EstimatedOverallContractAmount); `--verify N` re-parses N random notices with the real
parser and compares.

Change signal: the currency and lot-value passes move `updated_at` (a value that was wrong or
missing is a change a partner must receive). The type and buyer passes do not: they add facts
the notice always had, under `brubru.keep_change_signal` (migration 303's scoped switch).

    python3.12 scripts/backfill_tender_notice_fields.py                  # dry run: counts per pass
    python3.12 scripts/backfill_tender_notice_fields.py --apply
    python3.12 scripts/backfill_tender_notice_fields.py --verify 200     # parser vs database, read-only
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import random
import re
import sys
import time
from datetime import datetime, timezone

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import psycopg2  # noqa: E402

from services.tenders.eforms_parser import BUYER_LEVELS, EFormsParser  # noqa: E402

CHUNK = 2000
PAUSE_S = 0.3

_NOTICE_TYPE = r"<cbc:NoticeTypeCode[^>]*>([^<]+)<"
_BUYER_LEGAL = r'<cbc:PartyTypeCode listName="buyer-legal-type"[^>]*>([^<]+)<'
_CURRENCY = r'<cbc:EstimatedOverallContractAmount currencyID="([A-Z]{3})"'
_NOTICE_ID = r'<cbc:ID schemeName="notice-id">([^<]+)<'


def _db_url() -> str:
    if os.environ.get("DATABASE_URL"):
        url = os.environ["DATABASE_URL"]
    else:
        env = (BACKEND / ".env").read_text()
        m = re.search(r"^DATABASE_URL=(.*)$", env, re.M)
        if not m:
            raise SystemExit("[ERROR] DATABASE_URL missing")
        url = m.group(1).strip()
    return url.replace("postgresql+psycopg2://", "postgresql://")


def _values_sql(pairs) -> str:
    rows = ", ".join(f"('{a}', '{b}')" for a, b in sorted(pairs))
    return f"(VALUES {rows})"


def _form_types() -> dict:
    sdk = BACKEND / "knowledge_base" / "tenders" / "eforms" / "notice-types.json"
    subs = json.loads(sdk.read_text(encoding="utf-8"))["noticeSubTypes"]
    return {s["type"]: s["formType"] for s in subs if s.get("type") and s.get("formType")}


def _passes():
    form_map = _values_sql(_form_types().items())
    level_map = _values_sql(BUYER_LEVELS.items())
    # (name, moves the change signal, UPDATE for ids in [%(a)s, %(b)s], dry-run COUNT)
    currency_src = f"""SELECT id, substring(xml_content from '{_CURRENCY}') AS cur, estimated_value_currency AS old
                         FROM tenders WHERE id BETWEEN %(a)s AND %(b)s
                          AND estimated_value IS NOT NULL AND xml_content IS NOT NULL"""
    labels_src = f"""SELECT x.id, x.nt, coalesce(m.ft, t.form_type) AS ft, x.blt, lv.lvl, x.nid
                       FROM (SELECT id, substring(xml_content from '{_NOTICE_TYPE}') AS nt,
                                    substring(xml_content from '{_NOTICE_ID}') AS nid,
                                    lower(substring(xml_content from '{_BUYER_LEGAL}')) AS blt
                               FROM tenders WHERE id BETWEEN %(a)s AND %(b)s AND xml_content IS NOT NULL) x
                       JOIN tenders t ON t.id = x.id
                       LEFT JOIN {form_map} AS m(nt, ft) ON m.nt = x.nt
                       LEFT JOIN {level_map} AS lv(code, lvl) ON lv.code = x.blt
                      WHERE x.nt IS NOT NULL
                        AND (t.notice_subtype IS DISTINCT FROM x.nt OR t.form_type IS DISTINCT FROM coalesce(m.ft, t.form_type)
                             OR t.buyer_legal_type IS DISTINCT FROM x.blt OR t.buyer_level IS DISTINCT FROM lv.lvl
                             OR (x.nid IS NOT NULL AND t.notice_id IS DISTINCT FROM x.nid))"""
    lots_src = """SELECT id, sum((l->>'estimated_value')::float8) AS total, min(coalesce(l->>'currency', 'EUR')) AS cur
                    FROM tenders, jsonb_array_elements(lots) AS l
                   WHERE id BETWEEN %(a)s AND %(b)s AND estimated_value IS NULL AND jsonb_typeof(lots) = 'array'
                   GROUP BY id
                  HAVING count(*) > 0 AND count(l->>'estimated_value') = count(*)
                     AND count(DISTINCT coalesce(l->>'currency', 'EUR')) = 1"""
    return [
        ("currency", True,
         f"""UPDATE tenders t SET estimated_value_currency = s.cur FROM ({currency_src}) s
              WHERE t.id = s.id AND s.cur IS NOT NULL AND s.old IS DISTINCT FROM s.cur""",
         f"SELECT count(*) FROM ({currency_src}) s WHERE s.cur IS NOT NULL AND s.old IS DISTINCT FROM s.cur"),
        ("labels", False,
         f"""UPDATE tenders t SET notice_subtype = s.nt, form_type = s.ft, buyer_legal_type = s.blt, buyer_level = s.lvl,
                                     notice_id = coalesce(s.nid, t.notice_id)
               FROM ({labels_src}) s WHERE t.id = s.id""",
         f"SELECT count(*) FROM ({labels_src}) s"),
        ("lot_values", True,
         f"""UPDATE tenders t SET estimated_value = s.total, estimated_value_currency = s.cur
               FROM ({lots_src}) s WHERE t.id = s.id""",
         f"SELECT count(*) FROM ({lots_src}) s"),
    ]


def _backup(cur) -> pathlib.Path:
    out = BACKEND / "data" / "backups" / f"tenders_notice_fields_before_{datetime.now(timezone.utc):%Y%m%d_%H%M}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    cur.execute("SELECT id, form_type, notice_subtype, estimated_value, estimated_value_currency, updated_at "
                "FROM tenders ORDER BY id")
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "form_type", "notice_subtype", "estimated_value", "estimated_value_currency", "updated_at"])
        w.writerows(cur.fetchall())
    return out


def run(apply: bool) -> int:
    conn = psycopg2.connect(_db_url(), connect_timeout=15)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SELECT min(id), max(id) FROM tenders")
    lo, hi = cur.fetchone()
    conn.commit()
    if lo is None:
        print("[INFO] no tenders")
        return 0
    if apply:
        print(f"[BACKUP] {_backup(cur)}")
        conn.commit()
    totals = {name: 0 for name, *_ in _passes()}
    for a in range(lo, hi + 1, CHUNK):
        b = a + CHUNK - 1
        for name, moves_signal, update_sql, count_sql in _passes():
            if apply:
                if not moves_signal:
                    cur.execute("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)")
                cur.execute(update_sql, {"a": a, "b": b})
                totals[name] += cur.rowcount
            else:
                cur.execute(count_sql, {"a": a, "b": b})
                totals[name] += cur.fetchone()[0]
            conn.commit()   # one chunk of one pass per transaction
        print(f"  ids {a}-{b}: " + ", ".join(f"{k}={v}" for k, v in totals.items()), flush=True)
        time.sleep(PAUSE_S)
    conn.close()
    print(("[APPLIED] " if apply else "[DRY-RUN] would change ") + ", ".join(f"{k}={v}" for k, v in totals.items()))
    return 0


def verify(n: int) -> int:
    """Re-parse n random eForms notices with the real parser; compare with the stored columns."""
    conn = psycopg2.connect(_db_url(), connect_timeout=15)
    cur = conn.cursor()
    cur.execute("SELECT id FROM tenders WHERE xml_content LIKE '%%NoticeTypeCode%%' AND publication_date > now() - interval '120 days'")
    ids = random.sample([r[0] for r in cur.fetchall()], k=n)
    cur.execute("SELECT id, publication_number, xml_content, form_type, notice_subtype, buyer_legal_type, buyer_level, "
                "estimated_value, estimated_value_currency FROM tenders WHERE id = ANY(%s)", (ids,))
    parser, bad = EFormsParser(), []
    for (tid, pub, xml, ft, nst, blt, lvl, val, curcy) in cur.fetchall():
        d = parser.parse_to_tender_dict(xml, pub)
        want = {"form_type": d["form_type"], "notice_subtype": d["notice_subtype"],
                "buyer_legal_type": (d["buyer_legal_type"] or None) and d["buyer_legal_type"].lower(),
                "buyer_level": d["buyer_level"]}
        got = {"form_type": ft, "notice_subtype": nst, "buyer_legal_type": blt, "buyer_level": lvl}
        if d.get("estimated_value") is not None:
            want["estimated_value_currency"], got["estimated_value_currency"] = d["estimated_value_currency"], curcy
            want["estimated_value"], got["estimated_value"] = round(d["estimated_value"], 2), val and round(val, 2)
        diff = {k: (got[k], want[k]) for k in want if got[k] != want[k]}
        if diff:
            bad.append((pub, diff))
    conn.close()
    print(f"[VERIFY] {n - len(bad)} of {n} notices match the parser")
    for pub, diff in bad[:15]:
        print(f"   {pub}: {diff}")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--verify", type=int, default=0, help="Compare N random notices with the parser (read-only)")
    a = ap.parse_args()
    sys.exit(verify(a.verify) if a.verify else run(a.apply))
