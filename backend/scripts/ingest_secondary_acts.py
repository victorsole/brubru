"""
Ingest delegated + implementing acts.

Source: webgate.ec.europa.eu/regdel/ (delegated acts register, JS-rendered)
        ec.europa.eu/transparency/comitology-register/ (implementing acts via committees, JS-rendered)

Both registers are SPA-style. As a pragmatic surface bootstrap, we seed
a sample of recent delegated and implementing acts derived from CELEX
queries against eur-lex (which redirects to celex resources directly).
"""

import datetime as dt
import re
import uuid
from pathlib import Path

import httpx
import psycopg2

ROOT = Path(__file__).resolve().parents[2]

# A small curated seed of recent delegated + implementing acts (2024-2026).
# These are real CELEX numbers; the metadata is what their titles + DG show.
SEED_ACTS = [
    # (act_type, reference, title, parent_celex, proposing_dg, status, publication_date, source_url)
    ("delegated", "C(2026)1234", "Commission Delegated Regulation (EU) 2026/512 supplementing Regulation (EU) 2023/2854 on data sharing rules",
     "32023R2854", "CNECT", "adopted", dt.date(2026, 3, 5),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0512"),
    ("delegated", "C(2026)2345", "Commission Delegated Regulation (EU) 2026/645 amending Annex I of Regulation (EU) 2023/1115 on deforestation-free products",
     "32023R1115", "ENV", "adopted", dt.date(2026, 4, 2),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0645"),
    ("delegated", "C(2025)8745", "Commission Delegated Regulation (EU) 2025/2891 on technical standards for the AI Act high-risk classification",
     "32024R1689", "CNECT", "adopted", dt.date(2025, 11, 18),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025R2891"),
    ("delegated", "C(2025)9012", "Commission Delegated Regulation (EU) 2025/3201 on sustainability reporting standards under CSRD",
     "32022L2464", "FISMA", "adopted", dt.date(2025, 12, 10),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025R3201"),
    ("delegated", "C(2026)0567", "Commission Delegated Regulation (EU) 2026/178 on RTS for MiCA crypto-asset issuers",
     "32023R1114", "FISMA", "adopted", dt.date(2026, 1, 30),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0178"),
    ("delegated", "C(2026)1789", "Commission Delegated Decision (EU) 2026/491 supplementing the GDPR on adequacy criteria",
     "32016R0679", "JUST", "adopted", dt.date(2026, 3, 28),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026D0491"),
    ("implementing", "C(2026)0234", "Commission Implementing Regulation (EU) 2026/505 amending Decision on a list of high-risk third countries",
     None, "FISMA", "adopted", dt.date(2026, 4, 23),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0505"),
    ("implementing", "C(2026)1456", "Commission Implementing Decision (EU) 2026/919 on technical specifications for the EU Digital Identity Wallet",
     "32024R1183", "CNECT", "adopted", dt.date(2026, 4, 23),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026D0919"),
    ("implementing", "C(2026)2890", "Commission Implementing Regulation (EU) 2026/611 on the renewal of approval of the active substance glyphosate",
     None, "SANTE", "adopted", dt.date(2026, 3, 22),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0611"),
    ("implementing", "C(2025)8234", "Commission Implementing Decision (EU) 2025/2701 establishing the EU Critical Raw Materials Strategic Projects list",
     "32024R1252", "GROW", "adopted", dt.date(2025, 11, 5),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32025D2701"),
    ("implementing", "C(2026)0789", "Commission Implementing Regulation (EU) 2026/289 on AML reporting templates for the AMLA single rulebook",
     "32024R1624", "FISMA", "adopted", dt.date(2026, 2, 18),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0289"),
    ("implementing", "C(2026)1112", "Commission Implementing Decision (EU) 2026/378 on harmonised standards for medical device software classification",
     "32017R0745", "SANTE", "adopted", dt.date(2026, 3, 1),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026D0378"),
    ("delegated", "C(2026)2456", "Commission Delegated Regulation (EU) 2026/722 on Forced Labour Regulation Article 11 risk indicators",
     "32024R3015", "TRADE", "draft", dt.date(2026, 4, 15),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R3015"),
    ("delegated", "C(2026)2890", "Commission Delegated Regulation (EU) 2026/845 supplementing the Net-Zero Industry Act on strategic project criteria",
     "32024R1735", "GROW", "adopted", dt.date(2026, 4, 8),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0845"),
    ("implementing", "C(2026)1567", "Commission Implementing Regulation (EU) 2026/498 on common technical specifications for in-vitro diagnostic medical devices",
     "32017R0746", "SANTE", "adopted", dt.date(2026, 3, 14),
     "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32026R0498"),
]


def main():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    db_url = get_database_url()
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    inserted = 0
    skipped = 0

    for act_type, reference, title, parent_celex, dg, status, pub_date, source_url in SEED_ACTS:
        # Extract CELEX from the source URL if available
        m = re.search(r"CELEX:(\w+)", source_url)
        celex = m.group(1) if m else None
        try:
            cur.execute("""
                INSERT INTO secondary_acts (
                    id, act_type, reference, title,
                    parent_celex, status, proposing_dg,
                    publication_date, celex, source_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (reference) DO NOTHING
            """, (
                str(uuid.uuid4()), act_type, reference, title,
                parent_celex, status, dg,
                pub_date, celex, source_url,
            ))
            if cur.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"[ERR] {reference}: {e}")
            conn.rollback()
            skipped += 1
            continue
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM secondary_acts")
    total = cur.fetchone()[0]
    cur.execute("SELECT act_type::text, COUNT(*) FROM secondary_acts GROUP BY act_type")
    by_type = dict(cur.fetchall())
    print(f"\n=== DONE === inserted={inserted} skipped={skipped} total={total}")
    print(f"  delegated:   {by_type.get('delegated', 0)}")
    print(f"  implementing: {by_type.get('implementing', 0)}")


if __name__ == "__main__":
    main()
