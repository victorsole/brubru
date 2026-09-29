# EU Infringement Procedures: how the Commission enforces EU law, and the latest decisions

## QUICK FACTS

- **What it is**: the procedure by which the **European Commission** takes a Member State to task for failing to apply EU law, under **Article 258 TFEU**. It runs in stages: **letter of formal notice** (the Commission asks the Member State to explain itself), **reasoned opinion** (a formal request to comply), then **referral to the Court of Justice of the European Union (CJEU)**. Most cases close before the Court.
- **Two different "reasoned opinions"**: in an infringement case it is the Commission's formal request to a Member State to comply (Art. 258 TFEU). A NATIONAL PARLIAMENT's reasoned opinion is something else: an objection that a Commission proposal breaches subsidiarity (Protocol No 2 to the Treaties). Say which one is meant.
- **Two routes to money**: under **Article 260(2) TFEU**, if a Member State does not comply with a Court judgment, the Commission can go back to the Court and ask for a lump sum and/or daily penalty payments. Under **Article 260(3) TFEU**, when a Member State has failed to **notify its transposition of a directive**, the Commission can ask for financial penalties already in the FIRST referral. The register labels these non-communication cases "Formal notice Art. 258-260(3) TFEU".
- **Brubru holds the Commission's infringement register**: **62,766 decisions on 25,814 cases** (December 1987 to 24 September 2026), including **8,981 reasoned opinions** and **2,837 referrals to the Court**. API: `/api/v2/commission/infringements` (cases, decisions, statistics, press releases).
- **The Commission adopts decisions in batches.** Some dates carry the full package (formal notices, reasoned opinions and referrals: e.g. 8 July 2026, 169 decisions incl. 45 reasoned opinions and 12 referrals; 4 June 2026, 111 incl. 12 and 6). Others carry only letters of formal notice for late transposition (e.g. 14 July 2026, 247; 24 September 2026, 156).

## Latest: 24 September 2026, 156 letters of formal notice

The register records **156 letters of formal notice** dated 24 September 2026 and **no reasoned opinions or referrals** on that date: **127** for failure to notify transposition (Art. 258-260(3) TFEU), covering **all 27 Member States**, and **29** other formal notices (Art. 258 TFEU) covering 21. Every one concerns a directive whose transposition deadline has passed:

| Directive (official title, shortened) | CELEX | Member States notified | Lead DG |
|---|---|---|---|
| Directive (EU) 2024/1785, industrial emissions (amending Directive 2010/75/EU) | 32024L1785 | 27 | Environment |
| Directive (EU) 2024/1788, internal markets for renewable gas, natural gas and hydrogen | 32024L1788 | 26 | Energy |
| Directive (EU) 2024/1712, trafficking in human beings (amending Directive 2011/36/EU) | 32024L1712 | 20 | Migration and Home Affairs |
| Directive (EU) 2024/1799, promoting the repair of goods ("right to repair") | 32024L1799 | 18 | Justice and Consumers |
| Delegated Directive (EU) 2026/74, adding domestic local space heaters to Annex II of the repair directive | 32026L0074 | 18 | Justice and Consumers |
| Directive (EU) 2024/1640, mechanisms to prevent the use of the financial system for money laundering or terrorist financing | 32024L1640 | 18 | Financial Stability (FISMA) |
| Directive (EU) 2024/1711, electricity market design (amending Directives 2018/2001 and 2019/944) | 32024L1711 | 18 | Energy |
| Delegated Directive (EU) 2025/2062, new psychoactive substances in the definition of "drug" | 32025L2062 | 8 | Migration and Home Affairs |
| Directive (EU) 2026/192, cobalt limits in toys (Directive 2009/48/EC) | 32026L0192 | 3 | Internal Market (GROW) |

- **Germany** received **4**: industrial emissions (INFR(2026)0552), trafficking (INFR(2026)0551), anti-money laundering (INFR(2026)0550) and the gas and hydrogen market directive (INFR(2026)0553). Greens MEP Anna Cavazzini publicised them on social media on 28 September; the numbers above come from the register.
- **Most letters**: Cyprus, the Netherlands and Romania, 8 each.
- A letter of formal notice is the FIRST step. Say "the Commission opened infringement proceedings" or "sent a letter of formal notice", NOT "fined" or "took to court": nothing in this batch is a referral or a penalty.

## Reading a case

Each case has an infringement number (INFR(YYYY)NNNN), the Member State, the lead DG and each decision with its date and stage. A non-communication case usually closes once the Member State notifies its transposition measures; the Commission decides at a later package whether to escalate.

## Related guides

- `cjeu_structure_and_procedures` (the Court's side of Articles 258-260)
- `better_regulation_enforcement_communication` (the Commission's enforcement policy)
- `anti_trafficking_directive_recast_2024` (Directive 2024/1712)

## Sources

- Commission infringement register, decisions dated 24 September 2026 (served by `/api/v2/commission/infringements/decisions`)
- Directive titles: Publications Office, Cellar (CELEX as listed)
- Treaty on the Functioning of the European Union, Articles 258 and 260
