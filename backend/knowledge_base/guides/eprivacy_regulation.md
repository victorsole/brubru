# ePrivacy: Directive, Proposed Regulation, and Current Status

## QUICK FACTS
- ePrivacy Directive: Directive 2002/58/EC, as amended by Directive 2009/136/EC
- CELEX: 32002L0058 (consolidated: 02002L0058-20091219)
- ePrivacy Regulation proposal: COM(2017) 10, procedure 2017/0003(COD)
- Proposal date: 10 January 2017
- Status: WITHDRAWN by Commission on 11 February 2025 (2025 Work Programme)
- Reason for withdrawal: "No foreseeable agreement; proposal outdated in view of some recent legislation"
- EP position: Adopted October 2017
- Council mandate: Agreed 10 February 2021 (after 4 years of negotiations)
- Trilogues: Never concluded; Council and Parliament positions too far apart
- Current law: ePrivacy Directive 2002/58/EC (as amended) remains in force, transposed into national law
- Digital Omnibus (COM(2025) 837): Proposes interim amendments to ePrivacy Directive (cookies, consent)
- CJEU judgment C-654/23 (13 November 2025): Clarified "soft opt-in" exception for freemium services
- Legal basis: Article 16 TFEU (data protection), Article 114 TFEU (internal market)
- Relationship to GDPR: Lex specialis (ePrivacy rules override GDPR where they apply to the same subject matter)
- Related guides: dsa_enforcement, csam_regulation_online, digital_omnibus_package
- Related legislation: GDPR (32016R0679), EECC (32018L1972), DSA (32022R2065), CSAM derogation (32021R1232)

## Overview

The ePrivacy framework governs the confidentiality of electronic communications, cookies/tracking, direct marketing, and metadata processing in the EU. It operates as "lex specialis" to the GDPR -- where both frameworks apply to the same processing, ePrivacy takes precedence.

The current law is the **ePrivacy Directive (2002/58/EC)**, as amended by Directive 2009/136/EC (the "Cookie Directive"). It is transposed into 27 different national laws, creating fragmentation.

The Commission proposed an **ePrivacy Regulation** (COM(2017) 10) in January 2017 to replace the Directive with a directly applicable Regulation. After 8 years of negotiations, the Commission **withdrew the proposal on 11 February 2025**, citing no foreseeable agreement and the proposal being outdated.

The ePrivacy Directive remains in force. The Digital Omnibus on Data and Cybersecurity (COM(2025) 837) proposes interim amendments to modernise the Directive's cookie and consent provisions.

## ePrivacy Directive 2002/58/EC (In Force)

### Structure

| Article | Title | Content |
|---------|-------|---------|
| Art. 1 | Scope and aim | Privacy and confidentiality in electronic communications sector |
| Art. 2 | Definitions | Traffic data, location data, communication, value added service, electronic mail |
| Art. 3 | Services concerned | Processing of personal data in publicly available electronic communications services and public communications networks |
| Art. 4 | Security | Providers must take appropriate measures to safeguard security; breach notification to national authority (as amended by 2009/136/EC) |
| Art. 5 | Confidentiality of communications | Prohibition on listening, tapping, storage, surveillance without consent; **Art. 5(3): cookie consent** -- storing/accessing information on terminal equipment requires prior informed consent |
| Art. 6 | Traffic data | Must be erased or made anonymous when no longer needed for transmission; may be processed for billing (with consent for marketing/value-added services) |
| Art. 7 | Itemised billing | Subscriber right to non-itemised bills to protect privacy of calling parties |
| Art. 8 | Calling/connected line identification | Right to suppress CLI presentation; override for emergency services |
| Art. 9 | Location data | May only be processed when made anonymous or with consent; must be able to withdraw consent at any time; must be informed before consent |
| Art. 10 | Exceptions | Member States may restrict scope for national security, defence, public security, criminal investigation |
| Art. 11 | Automatic call forwarding | Right to stop automatic forwarding by a third party |
| Art. 12 | Directories | Consent required for inclusion in public directories |
| Art. 13 | Unsolicited communications (direct marketing) | **Opt-in required** for electronic direct marketing; **"soft opt-in" exception** (Art. 13(2)): existing customers can receive marketing for similar products if given opt-out at collection and in each message; natural persons only |
| Art. 14 | Technical features and standardisation | Reference to technical implementation measures |
| Art. 15 | Application of certain provisions of GDPR/95/46 | Judicial remedies, liability, sanctions |
| Art. 15a | Implementation and enforcement | National authorities must have investigation and enforcement powers |

### Key Provisions for Messaging Platforms (e.g. Discord)

1. **Art. 5(1) -- Confidentiality of communications:** Member States must ensure confidentiality of communications and related traffic data transmitted via public communications networks and publicly available electronic communications services. Listening, tapping, storage, or other kinds of interception or surveillance prohibited without consent. **This is the provision that the CSAM temporary derogation (Reg. 2021/1232) derogates from.**

2. **Art. 5(3) -- Cookies/tracking:** Storing information or gaining access to information stored in subscriber/user terminal equipment requires prior informed consent. Exceptions: (a) sole purpose of carrying out transmission; (b) strictly necessary for providing an information society service explicitly requested. **Discord's web cookies, tracking pixels, and local storage all require consent under this provision.**

3. **Art. 6 -- Traffic data:** Must be erased or anonymised when no longer needed for transmission. Processing for other purposes (marketing, value-added services) requires consent. Relevant to Discord's message metadata, connection logs, and user activity data.

4. **Art. 13 -- Direct marketing:** Opt-in required for unsolicited electronic communications for direct marketing. "Soft opt-in" for existing customers' similar products. Relevant to Discord's email marketing to EU users (Nitro promotions, server recommendations).

### Scope Limitation

The Directive applies to "publicly available electronic communications services" in "public communications networks." The EECC (Directive 2018/1972) expanded the definition to include NI-ICS providers like Discord, but the ePrivacy Directive's scope was written before NI-ICS existed. This creates legal uncertainty about which ePrivacy provisions apply to Discord-type services vs. traditional telecoms.

## Proposed ePrivacy Regulation COM(2017) 10 (WITHDRAWN)

### Why It Was Proposed

The Commission proposed replacing the Directive with a Regulation to:
- Ensure uniform application across all 27 Member States (no national transposition)
- Extend scope explicitly to OTT/NI-ICS providers (WhatsApp, Discord, Telegram, etc.)
- Align with the GDPR (adopted 2016, applied 2018)
- Modernise cookie consent rules
- Address new technologies (IoT, machine-to-machine communications)

### Key Differences Between Directive and Proposed Regulation

| Issue | ePrivacy Directive (in force) | Proposed ePrivacy Regulation (withdrawn) |
|-------|------------------------------|----------------------------------------|
| **Legal instrument** | Directive (requires national transposition; 27 different implementations) | Regulation (directly applicable, uniform across EU) |
| **Scope -- NI-ICS** | Applies to "publicly available electronic communications services" in "public communications networks"; NI-ICS coverage uncertain | Explicitly covers NI-ICS (Art. 2(1)): "electronic communications data processed in connection with the provision and the use of electronic communications services" regardless of whether number-based or number-independent |
| **Territorial scope** | EU establishment of provider | Applies when end-users are in the EU, regardless of provider establishment (similar to GDPR Art. 3) |
| **Confidentiality** | Art. 5(1): prohibition on interception/surveillance | Extended to cover electronic communications content AND metadata; interference without consent prohibited except for specific permitted purposes |
| **Metadata** | Art. 6 (traffic data): erased/anonymised when no longer needed for transmission; consent for other uses | Broader "metadata" concept; allowed for: billing, fraud detection, security; with consent: traffic monitoring, epidemiology; compatible purpose processing with safeguards |
| **Cookie consent** | Art. 5(3): prior informed consent required (with narrow exceptions for transmission/service necessity) | Users need "genuine choice"; browser/software settings can serve as consent mechanism; whitelisting permitted to avoid "consent fatigue"; access dependency on cookies allowed if equivalent non-cookie option exists |
| **Direct marketing** | Art. 13: opt-in; soft opt-in for existing customers | Similar framework but with updated definitions; clearer rules for B2B marketing |
| **Machine-to-machine** | Not addressed | Explicitly covered: IoT devices, smart meters, connected cars |
| **Penalties** | Left to Member States | GDPR-aligned: up to EUR 20 million or 4% of global annual turnover |
| **Supervisory authority** | National authorities (often telecoms regulators) | National data protection authorities (same as GDPR) -- one-stop-shop mechanism |
| **Enforcement** | Fragmented across national telecoms regulators | Centralised under GDPR enforcement framework; consistency mechanism |

### Key Similarities

| Issue | Both instruments |
|-------|-----------------|
| **Core principle** | Confidentiality of electronic communications is a fundamental right |
| **Consent basis** | Prior informed consent as primary legal basis for processing communications data |
| **Direct marketing** | Opt-in required for unsolicited electronic communications; soft opt-in exception for existing customers |
| **Lex specialis to GDPR** | Both function as lex specialis to the GDPR for electronic communications |
| **Security obligations** | Providers must take appropriate technical and organisational measures |
| **Breach notification** | Required (Directive via 2009 amendment; Regulation aligned with GDPR 72h) |
| **National security exceptions** | Member States may restrict scope for national security, defence, public security |
| **User rights** | Right to information, consent withdrawal, complaint to supervisory authority |

### Why the Regulation Failed (8 Years of Negotiations)

1. **Cookie consent:** Industry wanted lighter rules; privacy advocates wanted stricter consent. The Council spent years debating whether browser settings could substitute for specific consent.

2. **Metadata processing:** Telecoms operators wanted broader rights to process metadata for commercial purposes. Privacy advocates opposed any weakening of the consent requirement.

3. **NI-ICS scope:** Some Member States wanted to exempt certain NI-ICS providers from the most burdensome obligations. Others wanted uniform coverage.

4. **Relationship to GDPR:** Difficulty in drawing the line between general data protection (GDPR) and specific electronic communications privacy (ePrivacy).

5. **Political turnover:** The proposal survived three Commission mandates, multiple Council presidencies, and two EP terms. Each new presidency attempted different compromise texts.

6. **Overtaken by events:** The DSA (2022), AI Act (2024), Data Act (2023), and Digital Omnibus (2025) addressed some of the same issues through different instruments.

### Timeline of the Failed Proposal

| Date | Event |
|------|-------|
| 10 January 2017 | Commission proposal COM(2017) 10 |
| 26 October 2017 | EP adopted position (1st reading) |
| 2017-2021 | Council negotiations under 8 successive presidencies |
| 10 February 2021 | Council agreed negotiating mandate (general approach) |
| 2021-2024 | No trilogue progress; fundamental disagreements persist |
| 11 February 2025 | Commission withdraws proposal (2025 Work Programme) |

## Current Situation (Post-Withdrawal)

### What Remains in Force

The ePrivacy Directive 2002/58/EC (as amended by 2009/136/EC) remains in force. National transpositions continue to apply. This means:

- Fragmented implementation across 27 Member States
- Legal uncertainty about NI-ICS coverage
- Outdated cookie consent framework generating "consent fatigue"
- No GDPR-aligned penalty framework (penalties left to Member States)

### Digital Omnibus Interim Amendments (COM(2025) 837)

The Commission's November 2025 Digital Omnibus on Data and Cybersecurity proposes amendments to the ePrivacy Directive to address the most urgent gaps:

- ~60% of cookies would no longer require consent
- Lawful processing without consent for: transmission, service provision, audience measurement by media providers, website/app usage statistics, security maintenance
- Mandatory single-click consent/refusal buttons
- 6-month re-ask prohibition
- Machine-readable cookie preference standards
- Browser extensions for automated consent management (opt-out as default)
- Estimated savings: EUR 820 million/year (private sector) + EUR 320 million/year (public sector)

### CJEU Judgment C-654/23 (13 November 2025)

The Court clarified that the "soft opt-in" exception under Art. 13(2) of the ePrivacy Directive applies to freemium services:
- Free user accounts can trigger the exception if email obtained during service signup
- Recipient must be an established customer
- Marketing must concern the controller's similar offerings
- Clear opt-out opportunity must be given at collection and in each message
- This broadens direct marketing possibilities for platforms like Discord without requiring explicit prior consent

## Discord-Specific Analysis

### Discord's NI-ICS Classification

Discord is a number-independent interpersonal communications service under the EECC (Directive 2018/1972, Art. 2(7)). The ePrivacy Directive was written before NI-ICS existed, creating uncertainty:

- **Art. 5(1) (confidentiality):** Applies to Discord's messages, voice, and video -- but through national transposition, creating fragmented coverage
- **Art. 5(3) (cookies):** Applies to Discord's web client and cookies regardless of NI-ICS classification
- **Art. 6 (traffic data):** Applies to Discord's message metadata, connection logs, and user activity data -- but scope for NI-ICS uncertain in some Member States
- **Art. 13 (direct marketing):** Applies to Discord's Nitro promotions and email marketing to EU users

### Impact of ePrivacy Regulation Withdrawal

The withdrawal means Discord continues to operate under 27 different national transpositions of the ePrivacy Directive, with varying interpretations of:
- Whether Discord's messaging qualifies as a "publicly available electronic communications service"
- What metadata processing is permitted beyond transmission purposes
- What penalties apply for non-compliance (ranging from administrative fines to criminal sanctions depending on Member State)

The Digital Omnibus amendments, if adopted, would partially modernise the cookie regime but would not resolve the fundamental NI-ICS scope uncertainty.

## Sources

- ePrivacy Directive 2002/58/EC (consolidated version with 2009/136/EC amendments)
- COM(2017) 10: Proposal for an ePrivacy Regulation
- european-eprivacy-regulation.com
- Commission 2025 Work Programme (withdrawal notice)
- CJEU judgment C-654/23 (13 November 2025)
- Digital Omnibus on Data and Cybersecurity COM(2025) 837
