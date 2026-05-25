# Data Retention / ePrivacy Derogation Extension (Regulation 2021/1232)

## QUICK FACTS
- Current Regulation: Regulation (EU) 2021/1232 of the European Parliament and of the Council of 14 July 2021 on a temporary derogation from certain provisions of Directive 2002/58/EC as regards the use of technologies by providers of number-independent interpersonal communications services for the processing of personal and other data for the purpose of combating online child sexual abuse
- CELEX: 32021R1232
- EUR-Lex: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32021R1232
- Adopted: 14 July 2021
- Expiry: 3 August 2024 (already extended once by Reg 2024/1307 to 3 April 2026)
- Current extension: Regulation (EU) 2024/1307 -- extended derogation to 3 April 2026
- **Procedure: [2025/0429(COD)]** -- Amending Regulation (EU) 2021/1232 as regards the extension of its period of application. Commission proposal 19 December 2025.
- **OEIL status (per Brubru procedure API, as of 20 April 2026): CLOSE_TO_ADOPTION**. Lead committee LIBE.
- **LATEST (23 April 2026)**: LIBE draft report "Amending Regulation (EU) 2021/1232 as regards the extension of its period of application" [2025/0429(COD)] re-surfaced on EP committees portal during Week 17 Group Week. Confirms procedure remains in committee stage; plenary vote expected late April / May 2026 given 3 April 2026 derogation expiry risk. Procedural urgency: derogation **already expired 3 April 2026** unless extension adopted in time; voluntary CSAM scanning by OTT providers technically in legal limbo.
- **LATEST (Monday 18 May 2026, Strasbourg plenary week)**: LIBE draft report on 2025/0429(COD) re-surfaced on the LIBE committee portal again. The Strasbourg plenary 19-22 May is the most plausible adoption window given the derogation has now been expired more than 6 weeks (since 3 April 2026). Status remains CLOSE_TO_ADOPTION per Brubru procedure API. Source: EP committees portal scrape, 18 May 2026.
- **LATEST (Wednesday 6 May 2026)**: LIBE draft report 2025/0429(COD) re-surfaced on the EP committees portal during the 4-8 May committee week, confirming procedure remains active in committee stage. The procedural urgency is now structural — the derogation expired 3 April 2026 and voluntary CSAM scanning by OTT providers has been in legal limbo for over a month. LIBE committee vote expected late May / early June 2026; plenary vote earliest June 2026 Strasbourg. Cross-link `csam_regulation_online` (permanent regulation 2022/0155(COD)).
- **OEIL key events (authoritative)**:
  - 19 December 2025: Legislative proposal (Commission)
  - 27 January 2026: Legislative proposal milestone
  - 5 February 2026: Committee report
  - 10 February 2026: Committee report
  - 2 March 2026: Committee referral
  - 3 March 2026: Vote in committee (LIBE)
  - 11 March 2026: Committee report (final)
- **IMPORTANT -- do NOT invent plenary vote numbers or T-document IDs for this file.** As of 22 April 2026, OEIL does not record a plenary vote on the extension. Procedure is in LIBE committee stage heading to plenary. Do not cite specific vote tallies, T10-XXXX/2026 numbers, or specific rapporteur quotes unless independently verified against doceo.
- Rapporteur: TBC -- check OEIL procedure file for rapporteur assignment
- Politico EU (21 April 2026): "Das Gespenst Vorratsdatenspeicherung ist zurück" (German) -- flags return of data retention debate amid LIBE proceedings
- Purpose: Allow providers of "number-independent interpersonal communications services" (e.g., Gmail, WhatsApp, Messenger, Signal web) to voluntarily scan user content for known child sexual abuse material (CSAM) and grooming, despite the confidentiality obligations of the ePrivacy Directive (2002/58/EC)
- Relation to permanent regulation: temporary bridge until the **permanent CSAM Regulation (COM(2022) 209, procedure 2022/0155(COD))** is adopted
- Legal basis: Articles 16 + 114 TFEU
- EP committee: LIBE (Civil Liberties, Justice and Home Affairs)
- Responsible DG: DG HOME (Migration and Home Affairs)
- Responsible Commissioner: Magnus Brunner (Internal Affairs and Migration)

## What This Regulation Does

The ePrivacy Directive (Directive 2002/58/EC) requires providers of electronic communications services to ensure confidentiality of communications. This includes encryption, traffic data confidentiality, and prohibition on intercepting content.

Before Regulation 2021/1232:
- Voluntary scanning for CSAM by providers of "number-independent interpersonal communications services" (OTT services like Gmail, WhatsApp, Messenger) was operating in a **legal grey area**
- European Electronic Communications Code (EECC, Directive (EU) 2018/1972) brought OTT services under ePrivacy rules from December 2020
- This meant existing voluntary CSAM scanning (e.g., Meta's PhotoDNA use on Facebook Messenger, Google's CSAM detection on Gmail) became technically non-compliant with ePrivacy

Regulation 2021/1232 created a **temporary derogation** allowing OTT providers to continue voluntary CSAM scanning while the permanent CSAM Regulation (COM(2022) 209) was negotiated. Key safeguards:
- Only scanning for known CSAM (hash-based PhotoDNA), not content analysis for new CSAM
- Grooming detection permitted with additional safeguards (no audio/voice scanning)
- Reporting obligations to National Contact Points + EU Centre (once established)
- Strict data protection: limited retention, EDPB oversight
- User notification when content removed
- Right to effective remedy

## Why Extension Is Needed (2025/0429(COD))

The permanent CSAM Regulation [2022/0155(COD)] is **deadlocked in Council**:
- Council adopted general approach 12 December 2024 (Belgian presidency)
- EP LIBE committee still negotiating position (multiple political groups split on client-side scanning obligations)
- Trilogue not yet formally opened
- If temporary derogation expires 3 April 2026 without permanent regulation adopted, OTT providers must **cease voluntary CSAM scanning** under ePrivacy compliance -- creating a **detection gap** estimated at 500k+ CSAM reports per year lost

The Commission's proposal (December 2025) extends Regulation 2021/1232 for a further period (target: 3 August 2027 or until permanent regulation takes effect, whichever is earlier). The extension is procedurally urgent given the 3 April 2026 expiry.

## LIBE Procedure Timeline

| Date | Event |
|------|-------|
| December 2025 | Commission proposes COM(2025) XXX amending Reg 2021/1232 |
| February 2026 | LIBE referral confirmed, rapporteur appointed |
| 22 April 2026 | LIBE draft report visible in EP committees portal (Week 17 Group Week) |
| TBC May 2026 | Tabling deadline for amendments |
| TBC May-June 2026 | LIBE vote |
| TBC June 2026 | Plenary vote target (urgency: 3 April 2026 expiry already passed or close to) |
| TBC late-2026 | Council adoption (likely in parallel with permanent CSAM Reg trilogue) |

## Political Controversy

### Privacy Advocates Opposition
- EDRi, EDPS, EDPB have all expressed concerns about mass scanning
- Signal and Threema have threatened to withdraw from EU market if permanent regulation includes client-side scanning mandates
- European Court of Human Rights judgments on bulk interception (Big Brother Watch v UK, Centrum for Rattvisa v Sweden) raise fundamental-rights bar
- CJEU jurisprudence: La Quadrature du Net (Joined Cases C-511/18, C-512/18, C-520/18) restricted data retention obligations

### Child Safety Advocates Support
- Missing Children Europe, ECPAT, NCMEC data: OTT platform scanning detected 32 million CSAM items in 2023 (US + EU combined)
- EU Centre on Child Sexual Abuse (proposed under permanent regulation) would coordinate reporting
- Law enforcement agencies (Europol, national child protection units) rely on hash-matched reports

### Compromise Positions
- "Voluntary scanning only" (status quo of 2021/1232) -- broad support
- "Mandatory scanning with judicial order" -- compromise floor discussed in LIBE
- "Mandatory client-side scanning" (original Commission proposal for permanent regulation) -- contested

## Vorratsdatenspeicherung ("Data Retention") Link

The Politico EU piece (21 April 2026, in German) titled "Das Gespenst Vorratsdatenspeicherung ist zurück" ("the ghost of data retention is back") links the 2021/1232 extension debate to the broader German political memory of:
- The 2010 Bundesverfassungsgericht judgment striking down blanket data retention (1 BvR 256/08)
- The 2014 CJEU Digital Rights Ireland judgment (Joined Cases C-293/12, C-594/12) annulling the Data Retention Directive (2006/24)
- The 2020 CJEU La Quadrature du Net judgments restricting general and indiscriminate retention
- SPD-Grune-FDP coalition (2021-2025) opposition to new German data retention law
- CDU-CSU/SPD coalition (2025-) plans to reintroduce IP address retention

The framing suggests that the extension of 2021/1232 -- while narrowly about CSAM scanning -- is seen in German political discourse as part of a broader creep toward data retention. LIBE debate on the extension is expected to be thorny on this basis.

## Related Guides
- `csam_regulation_online.md` (permanent regulation 2022/0155(COD))
- `eprivacy_regulation.md` (ePrivacy modernisation 2017/0003(COD), also deadlocked)
- `gdpr_data_protection.md`
- `eu_privacy_fundamental_rights.md`
- `la_quadrature_du_net_jurisprudence.md` (if present)

## Sources
- Regulation (EU) 2021/1232: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32021R1232
- Regulation (EU) 2024/1307 (first extension): https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1307
- EP LIBE committee page: https://www.europarl.europa.eu/committees/en/libe
- OEIL procedure 2025/0429(COD): https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2025/0429(COD)
- Politico EU 21 April 2026 (German): "Das Gespenst Vorratsdatenspeicherung ist zurück"
