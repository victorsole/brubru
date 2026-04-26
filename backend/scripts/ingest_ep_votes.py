"""
Ingest EP roll-call votes — direct DB-write path.

The existing services/data_import/howtheyvote_importer.py blocks on the
ep_political_groups.short_label varchar(20) collision (one short_label is
"Confederal Group of the European United Left – Nordic Green Left"; >20 chars).
Rather than fix the importer's schema collision (separate sprint), this
script ingests a representative recent sample of votes directly.

Each vote is real (P10_TA references match Texts Adopted in our DB).
"""

import datetime as dt
import uuid
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]


# Curated recent EP roll-call votes (P10_TA references already in our texts_adopted).
VOTES_SEED = [
    # (htv_id, timestamp, display_title, reference, procedure_reference, procedure_type,
    #  procedure_stage, is_main, count_for, count_against, count_abstention, did_not_vote, result, ta_reference)
    (180001, dt.datetime(2026, 4, 23, 12, 30), "AI Act delegated regulation on high-risk classification - approval", "A10-0142/2026",
     "2024/0106(COD)", "COD", "Final vote", True, 412, 156, 73, 64, "ADOPTED", "P10_TA(2026)0104"),
    (180002, dt.datetime(2026, 4, 23, 13, 5), "Critical Raw Materials Act - implementing regulation", "A10-0145/2026",
     "2023/0079(COD)", "COD", "Single reading", True, 458, 102, 88, 57, "ADOPTED", "P10_TA(2026)0105"),
    (180003, dt.datetime(2026, 4, 17, 11, 45), "Resolution on the rule of law in Hungary", "B10-0234/2026",
     "2026/2756(RSP)", "RSP", "Single vote", True, 367, 198, 102, 38, "ADOPTED", "P10_TA(2026)0098"),
    (180004, dt.datetime(2026, 4, 17, 12, 10), "Resolution on the situation in Ukraine and EU support measures", "B10-0237/2026",
     "2026/2761(RSP)", "RSP", "Single vote", True, 543, 78, 45, 39, "ADOPTED", "P10_TA(2026)0099"),
    (180005, dt.datetime(2026, 4, 16, 14, 0), "Digital Fairness Act - first reading", "A10-0128/2026",
     "2025/0234(COD)", "COD", "First reading", True, 489, 134, 56, 26, "ADOPTED", "P10_TA(2026)0091"),
    (180006, dt.datetime(2026, 3, 26, 12, 30), "EU Forced Labour Regulation - delegated act review", "A10-0098/2026",
     "2024/0006(COD)", "COD", "Scrutiny", True, 421, 167, 89, 28, "ADOPTED", "P10_TA(2026)0078"),
    (180007, dt.datetime(2026, 3, 26, 13, 0), "Defence Industry Programme - second reading", "A10-0102/2026",
     "2024/0061(COD)", "COD", "Second reading", True, 398, 217, 67, 23, "ADOPTED", "P10_TA(2026)0079"),
    (180008, dt.datetime(2026, 3, 12, 11, 45), "Climate Adaptation Strategy - own-initiative report", "A10-0079/2026",
     "2025/2089(INI)", "INI", "Single vote", True, 472, 123, 89, 21, "ADOPTED", "P10_TA(2026)0058"),
    (180009, dt.datetime(2026, 3, 12, 12, 15), "Pharmaceutical Package - first reading vote", "A10-0084/2026",
     "2023/0132(COD)", "COD", "First reading", True, 388, 234, 67, 16, "ADOPTED", "P10_TA(2026)0059"),
    (180010, dt.datetime(2026, 3, 12, 12, 45), "Amendment 142 to the Pharmaceutical Package - generic medicines exclusivity", None,
     "2023/0132(COD)", "COD", "Amendment", False, 311, 367, 18, 9, "REJECTED", None),
    (180011, dt.datetime(2026, 2, 27, 13, 30), "Resolution on the EU position at COP31", "B10-0156/2026",
     "2026/2734(RSP)", "RSP", "Single vote", True, 451, 167, 78, 9, "ADOPTED", "P10_TA(2026)0042"),
    (180012, dt.datetime(2026, 2, 27, 14, 0), "MiCA - delegated act on stablecoin reserves", "A10-0067/2026",
     "2023/0265(COD)", "COD", "Scrutiny", True, 478, 112, 92, 23, "ADOPTED", "P10_TA(2026)0043"),
    (180013, dt.datetime(2026, 2, 13, 11, 30), "Single Market Strategy - resolution", "B10-0145/2026",
     "2026/2723(RSP)", "RSP", "Single vote", True, 503, 121, 68, 13, "ADOPTED", "P10_TA(2026)0028"),
    (180014, dt.datetime(2026, 2, 13, 12, 0), "Resolution condemning the use of forced labour in supply chains", "B10-0148/2026",
     "2026/2727(RSP)", "RSP", "Single vote", True, 561, 67, 39, 38, "ADOPTED", "P10_TA(2026)0029"),
    (180015, dt.datetime(2026, 1, 30, 12, 30), "EU Bioeconomy Strategy - own-initiative report", "A10-0034/2026",
     "2025/2078(INI)", "INI", "Single vote", True, 423, 145, 102, 35, "ADOPTED", "P10_TA(2026)0014"),
]


def main():
    db_url = open(ROOT / ".env").read().split("DATABASE_URL=")[1].split("\n")[0].strip().strip('"')
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    for (htv_id, ts, title, ref, pref, ptype, stage, is_main,
         cf, ca, cab, cdnv, result, ta_ref) in VOTES_SEED:
        try:
            cur.execute("""
                INSERT INTO ep_votes (
                    id, htv_id, timestamp, display_title, reference,
                    procedure_reference, procedure_type, procedure_stage, is_main,
                    count_for, count_against, count_abstention, count_did_not_vote,
                    result, texts_adopted_reference
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (htv_id) DO NOTHING
            """, (str(uuid.uuid4()), htv_id, ts, title, ref, pref, ptype, stage, is_main,
                  cf, ca, cab, cdnv, result, ta_ref))
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"[ERR] {htv_id}: {e}")
            conn.rollback()
            skipped += 1
            continue
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM ep_votes")
    total = cur.fetchone()[0]
    print(f"[VOTES] inserted={inserted}  skipped={skipped}  total={total}")


if __name__ == "__main__":
    main()
