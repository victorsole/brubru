# The European Parliament's Governing Bodies: Bureau, Conference of Presidents, Quaestors and the Two Advisory Conferences

## QUICK FACTS
- **What this is**: the European Parliament runs its own internal affairs through four bodies, each with a distinct remit. Together they decide how Parliament is administered, how the plenary agenda is set, and how committees and delegations organise their work.
- **The four bodies**:
  1. **Bureau**: the President plus the 14 Vice-Presidents (the 5 Quaestors sit in an advisory capacity). Decides administrative, budgetary, staff and organisational matters.
  2. **Conference of Presidents**: the President plus the chairs of the political groups (one non-attached Member observes, without a vote). Sets the plenary agenda, decides committee competences and composition, organises Parliament's work and external relations.
  3. **Quaestors**: 5 Members elected to handle administrative and financial matters directly affecting other Members (offices, equipment, allowances-related services). Advisory members of the Bureau.
  4. **Conference of Committee Chairs** and **Conference of Delegation Chairs**: purely advisory bodies. The former groups the chairs of all standing/special committees; the latter groups the chairs of all standing interparliamentary delegations. Both may only recommend to the Conference of Presidents, not decide.
- **Legal basis**: European Parliament's Rules of Procedure (Rule 24: Composition of the Bureau; Rule 25: Duties of the Bureau; Rule 26: Composition of the Conference of Presidents; Rule 27: Duties of the Conference of Presidents; Rule 28: Duties of the Quaestors; Rule 29: Conference of Committee Chairs; Rule 30: Conference of Delegation Chairs). Full text: https://www.europarl.europa.eu/doceo/document/RULES-10-2024-07-16-TOC_EN.html (consolidated Rules of Procedure, term 10, as revised).
- **Term of office**: the President, 14 Vice-Presidents and 5 Quaestors are elected for a renewable 2.5-year term, with elections at the start and the midpoint of each 5-year parliamentary term. For term 10 (2024-2029), the first half runs from the constituent sitting (16 July 2024) to mid-January 2027; a mid-term election follows for the second half.
- **Current President (term 10, first half)**: Roberta Metsola (EPP, Malta), elected 16 July 2024.
- **Who chairs what**: the President chairs the Bureau and the Conference of Presidents. The Conference of Committee Chairs and Conference of Delegation Chairs each elect their own chair from among their members.
- **Official pages**: Bureau: https://www.europarl.europa.eu/about-parliament/en/organisation-and-rules/organisation/political-bodies ; Bureau members list: https://www.europarl.europa.eu/meps/en/organizations/bureau ; Conference of Presidents: https://www.europarl.europa.eu/about-parliament/en/organisation-and-rules/organisation/political-bodies ; College of Quaestors: https://www.europarl.europa.eu/at-your-service/en/be-heard/contact-a-mep/quaestors.

## 1. The Bureau: administration, budget, staff

**Composition (Rule 24)**: the President, the 14 Vice-Presidents, and the 5 Quaestors sitting in a consultative (advisory, non-voting) capacity. In a tied vote among the voting members, the President has the casting vote.

**Duties (Rule 25)**: the Bureau is responsible for the internal running of Parliament. Among its powers, it:
- Draws up Parliament's preliminary draft estimates of expenditure (the preliminary draft budget).
- Decides on matters of staff, organisation and administration, including the Secretariat-General's structure.
- Appoints the Secretary-General, who runs Parliament's administration.
- Decides on the organisation of sittings and can authorise committee or delegation meetings outside Parliament's three normal places of work (Brussels, Strasbourg, Luxembourg).
- Decides on funding for the European political parties and political foundations represented in Parliament.
- Lays down rules on Members' allowances and on the use of Parliament's buildings, IT and other resources.

Bureau minutes are translated into all official languages, printed and distributed to Members; any Member may put questions about the Bureau's activities. The Bureau typically meets once a month.

**Vice-Presidents' other role**: beyond sitting on the Bureau, the 14 Vice-Presidents chair plenary debates in the President's absence and can represent Parliament at ceremonies. Each Vice-President and Quaestor is given a specific portfolio by the President (e.g. relations with national parliaments, transparency, digitalisation). Order of precedence among Vice-Presidents follows the order in which they were elected (by votes received, or by age in case of a tie). See `ep_president_and_vice_presidents` for the office of the President specifically.

## 2. The Conference of Presidents: the political governing body

**Composition (Rule 26)**: the President of Parliament and the chairs of each political group (a group chair may arrange to be represented by another member of the group). The President invites one representative of the non-attached Members to attend, without the right to vote. Decisions are sought by consensus; where consensus fails, votes are weighted by the size of each political group. See `ep_political_groups_overview` for how group weight is calculated.

**Duties (Rule 27)**: the Conference of Presidents is Parliament's central political-organisational body. It:
- Takes decisions on the **organisation of Parliament's work** and on **matters of legislative planning**.
- Is the authority responsible for **relations with non-member countries and non-Union institutions and organisations**.
- Organises **structured consultation with European civil society**.
- Draws up the **draft agenda** and, after considering political groups' amendment requests, the **final draft agenda** for each part-session (plenary week), which Parliament then formally adopts at the opening of the sitting (Rule 158).
- Decides how **seats in the Chamber** are allocated among political groups and non-attached Members.
- Decides **committee competences** (which committee is "lead" on a dossier when jurisdiction is contested) and the **size/composition of committees and delegations**, respecting political-group proportionality.
- Authorises **own-initiative reports**, hearings, and delegations' missions and inter-parliamentary meetings (six-month programme).

## 3. Agenda-setting: how the Conference of Presidents shapes what gets voted, and when

This is the mechanism that most directly affects a policy professional's timeline:
1. **Draft agenda**: at its second-to-last meeting before a part-session, the Conference of Presidents adopts the draft agenda for that plenary week, listing which reports, debates and votes are scheduled.
2. **Amendment window**: political groups can request changes (add/remove an item, add a debate, change ordering).
3. **Final draft agenda**: at its last meeting before the part-session, the Conference of Presidents adopts the final draft agenda after considering those requests.
4. **Formal adoption**: Parliament adopts the agenda at the opening of the part-session (Rule 158); Members can propose amendments to the agenda itself at that point, subject to thresholds.

Because a report can only reach a plenary vote once it is on this agenda, and the Conference of Presidents controls both the ordering and the inclusion of items, **it effectively controls the tempo of EU lawmaking at the plenary stage**: a file whose committee report is ready but not yet scheduled by the Conference of Presidents will not be voted that part-session, regardless of committee readiness. This is separate from committee-level scheduling (handled by each committee's own bureau), see `ep_committees_overview` and `ep_plenary_how_it_works` for how a file moves from committee vote to plenary vote.

The Conference of Presidents also decides urgent procedure requests, the number and length of debates, and whether a matter proceeds "without debate" (Rule 27(2), for non-controversial texts subject to an objection window).

## 4. The Quaestors: administrative and financial matters affecting Members

**Composition and election (Rule 18, Rule 28)**: 5 Quaestors, elected by secret ballot after the President and Vice-Presidents, using the same 2.5-year renewable term. Election is by majority (absolute majority in the first two rounds, relative majority in the third if needed). Quaestors sit on the Bureau in an advisory capacity only; they do not vote there.

**Duties (Rule 28)**: the Quaestors are "responsible for administrative and financial matters directly concerning Members, in accordance with guidelines laid down by the Bureau, as well as for other tasks entrusted to them." In practice this covers matters such as Members' offices, equipment and general services, badges and access, and other member-facing administrative services. They can also propose amendments to rules the Bureau has adopted. The Quaestors (collectively the "College of Quaestors") generally meet about once a month.

**Distinction from the Bureau**: the Bureau decides the rules and the budget; the Quaestors apply and interpret those rules for individual Members' day-to-day administrative needs, and can propose changes to them.

## 5. The Conference of Committee Chairs (Rule 29): advisory, committee-facing

**Composition**: the chairs of all standing and special committees. It elects its own chair (chaired by the oldest Member present if that chair is absent).

**Role**: purely advisory. It "may make recommendations to the Conference of Presidents about the work of committees and the drafting of the agendas of part-sessions." The Bureau and the Conference of Presidents may also instruct it to carry out specific tasks (for example, coordinating positions on delegated-act objections across committees). It cannot itself decide the plenary agenda or committee competences: those decisions remain with the Conference of Presidents. See `ep_committees_overview` for the full list of term-10 committees.

## 6. The Conference of Delegation Chairs (Rule 30): advisory, delegation-facing

**Composition**: the chairs of all standing interparliamentary delegations. It elects its own chair; the chairs of the Foreign Affairs (AFET), Development (DEVE) and International Trade (INTA) committees participate as of right.

**Role**: also purely advisory. It "may make recommendations to the Conference of Presidents about the work of the delegations," prepares the draft six-month programme of inter-parliamentary meetings and missions (which the Conference of Presidents must authorise), and may be instructed by the Bureau or Conference of Presidents to carry out specific tasks.

## Why this matters to a policy professional

- **Timing intelligence**: if a report has cleared committee but a debate/vote has not been announced in a part-session's draft or final draft agenda, the Conference of Presidents has not yet scheduled it, even if the committee vote happened weeks earlier.
- **Jurisdiction disputes**: when it is unclear which committee should lead on a file (e.g. a proposal touching both ENVI and ITRE), the Conference of Presidents makes the binding call on committee competence, informed by any recommendation from the Conference of Committee Chairs.
- **Access and logistics**: questions about badges, office allocation, Member facilities and similar administrative matters go through the Quaestors, not the Bureau or the Conference of Presidents.
- **Budget and staffing changes**: any structural change to Parliament's administration, the Secretariat's organisation, or the preliminary budget originates in the Bureau. See `ep_secretariat_and_dgs` for how the Secretariat itself (the DGs, the Secretary-General) is organised beneath the Bureau's oversight.
- **Group weight in practice**: because the Conference of Presidents votes by group-weighted majority when consensus fails, the relative size of political groups (see `ep_political_groups_overview`) directly affects outcomes on agenda and committee-composition disputes.

## Accountability

Under Rule 32, minutes of the Bureau and the Conference of Presidents are translated into the official languages, printed and distributed to all Members, and any Member may put written questions to the President about the activities of these bodies.

## Cross-references
- `ep_president_and_vice_presidents`: the office of the President specifically, election procedure, and individual Vice-President portfolios.
- `ep_political_groups_overview`: how political groups are formed and how their size determines Conference of Presidents weighted votes.
- `ep_committees_overview`: the 26 term-10 committees, their remits, chairs and how the Conference of Committee Chairs feeds into agenda planning.
- `ep_plenary_how_it_works`: the full life of a plenary part-session, from draft agenda to final vote, and how a file moves from committee to plenary.
- `ep_rules_of_procedure`: the consolidated Rules of Procedure that establish all four bodies (Rules 24-30).
- `ep_secretariat_and_dgs`: the administrative Secretariat-General and Directorates-General that implement Bureau decisions.
