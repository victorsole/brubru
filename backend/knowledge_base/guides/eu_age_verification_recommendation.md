# EU-wide Age Verification Recommendation (28 April 2026)

## QUICK FACTS
- **Title**: Commission Recommendation on establishing a common framework for EU-wide Age Verification technologies
- **Source**: OJ(2026) 2564 final, 28 April 2026, Item 10 (College of Commissioners agenda)
- **Adopted**: Tuesday 28 April 2026 (College in Strasbourg)
- **Type**: Commission Recommendation (non-binding instrument under Article 292 TFEU). Sets technical and legal expectations; transposed in practice via DSA Article 28 enforcement and Member State age-assurance regimes.
- **Lead Commissioner**: Henna Virkkunen (EVP for Tech Sovereignty, Security and Democracy)
- **Lead DG**: DG CNECT (Communications Networks, Content and Technology)
- **Predecessor / companion document**: Commission **age verification "blueprint"** (technical specification published December 2024) and the **EU age verification app announced "technically ready" on 15 April 2026** by President von der Leyen
- **Companion infrastructure**: **EUDI Wallet** (Regulation (EU) 2024/1183) — the age verification app uses the same technical specifications, focused on age-proving only (transitional tool ahead of full EUDI Wallet rollout)
- **Privacy architecture**: **Zero-Knowledge Proof (ZKP) cryptography** — proves a single fact ("user is over 18") without transmitting any identifying information to the requesting platform. Compatible with GDPR data minimisation (Article 5(1)(c)).

## What the Recommendation does

The Recommendation establishes a common technical and legal framework that Member States, online platforms, and providers should use when deploying age verification across the EU single market. It crystallises three previously fragmented strands:

1. **DSA child-protection enforcement (Regulation (EU) 2022/2065, Article 28)**: VLOPs and VLOSEs must put in place "appropriate and proportionate measures" to protect minors. The Recommendation defines what age verification "appropriate and proportionate" looks like.
2. **GDPR data minimisation (Article 5(1)(c))**: age verification must collect strictly the minimum data necessary. ZKP is the recommended baseline.
3. **EDPB Statement on Age Assurance** (joint Article 29 / EDPB output, 2025): risk-based proportionate approach.

The Recommendation positions the **EU Age Verification app + EUDI Wallet** as the reference standard for platforms required to verify age, providing the EU-level alternative to national-government or commercial age-assurance solutions.

## Scope of platforms expected to apply it

- **Pornography platforms** — DSA Article 28 + national online-safety regimes (e.g. France's ARCOM scheme, UK Online Safety Act for cross-Channel comparison)
- **Online gambling** — national gambling laws + DSA layered on top
- **Potentially social media** — politically debated; some Member States (FR, IT, EL) are pushing for mandatory age gates on social platforms for users under 16 / 15
- **App stores and OS-level age signals** — tied to DMA Article 6 interoperability obligations
- **Online video-sharing platforms** — AVMSD Article 28b protections for minors

## Key technical specifications

- **App distribution**: Apple App Store + Google Play Store (already published spring 2026 in pilot Member States)
- **Identity binding**: national eID (where available), EUDI Wallet (rollout-dependent), or fallback document scanning + liveness check
- **Persistence model**: device-side, not server-side. The app generates fresh ZKP proofs per request rather than storing tokens.
- **Cross-border interoperability**: a French citizen accessing a Belgian-hosted platform uses the same proof; the Recommendation harmonises the proof exchange protocol.

## Member State angle

Member States retain the competence to set the **age threshold** for specific types of content (typically 18 for pornography/gambling; 13/14/15/16 for social media — varies). The Recommendation harmonises the **technology** for age proving, not the **age** to be proved.

## Cross-link with other Brubru guides

- `digital_markets_act.md` — gatekeepers + interoperability
- `dsa_enforcement.md` — Article 28 minor protection enforcement; this Recommendation operationalises that obligation
- `csam_regulation_online.md` — age verification is one of three pillars (alongside detection orders + grooming detection) in the wider child-safety legislative package
- `digital_fairness_act.md` — pending Digital Fairness Act will codify aspects currently in Recommendation form
- `ai_act_regulation.md` — Article 5(1)(b) prohibition on AI exploiting vulnerabilities of minors crosses with age-verification design

## How this flows through Brubru answers

Whenever a user asks about:
- "age verification EU"
- "EU age 18 / 16 / 15 / 14 / 13 verification"
- "online platforms age check"
- "EUDI Wallet age proof"
- "age assurance vs age verification" (different legal concepts — assurance is risk-based, verification is binary; the Recommendation uses verification for the reference standard but acknowledges assurance for lower-risk contexts)

→ Brubru should lead with the 28 April 2026 Recommendation as the operational anchor, then cite the DSA Article 28 + GDPR Article 5(1)(c) + EUDI Wallet Reg 2024/1183 as the legal stack.

## Forecast

- **H2 2026**: pilot rollout in 5 Member States (DK, FR, EL, IT, ES expected)
- **2027**: full EUDI Wallet rollout, age verification app deprecated as a stand-alone (functionality folds into EUDI Wallet)
- **DSA enforcement actions**: Commission expected to use the Recommendation as the operational benchmark when assessing VLOPs' Article 28 compliance during 2026-2027 systemic-risk audits
- Possible legislative successor: the **Digital Fairness Act** (pending) may codify the Recommendation into binding obligations for online platforms targeting minors
