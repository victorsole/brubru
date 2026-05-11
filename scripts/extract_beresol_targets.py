"""
Extract Brussels-based trade associations and industry federations from
the EU Transparency Register data as potential Beresol clients.

Reads: data/emails/lobby_orgs_raw.csv + data/emails/lobby_orgs_emails.csv
Writes: docs/targets/transparency_register_targets.csv
"""

import csv
import re
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_CSV = os.path.join(BASE_DIR, "data/emails/lobby_orgs_raw.csv")
EMAIL_CSV = os.path.join(BASE_DIR, "data/emails/lobby_orgs_emails.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "docs/targets/transparency_register_targets.csv")

# Category filter: II (trade/business/professional) and III (NGOs)
ALLOWED_CATEGORIES = {
    "Trade and business associations",
    "Trade unions and professional associations",
    "Professional consultancies",
    "Non-governmental organisations, platforms and networks and similar",
}

ALLOWED_SUBCATEGORIES = {
    "Trade and business associations",
    "Trade unions and professional associations",
    "Non-governmental organisations, platforms and networks and similar",
}

# Sector keywords -> sector label
SECTOR_KEYWORDS = {
    "defence": ["defence", "defense", "military", "arms", "aerospace", "security industry", "nato"],
    "finance": ["financ", "fintech", "banking", "insurance", "investment", "capital market", "payment", "credit", "asset management", "pension"],
    "tech/AI/digital": ["artificial intelligence", " ai ", "digital", "software", "cyber", "data ", "cloud", "ict ", "tech", "telecom", "internet", "platform", "e-commerce", "semiconductor", "chip"],
    "quantum": ["quantum"],
    "startups/SMEs": ["startup", "start-up", "sme", "small and medium", "entrepreneur", "venture", "innovation ecosystem"],
    "trade/tariffs": ["trade policy", "tariff", "customs", "export", "import", "free trade", "wto ", "trade agreement"],
    "commodities": ["commodity", "commodit", "gold", "mining", "raw material", "mineral", "metal"],
    "health": ["health", "pharma", "medical", "biotech", "hospital", "clinic", "drug", "medic", "patient", "vaccine", "life science"],
    "fitness": ["fitness", "sport", "gym", "wellness", "physical activity"],
    "energy": ["energy", "oil", "gas ", "renewable", "solar", "wind power", "nuclear", "hydrogen", "battery", "grid", "electricity", "coal", "biofuel", "biogas"],
    "transport": ["transport", "aviation", "shipping", "rail", "automotive", "mobility", "logistics", "freight", "airline", "airport", "port ", "maritime"],
    "agriculture": ["agricult", "farming", "food", "agri-food", "crop", "livestock", "fisheries", "dairy", "wine", "organic farming", "seed", "fertiliz"],
}


def classify_sector(text: str) -> str | None:
    """Match org text against sector keywords, return first match."""
    text_lower = text.lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return sector
    return None


def parse_budget(cost_str: str) -> float | None:
    """Parse calculated_cost field to float."""
    try:
        val = float(cost_str)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


def parse_fte(fte_str: str) -> float | None:
    """Parse members_fte field to float."""
    try:
        val = float(fte_str)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


def generate_pitch(org_name: str, sector: str, goals: str) -> str:
    """Generate a one-sentence Beresol pitch angle."""
    goals_lower = goals.lower()

    # Sector-specific pitches
    pitches = {
        "defence": "Interactive EU defence procurement tracker dashboard with AI-powered tender matching",
        "finance": "Real-time EU financial regulation monitor with AI alerts on MiFID/CRD/AML updates",
        "tech/AI/digital": "AI-powered EU digital policy dashboard tracking DSA/DMA/AI Act compliance deadlines",
        "quantum": "Modern website + interactive EU quantum research funding tracker with grant deadline alerts",
        "startups/SMEs": "AI chatbot for SME members answering EU funding and regulatory questions in real-time",
        "trade/tariffs": "Interactive tariff impact calculator and trade agreement tracker dashboard",
        "commodities": "Real-time commodity regulation tracker with EUR-Lex integration and price impact analysis",
        "health": "EU health regulation monitor with AI-generated summaries of EMA/HERA developments",
        "fitness": "Modern website redesign + EU sport policy tracker with funding opportunity alerts",
        "energy": "Interactive EU energy policy dashboard with Fit for 55 implementation tracker and AI briefings",
        "transport": "EU transport regulation monitor with interactive modal shift and emissions tracking maps",
        "agriculture": "CAP reform tracker dashboard with AI-powered subsidy and compliance monitoring tools",
    }

    base = pitches.get(sector, "Modern website with AI-powered EU policy monitoring dashboard")

    # Refine based on goals content
    if "publish" in goals_lower or "report" in goals_lower or "data" in goals_lower:
        base += "; data visualisation portal for publications"
    if "monitor" in goals_lower or "track" in goals_lower:
        base += "; automated legislative tracking system"
    if "member" in goals_lower and ("inform" in goals_lower or "service" in goals_lower):
        base += "; member-facing news portal with AI digests"

    # Trim to one sentence (take first part before semicolons if too long)
    parts = base.split(";")
    return parts[0].strip()


def main():
    # Load emails lookup
    email_lookup = {}
    if os.path.exists(EMAIL_CSV):
        with open(EMAIL_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email_lookup[row["identification_code"]] = row.get("contact_email", "")

    # Process raw data
    results = []
    with open(RAW_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            main_cat = row.get("main_category", "")
            sub_cat = row.get("sub_category", "")

            # Category filter
            cat_match = main_cat in ALLOWED_CATEGORIES or sub_cat in ALLOWED_SUBCATEGORIES
            if not cat_match:
                continue

            # Brussels presence filter
            be_city = (row.get("be_city") or "").strip().lower()
            head_country = (row.get("head_country") or "").strip().upper()
            has_brussels = "brussel" in be_city or "bruxelles" in be_city or "brussels" in be_city
            has_belgium_hq = head_country == "BELGIUM"

            if not has_brussels and not has_belgium_hq:
                continue

            # Combine text for sector matching
            combined_text = " ".join([
                row.get("original_name", ""),
                row.get("goals", ""),
                row.get("activity_eu_legislative", ""),
                row.get("sub_category", ""),
            ])

            sector = classify_sector(combined_text)
            if not sector:
                continue

            # Budget filter: 500K - 50M (calculated_cost is annual cost in EUR)
            budget = parse_budget(row.get("calculated_cost", ""))
            fte = parse_fte(row.get("members_fte", ""))

            # Budget 500K-50M, staff 5-50. Require budget data.
            if budget is None or budget < 500000 or budget > 50000000:
                continue
            if fte is not None and (fte < 2 or fte > 50):
                continue

            # Determine category label
            if "trade" in main_cat.lower() or "trade" in sub_cat.lower():
                cat_label = "trade association"
            elif "professional" in main_cat.lower() or "professional" in sub_cat.lower() or "union" in main_cat.lower():
                cat_label = "professional body"
            elif "non-governmental" in main_cat.lower() or "non-governmental" in sub_cat.lower():
                cat_label = "NGO"
            else:
                cat_label = "other"

            # Get email
            org_id = row.get("identification_code", "")
            email = email_lookup.get(org_id, "")

            # Brussels address
            brussels_addr = be_city.title() if be_city else ("Belgium" if has_belgium_hq else "")

            # Website
            website = row.get("web_site_url", "").strip()
            if website and not website.startswith("http"):
                website = "https://" + website

            # Pitch
            pitch = generate_pitch(
                row.get("original_name", ""),
                sector,
                row.get("goals", "")
            )

            results.append({
                "organisation_name": row.get("original_name", ""),
                "category": cat_label,
                "sector": sector,
                "website_url": website,
                "brussels_address": brussels_addr,
                "contact_email": email,
                "annual_budget_eur": int(budget) if budget else "",
                "staff_count": fte if fte else "",
                "beresol_pitch_angle": pitch,
            })

    # Sort by sector, then budget descending
    def sort_key(r):
        budget_val = r["annual_budget_eur"] if r["annual_budget_eur"] != "" else 0
        return (r["sector"], -budget_val)

    results.sort(key=sort_key)

    # Write output
    fieldnames = [
        "organisation_name", "category", "sector", "website_url",
        "brussels_address", "contact_email", "annual_budget_eur",
        "staff_count", "beresol_pitch_angle"
    ]

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"[OK] Wrote {len(results)} targets to {OUTPUT_CSV}")

    # Sector breakdown
    from collections import Counter
    sector_counts = Counter(r["sector"] for r in results)
    print("\nSector breakdown:")
    for sector, count in sector_counts.most_common():
        print(f"  {sector}: {count}")

    # Budget stats for those with data
    budgets = [r["annual_budget_eur"] for r in results if r["annual_budget_eur"] != "" and r["annual_budget_eur"] > 0]
    if budgets:
        print(f"\nBudget stats (n={len(budgets)}):")
        print(f"  Min: {min(budgets):,.0f} EUR")
        print(f"  Max: {max(budgets):,.0f} EUR")
        print(f"  Median: {sorted(budgets)[len(budgets)//2]:,.0f} EUR")

    # How many have emails
    with_email = sum(1 for r in results if r["contact_email"])
    print(f"\nWith contact email: {with_email}/{len(results)}")


if __name__ == "__main__":
    main()
