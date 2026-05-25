# How the European Parliament Is Run — Its Governing Bodies

## QUICK FACTS
- **What this is**: the political and administrative bodies that organise Parliament's work — the **President**, the **Conference of Presidents**, the **Bureau**, the **Quaestors**, the **Conference of Committee Chairs (CCC)** and the **Conference of Delegation Chairs**. Together they set the agenda, run the institution and coordinate committees and delegations.
- **Why Brubru cares**: these bodies decide what reaches the plenary agenda, how committee competence disputes are settled, and how Parliament engages the Commission and Council — context for "why is this file scheduled now?" and "who decides X in the EP?".
- **Body codes** (used in EP data/meetings): Conference of Presidents = **BCPR**, Bureau = **BURO**, Quaestors = **QUE**, Conference of Committee Chairs = **PRCO**, Conference of Delegation Chairs = **PRDE**.
- **Source**: `europarl.europa.eu/committees/en/about/conference-of-committee-chairs` + the EP Rules of Procedure.

## The President
Elected by MEPs at the constitutive session for a **renewable 2.5-year term** (half a parliamentary term). The President directs Parliament's activities, chairs plenary sittings, represents Parliament in external relations and legal matters, and signs adopted legislative acts into the Official Journal alongside the Council. Nominations: by a political group or by ≥36 MEPs (one-twentieth). See `ep_plenary_how_it_works.md`.

## Conference of Presidents (BCPR)
- **Who**: the **President + the leaders (chairs) of the political groups**. Non-attached MEPs send a delegate (without voting rights).
- **What it does**: the EP's main political steering body. It **draws up the plenary agenda**, decides the timetable and organisation of Parliament's work, allocates committee/delegation responsibilities and seats, and handles relations with the other EU institutions, national parliaments and non-EU countries. Decides on the composition and competences of committees, delegations and committees of inquiry.

## Bureau (BURO)
- **Who**: the **President + 14 Vice-Presidents**, with the **Quaestors** sitting as members in an advisory capacity. Elected for renewable 2.5-year terms.
- **What it does**: responsible for **administrative, staff and organisational matters** — Parliament's internal rules, the preliminary draft budget (estimates), the organisation of the Secretariat, and rules for political groups and MEPs.

## Quaestors (QUE)
- **Who**: MEPs (currently five) elected by Parliament.
- **What they do**: handle **administrative and financial matters that directly concern Members** — office allocation, equipment, access, and the rules MEPs must follow in their day-to-day work.

## Conference of Committee Chairs (PRCO / CCC)
- **Who**: the **Chairs of all standing and special committees**; meets on **Tuesdays of the Strasbourg part-sessions**; its own Chair is elected for a 2.5-year mandate.
- **What it does** (from the EP's own description):
  - **Plenary agenda input**: submits to the Conference of Presidents a **monthly recommendation** for the next part-session's draft agenda, plus a **monthly screening** of whether draft legislation respects the Treaty rules on delegated and implementing acts.
  - **Coordination between committees**: a forum for horizontal issues; adopts common approaches/guidelines; **mediates competence conflicts** between committees and handles cooperation requests.
  - **Legislative dialogue**: prepares Parliament's contribution to the **Commission's annual Work Programme** by listing priorities per field; holds an **annual joint meeting with the College of Commissioners**; meets the **Council Presidency** several times a year to align on priorities.

## Conference of Delegation Chairs (PRDE)
- **Who**: the Chairs of all standing interparliamentary delegations.
- **What it does**: makes recommendations to the Conference of Presidents about the work of delegations and may draw up a draft annual calendar of interparliamentary meetings. See `ep_intergroups_and_delegations.md`.

## How a file gets onto the plenary agenda (why this matters)
Committee adopts a report → the **Conference of Committee Chairs** recommends it for a part-session → the **Conference of Presidents** sets the final **plenary agenda** → plenary debates and votes. So scheduling is a political decision of these bodies, not automatic.

## How Brubru uses this
- **Chat**: answer "who sets the EP plenary agenda?", "what is the Conference of Presidents/Bureau/Quaestors?", "who resolves committee turf wars?".
- **Predictions / Calendar**: agenda-setting by BCPR/CCC explains *when* a file is scheduled; the CCC's delegated/implementing-acts screening flags scrutiny risk.

## Cross-references
- `european_parliament_structure.md` — the EP overview these bodies sit within
- `ep_committees_overview.md` — the committees the CCC coordinates
- `ep_intergroups_and_delegations.md` — the delegations PRDE coordinates
- `ep_plenary_how_it_works.md` — the plenary whose agenda these bodies set
- `european_parliament_powers.md` — the powers exercised through these bodies
- `docs/api/eu_parliament_data_access.md` — body codes (BCPR/BURO/QUE/PRCO/PRDE) in EP data
