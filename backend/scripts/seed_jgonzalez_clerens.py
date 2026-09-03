"""
Seed Joan Gonzalez (CLERENS / BEPA) profile.

Updates the existing user (j.gonzalez@bepassociation.eu) with Clerens context,
attaches 7 priority legislative carriages to My Files, seeds 6 MEUB documents
under the canonical pattern (document_type='uploaded' with semantic type in
doc_metadata.original_document_type), points him at the acm-catalonia-style
private guide bundle (`joan-gonzalez-clerens`), and runs the Pydantic
round-trip validator before commit.

Pattern reference: memory/feedback_raw_insert_orm_defaults.md - especially
the addendum on `'uploaded' + doc_metadata.original_document_type`.

Usage:
    cd backend && python3.12 scripts/seed_jgonzalez_clerens.py            # dry-run
    cd backend && python3.12 scripts/seed_jgonzalez_clerens.py --apply    # write DB

Idempotent: re-runs skip rows that already exist for this user.
"""

from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import argparse
import json
import logging
import pathlib
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, f"{_REPO_ROOT}/backend")
sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv(f"{_REPO_ROOT}/.env")

from core.database import SessionLocal, engine

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


USER_EMAIL = "j.gonzalez@bepassociation.eu"
USER_FULL_NAME = "Joan Gonzalez"
USER_FIRST_NAME = "Joan"
USER_PREFERRED_NAME = "Joan"
USER_ORG = "CLERENS"
USER_ROLE_TITLE = "Senior Consultant (BEPA secretariat)"
USER_COUNTRY = "BE"
USER_LANGUAGE = "ca"
USER_TIMEZONE = "Europe/Brussels"
POLICY_INTERESTS = [
    "Batteries",
    "Critical Raw Materials",
    "Net-Zero Industry",
    "Clean Industrial Deal",
    "Energy Storage",
    "EU Funding",
]
PRIVATE_GUIDE_SLUG = "joan-gonzalez-clerens"

SUBSCRIPTION_TIER = "blue"
SUBSCRIPTION_EXPIRES_AT = datetime(2026, 6, 21, 23, 59, 59, tzinfo=timezone.utc)


CARRIAGE_SHORT_IDS = [
    "1f06a0e2",  # Proposal amending the EU Batteries Regulation + IED
    "db7a5e5e",  # European critical raw materials act (follow-up track)
    "f5fb51a6",  # Critical Raw Materials Centre
    "9cfd275d",  # Net-zero industry act (follow-up track)
    "fc5fac1e",  # AccelerateEU - Energy Union (COM(2026)0370)
    "2676a074",  # LIFE programme 2021-2027
    "fe2978e6",  # Clean Industrial Deal
]


APIFY_POSTS_FILE = pathlib.Path(
    f"{_REPO_ROOT}/data/apify/clerens_linkedin_posts_2026_05_21.json"
)


def build_apify_doc_content() -> tuple[str, dict]:
    """Read the Apify scrape and turn it into one ingestible markdown blob."""
    if not APIFY_POSTS_FILE.exists():
        return ("[Apify scrape file missing - re-run the Apify experiment to populate]", {})
    posts = json.loads(APIFY_POSTS_FILE.read_text())
    lines = [
        "# CLERENS LinkedIn feed - 50-post snapshot (21 May 2026)",
        "",
        f"Captured via Apify actor `freshdata/linkedin-company-post-scraper` on 21 May 2026 from https://www.linkedin.com/company/clerens/. "
        f"{len(posts)} posts. Each entry below is the verbatim post text with the publish date and engagement counters.",
        "",
        "---",
        "",
    ]
    for p in posts:
        date = p.get("posted") or "?"
        likes = p.get("num_likes", 0)
        comments = p.get("num_comments", 0)
        reposts = p.get("num_reposts", 0)
        url = p.get("url") or ""
        text_ = p.get("text") or ""
        lines.append(f"## {date}  ({likes} likes / {comments} comments / {reposts} reposts)")
        lines.append("")
        lines.append(text_.strip())
        if url:
            lines.append("")
            lines.append(f"Source: {url}")
        lines.append("")
        lines.append("---")
        lines.append("")
    content = "\n".join(lines)
    meta = {
        "source": "apify",
        "actor": "freshdata/linkedin-company-post-scraper",
        "captured_at": "2026-05-21",
        "company_url": "https://www.linkedin.com/company/clerens/",
        "post_count": len(posts),
    }
    return content, meta


DOCUMENTS = [
    {
        "title": "CLERENS LinkedIn feed - 50-post snapshot (21 May 2026)",
        "document_type": "uploaded",
        "original_document_type": "apify_linkedin_scrape",
        "policy_areas": ["Batteries", "Energy Storage", "EU Funding"],
        "tags": ["apify", "clerens", "linkedin", "snapshot"],
        "build_content": "apify",
    },
    {
        "title": "BEPA position outline: amending the EU Batteries Regulation (DRAFT)",
        "document_type": "uploaded",
        "original_document_type": "analysis",
        "policy_areas": ["Batteries"],
        "tags": ["bepa-position", "batteries-regulation", "draft"],
        "celex_number": None,
        "procedure_reference": None,
        "executive_summary": (
            "BEPA welcomes the Commission's intent to amend Regulation (EU) 2023/1542 to align "
            "the Batteries Regulation with the Industrial Emissions Directive (IED, Directive "
            "(EU) 2024/1785), but insists the amending act must not weaken the 2031-2036 phase-in "
            "of recycled-content minima for cobalt, lithium and nickel, and must preserve the "
            "carbon-footprint declaration methodology already issued. Three asks: (1) protect "
            "the recycled-content phase-in, (2) align permitting of gigafactories under IED in a "
            "single one-stop-shop with NZIA Strategic Project status, (3) extend the battery "
            "passport timetable only with concrete supply-chain readiness criteria."
        ),
        "content": (
            "## BEPA position outline: amending the EU Batteries Regulation\n\n"
            "**Draft for BEPA Board review. Updated 21 May 2026.**\n\n"
            "### 1. Context\n\n"
            "The Commission has announced an amending proposal to Regulation (EU) 2023/1542 "
            "intended to align the Batteries Regulation with the Industrial Emissions Directive "
            "recast (Directive (EU) 2024/1785) and to address implementation feedback from the "
            "first 18 months of the parent Regulation. BEPA represents 250+ members across the "
            "battery value chain and is the industrial side of the Batt4EU partnership.\n\n"
            "### 2. Three priority asks\n\n"
            "**Ask 1 - Do not weaken the recycled-content phase-in.** Article 8 of Regulation "
            "2023/1542 sets minimum levels of recycled cobalt, lithium and nickel, phased in from "
            "2031 to 2036. BEPA members have already begun recycling investments calibrated to "
            "that timetable. Any softening would strand investment.\n\n"
            "**Ask 2 - Single permitting one-stop-shop.** Gigafactory permitting currently "
            "engages: (i) IED 2024/1785 (industrial emissions), (ii) the Batteries Regulation "
            "(due diligence, carbon footprint), (iii) NZIA 2024/1735 (Strategic Project status, "
            "accelerated permitting), and (iv) CRMA 2024/1252 (Strategic Project status for "
            "upstream materials). BEPA asks for an integrated one-stop-shop per Article 6 NZIA, "
            "with a single contact point and a binding 27-month permitting target.\n\n"
            "**Ask 3 - Carbon-footprint methodology must not be reopened.** The Commission "
            "delegated act on the carbon-footprint methodology has been heavily negotiated. "
            "Reopening it inside the amending procedure would delay the 2028 declaration deadline "
            "and harm EU competitiveness against Chinese cell makers.\n\n"
            "### 3. Procedural calendar\n\n"
            "- Commission proposal expected Q3 2026 under DG ENV / DG GROW joint lead.\n"
            "- EP rapporteur expected ENVI committee.\n"
            "- Council working group on Environment + Internal Market.\n"
            "- Trilogue likely Q2 2027.\n\n"
            "### 4. Suggested BEPA action\n\n"
            "1. Joint paper with EUROBAT and Eucobat on the recycled-content phase-in.\n"
            "2. Bilateral meeting requests with the cabinets of Commissioner Roswall (ENV) and "
            "Commissioner Sejourne (Industry). Through Clerens government-relations channel.\n"
            "3. Coordinate position with the German EUMICON and French France Industrie.\n"
            "4. Member intelligence: survey of BEPA members on planned recycling capacity "
            "investments and dependencies on the 2031-2036 timetable.\n"
        ),
    },
    {
        "title": "LIFE Programme 2026 calls: BEPA member opportunities (BRIEFING NOTE)",
        "document_type": "uploaded",
        "original_document_type": "briefing_note",
        "policy_areas": ["EU Funding", "Batteries"],
        "tags": ["life-programme", "bepa-members", "briefing"],
        "celex_number": "32021R0783",
        "procedure_reference": None,
        "content": (
            "## LIFE Programme 2026 calls: BEPA member opportunities\n\n"
            "**Briefing note for BEPA members - drafted 21 May 2026.**\n\n"
            "### 1. The LIFE landscape for batteries and storage\n\n"
            "The LIFE Programme (Regulation (EU) 2021/783) runs four sub-programmes:\n\n"
            "- Nature and Biodiversity\n"
            "- Circular Economy and Quality of Life\n"
            "- Climate Change Mitigation and Adaptation\n"
            "- Clean Energy Transition (CET)\n\n"
            "BEPA members typically apply under **Circular Economy and Quality of Life** "
            "(end-of-life batteries, recycling processes, second-life applications) and "
            "**Clean Energy Transition** (storage demonstration, grid services, market design).\n\n"
            "### 2. Open in 2026\n\n"
            "Specific call detail is best fetched via Brubru Tenderator on the day. As of 21 May "
            "2026 the public-call calendar shows:\n\n"
            "- LIFE Standard Action Projects (SAP) for Circular Economy: indicative budget envelope "
            "and Q3 2026 deadline.\n"
            "- LIFE Clean Energy Transition coordination and support actions (CSA): rolling.\n"
            "- LIFE Strategic Integrated Projects (SIP) and Strategic Nature Projects (SNAP): "
            "by invitation, multi-year, large envelopes.\n\n"
            "### 3. What Clerens learned from the 20 May 2026 webinar\n\n"
            "- LIFE 2026 is won on impact design, not on the size of the idea.\n"
            "- Evaluators look for: topic fit, measurable impact, the right consortium, a credible "
            "implementation plan.\n"
            "- Common pitfalls: scattered consortium, vague impact pathway, weak dissemination "
            "plan, overstated baseline.\n"
            "- Bonus levers: prior LIFE project credentials, link to a relevant EU strategy "
            "(Critical Raw Materials Act for recycling projects; Clean Industrial Deal for grid "
            "storage projects).\n\n"
            "### 4. Suggested next steps for BEPA members\n\n"
            "1. Pre-screen for fit: check the 2026 work programme for relevant calls.\n"
            "2. Map consortium gaps: typical LIFE consortium is 4-8 partners across 3+ Member "
            "States.\n"
            "3. Engage Clerens grant-support service early - the firm has a strong LIFE track "
            "record and can co-write the proposal.\n"
            "4. Apply for an Innovation Fund Round 5 slot in parallel if the project is TRL 8-9 "
            "first-of-a-kind deployment.\n"
        ),
    },
    {
        "title": "Innovation Fund Round 5 readiness check for energy-storage projects (BRIEFING NOTE)",
        "document_type": "uploaded",
        "original_document_type": "briefing_note",
        "policy_areas": ["EU Funding", "Energy Storage"],
        "tags": ["innovation-fund", "energy-storage", "readiness"],
        "celex_number": "32019R0856",
        "procedure_reference": None,
        "content": (
            "## Innovation Fund Round 5 readiness check for energy-storage projects\n\n"
            "**Briefing note for Energy Storage Europe and BEPA members. 21 May 2026.**\n\n"
            "### 1. What the Innovation Fund actually is\n\n"
            "The Innovation Fund (legal basis: ETS Directive 2003/87/EC Article 10a(8); mechanics "
            "via Implementing Regulation (EU) 2019/856) supports **first-of-a-kind deployment** "
            "of low-carbon technologies at TRL 8-9. Grant rates up to 60 percent of relevant "
            "costs. Strongly focused on demonstration scale, not on R&D. Two main calls per year: "
            "Large-scale projects and Small/Medium-scale projects.\n\n"
            "### 2. Eligibility for storage projects\n\n"
            "- Grid-scale battery storage, mechanical storage, thermal storage and power-to-X are "
            "all eligible.\n"
            "- Capital-expenditure intensive projects with measurable absolute GHG avoidance score "
            "best.\n"
            "- Cross-border projects are not required but are preferred.\n\n"
            "### 3. The three Innovation Fund myths (per the Clerens December 2025 LinkedIn post)\n\n"
            "**Myth 1: Innovation Fund is for R&D.** False. Innovation Fund is for first-of-a-kind "
            "demonstration. R&D goes to Horizon Europe Cluster 5 or to the Batt4EU partnership.\n\n"
            "**Myth 2: Only blue-chip companies win.** False. SMEs with strong consortia and "
            "measurable GHG avoidance score highly.\n\n"
            "**Myth 3: Submitting once is enough.** False. Many winning applications were "
            "resubmitted after a first reject with improved impact-pathway documentation.\n\n"
            "### 4. Suggested readiness check\n\n"
            "1. Is the project TRL 8-9? If lower, route to Horizon Europe or LIFE CET.\n"
            "2. Is the absolute GHG avoidance quantified for a 10-year horizon?\n"
            "3. Is the project capex reliably between 7.5 MEUR (small-scale) and the typical "
            "150-300 MEUR for large-scale?\n"
            "4. Is the financing plan complete - private funding, national co-funding, no "
            "double-funding?\n"
            "5. Is dissemination plan strong - public outputs, replication potential, knowledge "
            "transfer?\n"
        ),
    },
    {
        "title": "Talking points: DG RTD on Batt4EU partnership renewal (DRAFT)",
        "document_type": "uploaded",
        "original_document_type": "talking_points",
        "policy_areas": ["Batteries", "EU Funding"],
        "tags": ["batt4eu", "dg-rtd", "horizon-europe", "draft"],
        "celex_number": None,
        "procedure_reference": None,
        "objectives": (
            "Open a working channel between BEPA and DG RTD on the renewal of the Batt4EU "
            "co-programmed partnership for the second half of Horizon Europe. Anchor BEPA's "
            "role as the industrial-side counterpart."
        ),
        "content": (
            "## Talking points - DG RTD meeting on Batt4EU partnership renewal\n\n"
            "**One-pager for Joan ahead of the next DG RTD meeting. Draft.**\n\n"
            "### 1. Who BEPA is (60 seconds)\n\n"
            "Batteries European Partnership Association - founded 2020, 250+ members. Industrial "
            "counterpart to the Batt4EU Horizon Europe co-programmed partnership. Managed by "
            "Clerens (secretariat).\n\n"
            "### 2. Headline points\n\n"
            "**Point 1 - Batt4EU 2.0 strategic agenda.** The current strategic research agenda "
            "ends with the close of the current MFF (end-2027). BEPA proposes to extend with a "
            "consolidation phase that prioritises pilot lines, second-life applications and "
            "circular value chains alongside next-generation chemistries.\n\n"
            "**Point 2 - Tighten the loop with NZIA Strategic Projects.** Horizon Europe pilot-line "
            "investments often feed NZIA Strategic Project candidates. BEPA asks for a fast-track "
            "between RTD's results and NZIA / CRMA Strategic Project status.\n\n"
            "**Point 3 - Streamline the application route.** BEPA members find the dual route "
            "(Horizon Europe + Innovation Fund) costly. A coordinated calendar between RTD and "
            "CINEA would help.\n\n"
            "### 3. What BEPA offers DG RTD\n\n"
            "- Direct line into 250+ industrial members.\n"
            "- Annual stakeholder report on Batt4EU project outputs.\n"
            "- Joint events (BID, ESGC).\n\n"
            "### 4. Listening agenda\n\n"
            "- DG RTD's reading of the FP10 (next-MFF) battery research budget envelope.\n"
            "- Plans for a renewed Batt4EU partnership versus a new mission-led architecture.\n"
            "- Which Member State delegations are most active in shaping FP10.\n"
        ),
    },
    {
        "title": "ESGC 2026 event-brief skeleton (Brussels, 6-8 October 2026)",
        "document_type": "uploaded",
        "original_document_type": "event_brief",
        "policy_areas": ["Energy Storage"],
        "tags": ["esgc", "event-brief", "clerens", "draft"],
        "celex_number": None,
        "procedure_reference": None,
        "content": (
            "## Energy Storage Global Conference 2026 - event brief skeleton\n\n"
            "**Draft event brief. Updated 21 May 2026.**\n\n"
            "### 1. Event\n\n"
            "- Name: Energy Storage Global Conference (ESGC)\n"
            "- Dates: 6-8 October 2026\n"
            "- Location: Hotel Le Plaza, Brussels\n"
            "- Expected attendance: 400+\n"
            "- Host: Energy Storage Europe (managed by Clerens)\n\n"
            "### 2. Strategic context\n\n"
            "The conference falls during a window where the Council position on the Batteries "
            "Regulation amending proposal is expected, and where the Innovation Fund Round 5 "
            "results may have been announced. Both are conversation drivers.\n\n"
            "### 3. Themes to anchor the agenda\n\n"
            "- Long-duration storage and the new Electricity Market Design.\n"
            "- Battery storage in flexible grid services - ancillary markets, capacity mechanisms.\n"
            "- Hydrogen storage and power-to-X under the renewable-gas package (Reg 2024/1789).\n"
            "- Financing - Innovation Fund, LIFE CET, ETS auctioning revenues, EIB.\n"
            "- Trade and competition - CRMA Strategic Projects, Foreign Subsidies Regulation.\n\n"
            "### 4. Suggested speakers / invitees to test\n\n"
            "- Commission: cabinet of Commissioner Jorgensen (Energy and Housing), DG ENER C "
            "Director.\n"
            "- EP: rapporteurs of the Batteries amending proposal and EMD.\n"
            "- Industry: BEPA Board members, EASE counterparts, large grid operators.\n"
            "- Member States: presidency in trio (BE / DK / FR after the Polish presidency).\n\n"
            "### 5. Logistics watch-outs\n\n"
            "- Same week as some EP committee sittings - check the EP calendar for conflicts.\n"
            "- Hotel Le Plaza capacity is around 450 plenary - design break-out tracks "
            "accordingly.\n"
            "- Hybrid streaming required - last year's hybrid attendees were 35 percent of total.\n"
        ),
    },
]


def upsert_user(db, apply: bool) -> str:
    existing = db.execute(
        text("SELECT id::text, subscription_tier FROM users WHERE email = :e"),
        {"e": USER_EMAIL},
    ).first()
    if not existing:
        raise RuntimeError(f"User {USER_EMAIL} not found - expected to exist (test users seed).")
    logger.info(f"  [user] exists: {USER_EMAIL} (id={existing.id[:8]}, current tier={existing.subscription_tier})")
    if apply:
        db.execute(
            text("""
                UPDATE users SET
                    full_name = :full_name,
                    first_name = :first_name,
                    preferred_name = :preferred_name,
                    organization = :org,
                    role_title = :role_title,
                    country = :country,
                    language = :language,
                    timezone = :tz,
                    policy_interests = CAST(:interests AS JSONB),
                    subscription_tier = :tier,
                    subscription_expires_at = :expires_at,
                    is_active = true,
                    is_verified = true,
                    updated_at = NOW()
                WHERE email = :email
            """),
            {
                "full_name": USER_FULL_NAME,
                "first_name": USER_FIRST_NAME,
                "preferred_name": USER_PREFERRED_NAME,
                "org": USER_ORG,
                "role_title": USER_ROLE_TITLE,
                "country": USER_COUNTRY,
                "language": USER_LANGUAGE,
                "tz": USER_TIMEZONE,
                "interests": json.dumps(POLICY_INTERESTS),
                "tier": SUBSCRIPTION_TIER,
                "expires_at": SUBSCRIPTION_EXPIRES_AT,
                "email": USER_EMAIL,
            },
        )
        logger.info(f"  [user] updated metadata + tier={SUBSCRIPTION_TIER}, expires={SUBSCRIPTION_EXPIRES_AT.date()}")
    return existing.id


def resolve_carriage_uuids(db, short_ids: list[str]) -> dict[str, str]:
    out = {}
    for s in short_ids:
        row = db.execute(text("SELECT id::text FROM legislative_carriages WHERE id::text LIKE :p LIMIT 1"), {"p": s + "%"}).first()
        if row:
            out[s] = row.id
        else:
            logger.warning(f"  [WARN] no legislative_carriage row found for short id {s}")
    return out


def seed_carriage_tracks(db, user_id: str, apply: bool):
    resolved = resolve_carriage_uuids(db, CARRIAGE_SHORT_IDS)
    for short, uid in resolved.items():
        exists = db.execute(
            text("SELECT 1 FROM user_carriage_tracks WHERE user_id = :u AND carriage_id = :c"),
            {"u": user_id, "c": uid},
        ).first()
        if exists:
            logger.info(f"  [track] SKIP carriage {short}")
            continue
        if apply:
            db.execute(
                text("""
                    INSERT INTO user_carriage_tracks (
                        id, user_id, carriage_id,
                        notify_on_status_change, notify_on_blocking, notify_on_new_documents,
                        tracked_since
                    ) VALUES (
                        :id, :u, :c, true, true, true, NOW()
                    )
                """),
                {"id": str(uuid.uuid4()), "u": user_id, "c": uid},
            )
            logger.info(f"  [track] CREATE carriage {short}")
        else:
            logger.info(f"  [track] WOULD CREATE carriage {short}")


def seed_documents(db, user_id: str, apply: bool):
    for d in DOCUMENTS:
        exists = db.execute(
            text("SELECT 1 FROM user_documents WHERE user_id = :u AND title = :t"),
            {"u": user_id, "t": d["title"]},
        ).first()
        if exists:
            logger.info(f"  [doc] SKIP '{d['title'][:60]}'")
            continue

        # Build doc_metadata with the canonical original_document_type pin
        meta = {"original_document_type": d.get("original_document_type", "uploaded")}
        if d.get("build_content") == "apify":
            content, extra_meta = build_apify_doc_content()
            meta.update(extra_meta)
        else:
            content = d.get("content")

        if apply:
            db.execute(
                text("""
                    INSERT INTO user_documents (
                        id, user_id, document_type, title, content,
                        celex_number, procedure_reference,
                        policy_areas, tags,
                        executive_summary, objectives, action_plan, timeline, stakeholders,
                        doc_metadata,
                        include_in_ai_context, is_private,
                        version, view_count, is_featured,
                        created_at, updated_at
                    ) VALUES (
                        :id, :u, :type, :title, :content,
                        :celex, :proc,
                        :areas, :tags,
                        :exec_sum, :objectives, :action_plan, :timeline, :stakeholders,
                        CAST(:meta AS jsonb),
                        true, true,
                        1, 0, false,
                        NOW(), NOW()
                    )
                """),
                {
                    "id": str(uuid.uuid4()),
                    "u": user_id,
                    "type": d["document_type"],
                    "title": d["title"],
                    "content": content,
                    "celex": d.get("celex_number"),
                    "proc": d.get("procedure_reference"),
                    "areas": d.get("policy_areas"),
                    "tags": d.get("tags"),
                    "exec_sum": d.get("executive_summary"),
                    "objectives": d.get("objectives"),
                    "action_plan": d.get("action_plan"),
                    "timeline": d.get("timeline"),
                    "stakeholders": d.get("stakeholders"),
                    "meta": json.dumps(meta),
                },
            )
            logger.info(f"  [doc] CREATE [{d['original_document_type']:<22}] '{d['title'][:60]}'")
        else:
            logger.info(f"  [doc] WOULD CREATE [{d['original_document_type']:<22}] '{d['title'][:60]}'")


def flip_private_guide(db, apply: bool):
    if apply:
        db.execute(
            text("""
                UPDATE users
                SET private_guide_slug = :slug,
                    private_guide_status = 'ready',
                    private_guide_updated_at = NOW()
                WHERE email = :e
            """),
            {"slug": PRIVATE_GUIDE_SLUG, "e": USER_EMAIL},
        )
        logger.info(f"  [guide] users.{USER_EMAIL}.private_guide_slug = '{PRIVATE_GUIDE_SLUG}', status=ready")
    else:
        logger.info(f"  [guide] WOULD set users.{USER_EMAIL}.private_guide_slug = '{PRIVATE_GUIDE_SLUG}'")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write to DB (default: dry-run)")
    args = ap.parse_args()

    apply = args.apply
    logger.info("=" * 78)
    logger.info(f"Seed Joan Gonzalez / CLERENS - {'APPLY' if apply else 'DRY RUN'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        user_id = upsert_user(db, apply)
        seed_carriage_tracks(db, user_id, apply)
        seed_documents(db, user_id, apply)
        flip_private_guide(db, apply)

        if apply:
            from scripts._validate_user_documents import validate_user_documents_for
            n = validate_user_documents_for(db, user_id)
            logger.info(f"  [validate] {n} user_documents rows round-trip cleanly")
            db.commit()
            logger.info("\n[OK] committed.")
        else:
            db.rollback()
            logger.info("\n[OK] dry-run only. Re-run with --apply to commit.")
    except Exception as e:
        db.rollback()
        logger.exception(f"FAILED: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
