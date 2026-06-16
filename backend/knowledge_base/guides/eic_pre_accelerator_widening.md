# EIC Pre-Accelerator — Widening Hop-On Facility

## QUICK FACTS
- A **Widening / Hop-On Facility** instrument: helps deep-tech start-ups from EU Widening countries reach the investment readiness needed for the EIC Accelerator.
- **No 2026 call** (instrument is paused for the 2026 EIC Work Programme cycle).
- **Next call: 5 May 2027** opening, **18 November 2027** deadline.
- 2027 grant range: **EUR 500,000 – EUR 1,000,000** per beneficiary.
- 2027 funding rate: **70% of eligible costs**.
- Project duration: **max 2 years**.
- Mono-beneficiary scheme (single applicant SME).
- Topic ID prefix: `HORIZON-WIDERA-*-ACCESS-*` (Brubru's bucket filter narrows by `title ILIKE '%EIC%'` to exclude non-EIC HORIZON-WIDERA rows such as Twinning / Teaming / Excellence Hubs).
- Implemented under Pillar III's WIDERA "Widening Participation and Spreading Excellence" component.

## Eligibility — Widening countries

Applicants must be established in a Horizon Europe Widening country:

**Member States**: Bulgaria, Croatia, Cyprus, Czechia, Estonia, Greece, Hungary, Latvia, Lithuania, Malta, Poland, Portugal, Romania, Slovakia, Slovenia.

**Associated Countries with Widening status**: Albania, Armenia, Bosnia and Herzegovina, Faroe Islands, Georgia, Kosovo, Moldova, Montenegro, Morocco, North Macedonia, Serbia, Tunisia, Türkiye, Ukraine (and others as the list evolves).

**Outermost regions** of the EU also qualify (Açores, Madeira, Canary Islands, Réunion, Mayotte, Guadeloupe, Martinique, French Guiana, Saint-Martin).

Applicants must be **single SMEs** (per EU Recommendation 2003/361/EC).

## What it funds

Pre-Accelerator (Hop-On Facility) supports activities that enhance:
- **Business readiness** — go-to-market strategy, commercial validation, customer discovery
- **Investor readiness** — pitch deck quality, financial model, due diligence preparation
- **Technology readiness** — last-mile TRL maturation before Accelerator submission

The goal is to bring a Widening-country deeptech start-up to the maturity needed to **succeed in the EIC Accelerator** application — closing the participation gap that has historically left Widening countries underrepresented in EIC Accelerator winners.

## Application process (based on 2025 call structure, 2027 to be confirmed)

Single-stage:
1. Submit proposal at the Funding & Tenders Portal by the deadline (18 November 2027 for the 2027 call).
2. Eligibility + admissibility check by EISMEA.
3. Remote evaluation by ≥3 experts.
4. Ranking + selection.
5. GAP (Grant Agreement Preparation) — 3-5 months.
6. Grant Agreement signature under the Horizon Europe MGA.
7. Pre-financing disbursement.

## Funding terms

- **Grant**, NOT lump sum (cost-based reimbursement at 70% funding rate).
- Up to EUR 1M.
- Max 2 years duration.
- Eligible activities: business development, customer engagement, IP / FTO, prototype refinement, regulatory + certification work, investor outreach.

## What's NOT eligible

- Applicants from non-Widening MS / non-Widening Associated Countries
- Mid-caps (>250 employees)
- Consortium applications
- Activities that would already qualify for Accelerator (the Pre-Accelerator is preparatory, not commercial scale-up)

## Templates required (based on 2025 call)

- Application Form Part A (Submission Service)
- Application Form Part B (template DOCX from the 2025 topic page; new template will be published with the 2027 call on 5 May 2027)
- Ethics Self-Assessment

## After the Pre-Accelerator

The expected pathway is **direct application to EIC Accelerator** once the Pre-Accelerator project has delivered. Pre-Accelerator beneficiaries who later apply to the Accelerator may benefit from:
- Strengthened pitch deck and proposal
- Validated commercial traction
- Better investor pipeline
- Stronger team profile

## Historic context

- 2024 call: closed (Widening Hop-On Facility — €25M total)
- 2025 call: closed (transition to the 2025 EIC Work Programme rebrand)
- **2026: NO call** (instrument paused for the 2026 EIC Work Programme)
- 2027 call: opens 5 May 2027, deadline 18 November 2027

## Useful URLs

- Pre-Accelerator instrument page: https://eic.ec.europa.eu/eic-funding-opportunities/eic-pre-accelerator_en
- 2027 Work Programme (when published): https://eic.ec.europa.eu/eic-2026-work-programme_en (link will roll to 2027 version)
- Widening countries definition: https://research-and-innovation.ec.europa.eu/strategy/strategy-research-and-innovation/our-digital-future/european-research-area_en

## How Brubru helps Pre-Accelerator applicants

Tenderator should:
- Flag this instrument as "next call 5 May 2027" in any Widening-country user's saved view
- Surface the 2025 template as reference until the 2027 template is published
- Filter `HORIZON-WIDERA-*-ACCESS-*` rows to surface ONLY those with "EIC" in title (the bucket map in `backend/api/tenderator.py` already does this)
Hand-offs:
- Chat: "Am I in a Widening country?" / "Should I wait for the Pre-Accelerator or go straight to Accelerator?"
- EU Law Comply: same regulatory checks as Accelerator (AI Act / MDR / etc.)
- MEUB Documents → future Tender Docs: Part B drafts using 2025 template as starter
