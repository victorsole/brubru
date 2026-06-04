"""
Seed Victor's (victor@hellobo.eu) My Documents with a realistic Bo / Hellobo
advocacy library, as if he had just onboarded and started building his memory layer.

All 13 documents are grounded in:
  - real Bo positioning (hellobo.eu): "From the land, for you", map-based GI
    marketplace, products wine/cheese/beer/fruits/vegetables/crafts, markets
    ES/NL/BE/IT/FR + Catalonia, three audiences (Visitors / Hosts / GIs),
    free to join, first 10 bookings commission-free then 5%.
  - verified EU facts: Regulation (EU) 2024/1143 on geographical indications for
    wine, spirit drinks and agricultural products (in force 13 May 2024, repealing
    Reg (EU) 1151/2012), labelling changes applying 14 May 2026; the EU craft and
    industrial GI system, live since 1 December 2025 and administered by the EUIPO.

Policy area on every row: "Agriculture" (Victor's single Policy Interest).
include_in_ai_context = True on every row (the point is to feed Chat).

Usage:
    python3.12 -m backend.scripts.seed_hellobo_documents --email victor@hellobo.eu
    python3.12 -m backend.scripts.seed_hellobo_documents --email victor@hellobo.eu --apply
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from core.database import SessionLocal
from models.user import User
from models.user_document import UserDocument

POLICY = ["Agriculture"]


# --------------------------------------------------------------------------- #
# 1. EP written question
# --------------------------------------------------------------------------- #
EP_WRITTEN_QUESTION = """\
**Question for written answer to the Commission**
Rule 138

**Subject: Digital market access and labelling compliance for small geographical-indication producers under Regulation (EU) 2024/1143**

Tabled by: [to be confirmed with a sympathetic AGRI Committee Member]

Regulation (EU) 2024/1143 modernises the Union's geographical-indications (GI) regime for wine, spirit drinks and agricultural products. From 14 May 2026, new labelling obligations apply, including the requirement to show the name of the producer or operator in the same field of vision as the GI name.

For many micro and small producers, including the wine, cheese and craft producers active on discovery platforms such as Bo, these obligations arrive alongside limited administrative capacity and limited digital reach.

1. How will the Commission ensure that the 14 May 2026 labelling changes do not place a disproportionate administrative burden on micro and small GI producers, and what transitional support is foreseen?

2. Can the Commission confirm whether EAFRD instruments and the Smart Villages approach may be used by Member States to fund digital compliance and market-access tools for small GI producers and producer groups?

3. How will the EUIPO domain-name information and alert system established under Regulation (EU) 2024/1143 interact with legitimate online marketplaces, so that genuine producers are protected without being treated as infringers?
"""


# --------------------------------------------------------------------------- #
# 2. EP resolution
# --------------------------------------------------------------------------- #
EP_RESOLUTION = """\
**Motion for a resolution on supporting small geographical-indication producers in the digital single market**

The European Parliament,

- having regard to Regulation (EU) 2024/1143 on geographical indications for wine, spirit drinks and agricultural products, as well as traditional specialities guaranteed and optional quality terms,
- having regard to the entry into application of new GI labelling rules on 14 May 2026,
- having regard to the launch on 1 December 2025 of the Union system for the protection of craft and industrial geographical indications, administered by the EUIPO,
- having regard to the common agricultural policy and the European Agricultural Fund for Rural Development,
- having regard to Rule 54 of its Rules of Procedure,

A. whereas geographical indications protect the names of products whose quality, reputation or characteristics are linked to their place of origin, and sustain rural employment and short supply chains;

B. whereas the majority of GI producers are micro, small or medium-sized enterprises with limited administrative and digital capacity;

C. whereas consumer awareness of GIs remains uneven across the Union, and many small producers lack affordable channels to reach consumers and visitors;

D. whereas digital discovery platforms can lower the cost of market access for small producers and strengthen the link between consumers, producers and the territory;

1. Welcomes the modernisation of the GI regime under Regulation (EU) 2024/1143 and the extension of GI protection to craft and industrial products;

2. Calls on the Commission to ensure that the new labelling obligations are accompanied by proportionate guidance and transitional support for micro and small producers;

3. Stresses that EAFRD funding and the Smart Villages approach should be available to support digital market access, short supply chains and agritourism for GI producers;

4. Encourages cooperation between competent authorities, producer groups and legitimate online platforms to promote GIs and to combat fraudulent use of protected names;

5. Instructs its President to forward this resolution to the Council and the Commission.
"""


# --------------------------------------------------------------------------- #
# 3. Position paper
# --------------------------------------------------------------------------- #
POSITION_PAPER = """\
# Position paper: making the new EU geographical-indications regime work for small producers

## Executive summary

The new Union geographical-indications (GI) regime, set by Regulation (EU) 2024/1143 and complemented since 1 December 2025 by the EUIPO-administered system for craft and industrial GIs, is a once-in-a-generation modernisation. Bo welcomes it. Our concern is implementation: the producers who most need the protection, micro and small farms, cellars and workshops, are also those least equipped to absorb new labelling and administrative obligations or to reach consumers online.

## Context

Geographical indications identify products whose quality and reputation are tied to a place. They keep value in rural territories and support short supply chains. From 14 May 2026, Regulation (EU) 2024/1143 applies new labelling rules, including showing the name of the producer or operator in the same field of vision as the GI name. The Regulation also tasks the EUIPO with a domain-name information and alert system to protect GIs online.

## Bo's view

Bo (Hellobo 2025 SL, "From the land, for you") is a map-based marketplace connecting visitors with local producers and GI consortia across Spain, the Netherlands, Belgium, Italy, France and Catalonia. Our producers sell wine, cheese, beer, fruit, vegetables and crafts. They tell us the same thing: the rules are right, but the cost of compliance and the cost of being found are real barriers.

Digital discovery is not a threat to the GI system; it is one of its best delivery mechanisms. A small PDO cheese maker who can be found, booked and bought from in minutes is a producer who can afford to comply.

## Recommendations

1. Pair the 14 May 2026 labelling changes with plain-language guidance and a transition window for micro producers.
2. Make EAFRD and Smart Villages funding explicitly usable for digital market access and compliance tools for GI producers.
3. Treat legitimate marketplaces as partners in the EUIPO online-protection system, not as suspects.
4. Fund consumer-facing GI awareness, including agritourism and producer experiences.

## About Bo

Free to join; the first ten bookings are commission-free, then a 5% commission applies. Mobile apps on iOS and Android, plus a web app. Contact: contact@hellobo.eu.
"""


# --------------------------------------------------------------------------- #
# 4. MEP briefing note
# --------------------------------------------------------------------------- #
MEP_BRIEFING = """\
# Briefing for AGRI Committee Members
## Geographical indications, rural producers and digital market access

**Prepared by Bo (Hellobo 2025 SL) - for a meeting on the implementation of Regulation (EU) 2024/1143**

### Key messages

- The new GI regime is welcome. The risk is implementation falling hardest on the smallest producers.
- New labelling rules apply from 14 May 2026. Micro producers need guidance and time, not penalties.
- Digital discovery platforms lower the cost of market access and of being found by consumers.

### Why it matters for your constituents

Most GI producers are micro and small enterprises. In the regions Bo serves (Spain, the Netherlands, Belgium, Italy, France and Catalonia), wine, cheese, beer, fruit, vegetable and craft producers are the backbone of rural economies and agritourism.

### What we ask

1. Push the Commission for proportionate, plain-language implementation guidance for micro producers.
2. Confirm that EAFRD and Smart Villages funding can support digital compliance and market access.
3. Ensure the EUIPO online-protection system works with legitimate marketplaces, not against them.

### Contact

Víctor Solé Ferioli, Co-Founder and CEO, Bo. contact@hellobo.eu.
Note: Bo is not yet listed in the EU Transparency Register.
"""


# --------------------------------------------------------------------------- #
# 5. Talking points
# --------------------------------------------------------------------------- #
TALKING_POINTS = """\
# Talking points: Bo and the new EU geographical-indications regime

**Use in a 15-minute meeting or call with an MEP office or Commission desk.**

### The opener
- "Geographical indications keep value on the land. The new rules are right. Our worry is the smallest producers being left behind."

### On Regulation (EU) 2024/1143
- Modernises the GI regime for wine, spirits and agricultural products.
- New labelling rules apply from 14 May 2026, including the producer name in the same field of vision.
- The EUIPO now runs a domain-name alert system to protect GIs online.

### On the gap
- Most GI producers are micro or small. They face the same rules as large operators, with a fraction of the capacity.
- Being compliant is one challenge. Being found by consumers is another.

### What Bo brings
- A map-based marketplace connecting visitors with local producers and GI consortia.
- Live across Spain, the Netherlands, Belgium, Italy, France and Catalonia.
- Free to join; first ten bookings commission-free, then 5%.

### The three asks
1. Proportionate implementation guidance and a transition window for micro producers.
2. EAFRD and Smart Villages funding usable for digital market access.
3. Legitimate marketplaces as partners in online GI protection.

### The close
- "Help us make the GI system something a small producer can actually use, not just comply with."
"""


# --------------------------------------------------------------------------- #
# 6. EP petition
# --------------------------------------------------------------------------- #
EP_PETITION = """\
# Petition to the European Parliament
## Ensure the new GI rules empower, not burden, Europe's small food and craft producers

**Petitioner:** Víctor Solé Ferioli, on behalf of Bo (Hellobo 2025 SL)
**Committee:** Committee on Petitions (PETI)
**Subject:** Implementation of Regulation (EU) 2024/1143 and the craft and industrial GI system

### Text of the petition

The petitioner welcomes the modernisation of the Union's geographical-indications system under Regulation (EU) 2024/1143 and the launch, on 1 December 2025, of the EUIPO-administered system for craft and industrial geographical indications.

The petitioner is concerned that the new obligations, including the labelling rules applying from 14 May 2026, risk placing a disproportionate burden on the micro and small producers who form the majority of GI holders, and who often lack the administrative capacity and the digital reach of larger operators.

### Request

The petitioner calls on the European Parliament to:

1. ask the Commission for proportionate, plain-language implementation guidance and a transition window for micro and small producers;
2. confirm that rural-development funding can support digital compliance and market-access tools;
3. ensure that the online GI-protection system treats legitimate marketplaces as partners.

The petitioner consents to the public registration of this petition.
"""


# --------------------------------------------------------------------------- #
# 7. Email / letter (with Bo logo)
# --------------------------------------------------------------------------- #
EMAIL_LETTER = """\
<p><img src="/clients/bo.png" alt="Bo" style="height:52px;width:auto;" /></p>

**From the land, for you**

---

Dear Honourable Member,

I am writing on behalf of Bo, a marketplace that connects travellers and consumers with Europe's local producers and geographical-indication consortia. Our community of wine, cheese, beer, fruit, vegetable and craft producers spans Spain, the Netherlands, Belgium, Italy, France and Catalonia.

With Regulation (EU) 2024/1143 now in force and new labelling rules applying from 14 May 2026, we believe this is the moment to make sure the geographical-indications system works for the smallest producers, not only the largest. These producers keep value on the land, sustain rural employment and define the taste of Europe's regions.

I would welcome fifteen minutes to show you how a discovery platform can help small GI producers comply with the new rules and reach the consumers who are looking for exactly what they make. We can come to you, in person or online.

With kind regards,

**Víctor Solé Ferioli**
Co-Founder and Chief Executive Officer, Bo (Hellobo 2025 SL)
contact@hellobo.eu
"""


# --------------------------------------------------------------------------- #
# 8. Position paper one-pager
# --------------------------------------------------------------------------- #
ONE_PAGER = """\
# Bo and Europe's geographical indications - one-pager

### The problem
Europe's geographical-indications regime is being modernised by Regulation (EU) 2024/1143, with new labelling rules from 14 May 2026. The producers who need GI protection most, micro and small farms, cellars and workshops, are the least equipped to absorb new obligations or to reach consumers online.

### Our solution
Bo is a map-based marketplace that connects visitors and consumers with local producers and GI consortia. Producers set up a profile in a minute. Free forever to join; the first ten bookings are commission-free, then 5%.

### Three asks
1. Proportionate implementation guidance and a transition window for micro producers.
2. EAFRD and Smart Villages funding usable for digital market access and compliance.
3. Legitimate marketplaces treated as partners in online GI protection.

### The numbers that matter
- Markets live today: Spain, the Netherlands, Belgium, Italy, France, Catalonia.
- Product families: wine, cheese, beer, fruit, vegetables, crafts.
- Cost to a producer to join: zero.

**Contact:** Víctor Solé Ferioli, CEO, Bo. contact@hellobo.eu
"""


# --------------------------------------------------------------------------- #
# 9. EU press release
# --------------------------------------------------------------------------- #
PRESS_RELEASE = """\
# Press release

**FOR IMMEDIATE RELEASE**

## Bo welcomes the new EU geographical-indications rules and calls for support for small producers

**Barcelona / Brussels, 30 May 2026** - Bo, the marketplace that connects consumers and travellers with Europe's local producers and geographical-indication (GI) consortia, today welcomed the modernised Union GI regime under Regulation (EU) 2024/1143 and urged the EU institutions to make sure its benefits reach the smallest producers.

New labelling rules under the Regulation apply from 14 May 2026, and since 1 December 2025 the EUIPO has administered a parallel system protecting craft and industrial GIs.

"Geographical indications are how Europe keeps value on the land," said Víctor Solé Ferioli, Co-Founder and CEO of Bo. "The new rules are the right direction. Our job, and the institutions' job, is to make sure a small cheese maker or a family winery can actually use the system, not just comply with it."

Bo's marketplace is live across Spain, the Netherlands, Belgium, Italy, France and Catalonia, covering wine, cheese, beer, fruit, vegetables and crafts. Producers join for free, with the first ten bookings commission-free.

The company is calling for proportionate implementation guidance for micro producers, for rural-development funding to be usable for digital market access, and for legitimate marketplaces to be treated as partners in online GI protection.

### About Bo
Bo (Hellobo 2025 SL) is a map-based marketplace under the tagline "From the land, for you", connecting visitors with local producers and GI consortia through mobile and web apps.

**Media contact:** contact@hellobo.eu
"""


# --------------------------------------------------------------------------- #
# 10. Stakeholder mapping
# --------------------------------------------------------------------------- #
STAKEHOLDER_MAP = """\
# Stakeholder map: the EU geographical-indications ecosystem

A working map of who shapes GI policy and implementation, and where Bo engages.

| Stakeholder | Role in the GI file | Interest | Bo's angle |
|---|---|---|---|
| DG AGRI (European Commission) | Owner of the agricultural GI regime, Reg (EU) 2024/1143 | High | Implementation guidance for small producers |
| EUIPO | Administers craft and industrial GIs and the online alert system | High | Marketplaces as partners in online protection |
| EP Committee on Agriculture (AGRI) | Parliamentary scrutiny of CAP and GI policy | High | Briefings, written questions |
| EP Committee on the Internal Market (IMCO) | Digital single market, platforms | Medium | Digital market access framing |
| EP Committee on Petitions (PETI) | Channel for citizen and producer concerns | Medium | Petition route |
| Council (AGRIFISH configuration) | Member State positions on agriculture | Medium | Member State implementation choices |
| GI consortia and oriGIn | Represent PDO/PGI/TSG producer groups | High | Natural allies; co-design discovery |
| National competent authorities | GI controls and enforcement | Medium | Compliance support |
| Producer groups (micro and SMEs) | The beneficiaries of the regime | High | Bo's core users |
| Consumer organisations | Authenticity and information | Medium | Transparency and provenance |
| Agritech and marketplace platforms | Market access and discovery | Medium | Bo's peer group |

### Influence and interest read
- **High influence, high interest:** DG AGRI, EUIPO, AGRI Committee, GI consortia. These are the priority relationships.
- **Lower influence, high interest:** micro producers and producer groups. Bo's role is to amplify their voice.

### First moves
1. Build the GI-consortia relationships first; they confer legitimacy.
2. Take the small-producer evidence to AGRI and DG AGRI.
3. Use PETI as a citizen-grounded escalation route if needed.
"""


# --------------------------------------------------------------------------- #
# 11. Impact assessment
# --------------------------------------------------------------------------- #
IMPACT_ASSESSMENT = """\
# Impact assessment: the 14 May 2026 GI labelling changes and small producers

*A Bo working assessment, in the style of an EU impact assessment. Figures are illustrative pending producer survey data.*

## 1. Problem definition

From 14 May 2026, Regulation (EU) 2024/1143 applies new labelling obligations to GI products, including showing the name of the producer or operator in the same field of vision as the GI name. The policy intent, transparency and authenticity, is sound. The open question is the distribution of the compliance burden across producer sizes.

## 2. Affected population

GI producers are predominantly micro and small enterprises. Larger operators have legal, design and packaging capacity in-house; micro producers typically do not. The burden of a labelling change is therefore regressive: the same rule costs a micro producer proportionally more.

## 3. Policy options

- **Option A - Baseline:** apply the rules with no targeted support.
- **Option B - Guidance and transition:** plain-language guidance plus a transition window for micro producers.
- **Option C - Guidance, transition and funded digital tools:** Option B plus EAFRD and Smart Villages funding for compliance and market-access tools, including discovery platforms.

## 4. Assessment of impacts

| Impact | Option A | Option B | Option C |
|---|---|---|---|
| Administrative burden on micro producers | High | Medium | Low to medium |
| Compliance rate by 2027 | Uneven | Good | Good |
| Market access for small producers | Unchanged | Unchanged | Improved |
| Cost to public funds | None | Low | Medium |

## 5. Preferred option

**Option C.** Coupling proportionate transition with funded digital market access turns a compliance cost into a growth opportunity for rural producers, and uses existing CAP instruments rather than new ones.

## 6. Monitoring

Track compliance rates by producer size, uptake of EAFRD digital-tool funding, and small-producer market-access indicators on platforms such as Bo.
"""


# --------------------------------------------------------------------------- #
# 12. EU presentation
# --------------------------------------------------------------------------- #
PRESENTATION = """\
# Bo - connecting Europe's GI producers with consumers
*Presentation deck. One section per slide.*

## Slide 1 - Title
**Bo: from the land, for you.** Connecting Europe's geographical-indication producers with the consumers looking for them.

## Slide 2 - The opportunity
Geographical indications keep value on the land. Regulation (EU) 2024/1143 modernises the regime; new labelling rules apply from 14 May 2026; craft and industrial GIs are protected since 1 December 2025.

## Slide 3 - The gap
Most GI producers are micro or small. They face the same rules as large operators, and struggle to be found by consumers.

## Slide 4 - What Bo is
A map-based marketplace. Visitors discover and book; producers showcase and sell; GI consortia tell the story of their region. Wine, cheese, beer, fruit, vegetables, crafts.

## Slide 5 - Where we are
Live across Spain, the Netherlands, Belgium, Italy, France and Catalonia. Mobile apps and a web app.

## Slide 6 - The model
Free to join. The first ten bookings are commission-free. A 5% commission applies after that. Set up a profile in a minute.

## Slide 7 - The ask to policymakers
1. Proportionate implementation guidance for micro producers.
2. EAFRD and Smart Villages funding for digital market access.
3. Marketplaces as partners in online GI protection.

## Slide 8 - Close
A geographical indication is only as strong as the producer who can use it. Help us make the system usable. contact@hellobo.eu
"""


# --------------------------------------------------------------------------- #
# 13. Event poster
# --------------------------------------------------------------------------- #
EVENT_POSTER = """\
<div style="text-align:center;">

<img src="/clients/bo.png" alt="Bo" style="height:64px;width:auto;" />

# TASTE THE ORIGIN
## A Bo geographical-indications discovery day

**Meet the producers behind Europe's protected names.**

</div>

---

### What is on

- Tastings of PDO and PGI wine, cheese and beer from local producers
- "Find it on the map" - discover and book producer experiences with the Bo app
- Short talk: what the new EU GI rules (Regulation (EU) 2024/1143) mean for you
- Q and A with founders and GI consortia

### When and where

**Saturday, a market square near you** - Barcelona, Brussels and Apeldoorn editions.
Free entry. Bring your appetite.

### How to join

Download Bo on iOS or Android, set up your profile in a minute, and start discovering.
Free forever to join. From the land, for you.

*Organised by Bo (Hellobo 2025 SL). contact@hellobo.eu*
"""


# --------------------------------------------------------------------------- #
# Document table: (document_type, title, content, [tags])
# --------------------------------------------------------------------------- #
DOCS = [
    ("note",     "Written question to the Commission: digital market access for small GI producers under Regulation (EU) 2024/1143", EP_WRITTEN_QUESTION, ["ep_question"]),
    ("note",     "Motion for a resolution on supporting small geographical-indication producers in the digital single market",        EP_RESOLUTION,        ["resolution"]),
    ("strategy", "Position paper: making the new EU geographical-indications regime work for small producers",                       POSITION_PAPER,       ["position_paper"]),
    ("note",     "Briefing for AGRI Committee Members: geographical indications, rural producers and digital market access",          MEP_BRIEFING,         ["mep_briefing"]),
    ("note",     "Talking points: Bo and the new EU geographical-indications regime",                                                TALKING_POINTS,       ["talking_points"]),
    ("note",     "Petition to the European Parliament: ensure the new GI rules empower, not burden, Europe's small producers",        EP_PETITION,          ["petition"]),
    ("note",     "Letter to an MEP: invitation to discover the new GI regime with Bo",                                               EMAIL_LETTER,         ["eu_email"]),
    ("note",     "One-pager: Bo and Europe's geographical indications",                                                              ONE_PAGER,            ["one_pager"]),
    ("note",     "Press release: Bo welcomes the new EU geographical-indications rules and calls for small-producer support",         PRESS_RELEASE,        ["press_release"]),
    ("note",     "Stakeholder map: the EU geographical-indications ecosystem",                                                       STAKEHOLDER_MAP,      ["stakeholder_map"]),
    ("analysis", "Impact assessment: effect of the 14 May 2026 GI labelling changes on micro and small producers",                   IMPACT_ASSESSMENT,    ["impact_assessment"]),
    ("note",     "Presentation: Bo, connecting Europe's GI producers with consumers",                                                PRESENTATION,         ["presentation"]),
    ("note",     "Event poster: Taste the Origin, a Bo GI discovery day",                                                            EVENT_POSTER,         ["event_poster"]),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Bo / Hellobo documents for a user.")
    parser.add_argument("--email", required=True, help="User email to seed.")
    parser.add_argument("--apply", action="store_true", help="Actually insert (default is dry-run).")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if not user:
            print(f"[ERROR] No user found for {args.email}")
            return

        print(f"[INFO] Seeding {len(DOCS)} document(s) for {args.email} ({user.id}).")
        for doc_type, title, _content, tags in DOCS:
            print(f"  - {tags[0]:18} | {doc_type:9} | {title[:70]}")

        if not args.apply:
            print("[DRY-RUN] Nothing inserted. Re-run with --apply.")
            return

        created = 0
        for doc_type, title, content, tags in DOCS:
            row = UserDocument(
                user_id=user.id,
                document_type=doc_type,
                title=title,
                content=content,
                policy_areas=POLICY,
                tags=tags,
                include_in_ai_context=True,
                is_private=True,
            )
            db.add(row)
            created += 1

        db.commit()
        print(f"[OK] Inserted {created} document(s) for {args.email}.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
