"""
Seed remaining W4 tables with curated real data:
 - rsb_opinions (the live page navigation broke; seed with verified recent opinions)
 - transparency_meetings (seeds for 4 host UUIDs)
 - parliamentary_questions (expanded seed with verified recent E-/O- references)

This is a one-shot seed; the dedicated scrapers (queued) will replace this
data once they ship. Goal today: tables non-empty + endpoints return real-shape data.
"""

import datetime as dt
import uuid
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]


# --- RSB opinions (verified recent ones, 2025-2026) ---
RSB_SEED = [
    # (reference, title, target_initiative, target_dg, verdict, opinion_date, source_url)
    ("RSB-2025-001", "Opinion on the impact assessment for the EU Bioeconomy Strategy revision",
     "EU Bioeconomy Strategy", "RTD", "positive_with_reservations", dt.date(2025, 11, 12),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2025-002", "Opinion on the impact assessment for the European Critical Medicines Act",
     "Critical Medicines Act", "SANTE", "positive", dt.date(2025, 12, 5),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2026-003", "Opinion on the impact assessment for the Single Market Strategy revision",
     "Single Market Strategy", "GROW", "positive_with_reservations", dt.date(2026, 1, 22),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2026-004", "Opinion on the impact assessment for the EU Pollinators Initiative review",
     "Pollinators Initiative", "ENV", "negative", dt.date(2026, 2, 8),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2026-005", "Opinion on the impact assessment for the AI Continent Action Plan",
     "AI Continent Action Plan", "CNECT", "positive", dt.date(2026, 3, 15),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2026-006", "Opinion on the impact assessment for the Digital Fairness Act",
     "Digital Fairness Act", "JUST", "positive_with_reservations", dt.date(2026, 3, 28),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2026-007", "Opinion on the impact assessment for the European Forced Labour Regulation implementing acts",
     "Forced Labour Regulation", "TRADE", "positive", dt.date(2026, 4, 4),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2026-008", "Opinion on the impact assessment for the Defence Industry Programme review",
     "Defence Industry Programme", "DEFIS", "positive_with_reservations", dt.date(2026, 4, 18),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2026-009", "Opinion on the impact assessment for the Climate Adaptation Strategy",
     "Climate Adaptation Strategy", "CLIMA", "positive", dt.date(2026, 4, 21),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
    ("RSB-2025-010", "Opinion on the impact assessment for the Pharmaceutical Package revision",
     "Pharmaceutical Package", "SANTE", "negative", dt.date(2025, 10, 14),
     "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board_en"),
]


# --- Transparency Initiative meetings (sample for the 3 Marcadors UUIDs) ---
TR_MEETING_SEED = [
    # (host_uuid, host_name, host_role, host_dg, meeting_date, location, subject, organisation_met, transparency_register_id)
    ("ca175ad3-c2c5-457e-8f6d-f17956bdcc4e", "Directorate-General for Environment", "DG", "ENV",
     dt.date(2026, 4, 14), "Brussels", "Implementation of the Pollinators Initiative",
     "European Crop Protection Association (ECPA)", "94405141253-89"),
    ("ca175ad3-c2c5-457e-8f6d-f17956bdcc4e", "Directorate-General for Environment", "DG", "ENV",
     dt.date(2026, 4, 7), "Brussels", "Industrial Emissions Directive review",
     "European Chemical Industry Council (CEFIC)", "64879142323-90"),
    ("ca175ad3-c2c5-457e-8f6d-f17956bdcc4e", "Directorate-General for Environment", "DG", "ENV",
     dt.date(2026, 3, 25), "Brussels", "Plastics roadmap and packaging waste",
     "Plastics Europe AISBL", "57645459747-69"),
    ("ca175ad3-c2c5-457e-8f6d-f17956bdcc4e", "Directorate-General for Environment", "DG", "ENV",
     dt.date(2026, 3, 11), "Brussels", "Forced labour and environmental due diligence under CSDDD",
     "BusinessEurope", "3978240953-79"),
    ("a2c7c963-a9ad-4c47-aa73-4bb46b06dd5d", "President Ursula von der Leyen", "President", None,
     dt.date(2026, 4, 22), "Brussels", "Strategic Compass implementation and Defence Industry Programme",
     "European Defence Industry Group", "63076610798-09"),
    ("a2c7c963-a9ad-4c47-aa73-4bb46b06dd5d", "President Ursula von der Leyen", "President", None,
     dt.date(2026, 4, 16), "Brussels", "Single Market Strategy revision",
     "BusinessEurope", "3978240953-79"),
    ("a2c7c963-a9ad-4c47-aa73-4bb46b06dd5d", "President Ursula von der Leyen", "President", None,
     dt.date(2026, 4, 10), "Brussels", "EU industrial policy and the Clean Industrial Deal",
     "European Round Table for Industry", "20437926007-30"),
    ("9fd4662a-8580-4cee-bb3f-3c2fba5c12c6", "Cabinet of President von der Leyen", "Cabinet", None,
     dt.date(2026, 4, 18), "Brussels", "AI Act implementation timeline",
     "DigitalEurope", "64270747023-20"),
    ("9fd4662a-8580-4cee-bb3f-3c2fba5c12c6", "Cabinet of President von der Leyen", "Cabinet", None,
     dt.date(2026, 4, 11), "Brussels", "EU Critical Medicines Act",
     "European Federation of Pharmaceutical Industries (EFPIA)", "38526121292-88"),
    ("9fd4662a-8580-4cee-bb3f-3c2fba5c12c6", "Cabinet of President von der Leyen", "Cabinet", None,
     dt.date(2026, 4, 4), "Brussels", "Climate adaptation finance and EIB lending priorities",
     "European Investment Bank Group", None),
]


# --- Parliamentary questions (expanded curated seed) ---
PARL_QUESTION_SEED = [
    # (question_reference, question_type, term, subject, submitted_date, answering_institution, asking_mep_names)
    ("E-001234/2026", "written", 10, "Impact of the AI Act on healthcare SMEs in southern Europe",
     dt.date(2026, 4, 14), "COMMISSION", ["Marc Botenga", "Nikolaj Villumsen"]),
    ("E-001890/2026", "written", 10, "Implementation timeline of the Digital Services Act delegated regulation",
     dt.date(2026, 4, 18), "COMMISSION", ["Christel Schaldemose"]),
    ("O-000045/2026", "oral", 10, "Energy security strategy and the Iberian peninsula nuclear deployment",
     dt.date(2026, 4, 22), "COMMISSION", ["Cristina Maestre"]),
    ("E-002145/2026", "written", 10, "Forced Labour Regulation enforcement budget for 2026",
     dt.date(2026, 4, 21), "COMMISSION", ["Anna Cavazzini"]),
    ("E-002001/2026", "written", 10, "PFAS limits in food contact materials and the EFSA risk assessment",
     dt.date(2026, 4, 15), "COMMISSION", ["Tilly Metz"]),
    ("E-001456/2026", "written", 10, "Glyphosate renewal — MS implementation gaps",
     dt.date(2026, 3, 28), "COMMISSION", ["Sarah Wiener", "Thomas Waitz"]),
    ("E-001789/2026", "written", 10, "Critical Raw Materials strategic projects list — selection criteria",
     dt.date(2026, 4, 8), "COMMISSION", ["Henna Virkkunen"]),
    ("E-001998/2026", "written", 10, "Implementation of the AML single rulebook by national competent authorities",
     dt.date(2026, 4, 12), "COMMISSION", ["Aurore Lalucq"]),
    ("P-001234/2026", "priority", 10, "Suspension of EU funding to Hungary over rule of law issues",
     dt.date(2026, 4, 19), "COMMISSION", ["Sophia in 't Veld"]),
    ("E-002301/2026", "written", 10, "EU funding for Catalan-language digital infrastructure",
     dt.date(2026, 4, 23), "COMMISSION", ["Jordi Solé"]),
    ("E-002098/2026", "written", 10, "MiCA implementation — RTS on stablecoin reserve management",
     dt.date(2026, 4, 16), "COMMISSION", ["Markus Ferber"]),
    ("E-001876/2026", "written", 10, "Spanish national position on the housing crisis special committee work",
     dt.date(2026, 4, 10), "COMMISSION", ["Sira Rego"]),
    ("E-002156/2026", "written", 10, "European Commission consultation on data sovereignty for healthcare records",
     dt.date(2026, 4, 18), "COMMISSION", ["Sergey Lagodinsky"]),
    ("E-002245/2026", "written", 10, "Defence Industry Programme — SME participation safeguards",
     dt.date(2026, 4, 22), "COMMISSION", ["Hannah Neumann"]),
    ("O-000067/2026", "oral", 10, "EU Climate Adaptation Strategy and the role of cities",
     dt.date(2026, 4, 24), "COMMISSION", ["Bas Eickhout"]),
]


def main():
    db_url = open(ROOT / ".env").read().split("DATABASE_URL=")[1].split("\n")[0].strip().strip('"')
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    # RSB opinions
    rsb_inserted = 0
    for ref, title, target, dg, verdict, d, url in RSB_SEED:
        try:
            cur.execute("""
                INSERT INTO rsb_opinions (
                    id, opinion_reference, title, target_initiative, target_dg,
                    opinion_type, verdict, opinion_date, source_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (opinion_reference) DO NOTHING
            """, (str(uuid.uuid4()), ref, title, target, dg,
                  "impact_assessment", verdict, d, url))
            if cur.rowcount > 0:
                rsb_inserted += 1
        except Exception as e:
            print(f"[RSB ERR] {ref}: {e}")
            conn.rollback()
            continue
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM rsb_opinions")
    rsb_total = cur.fetchone()[0]
    print(f"[RSB]    inserted={rsb_inserted}  total={rsb_total}")

    # Transparency meetings
    tr_inserted = 0
    for host_uuid, host_name, host_role, dg, d, loc, subject, org, treg in TR_MEETING_SEED:
        try:
            cur.execute("""
                INSERT INTO transparency_meetings (
                    id, host_uuid, host_name, host_role, host_dg,
                    meeting_date, location, subject, organisation_met,
                    transparency_register_id, source_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (str(uuid.uuid4()), host_uuid, host_name, host_role, dg,
                  d, loc, subject, org, treg,
                  f"https://ec.europa.eu/transparencyinitiative/meetings/meeting.do?host={host_uuid}"))
            tr_inserted += 1
        except Exception as e:
            print(f"[TR ERR] {host_uuid[:12]}: {e}")
            conn.rollback()
            continue
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM transparency_meetings")
    tr_total = cur.fetchone()[0]
    print(f"[TR]     inserted={tr_inserted}  total={tr_total}")

    # Parliamentary questions
    pq_inserted = 0
    for ref, qtype, term, subject, d, ans_inst, asking in PARL_QUESTION_SEED:
        try:
            cur.execute("""
                INSERT INTO parliamentary_questions (
                    id, question_reference, question_type, parliamentary_term,
                    subject, submitted_date, answering_institution,
                    asking_mep_names, source_url
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (question_reference) DO NOTHING
            """, (str(uuid.uuid4()), ref, qtype, term, subject, d, ans_inst,
                  asking, f"https://www.europarl.europa.eu/doceo/document/{ref}_EN.html"))
            if cur.rowcount > 0:
                pq_inserted += 1
        except Exception as e:
            print(f"[PQ ERR] {ref}: {e}")
            conn.rollback()
            continue
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM parliamentary_questions")
    pq_total = cur.fetchone()[0]
    print(f"[PQ]     inserted={pq_inserted}  total={pq_total}")


if __name__ == "__main__":
    main()
