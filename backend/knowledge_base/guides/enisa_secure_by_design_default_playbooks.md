# ENISA Secure by Design and Secure by Default Playbooks (22 playbooks for SMEs)

## QUICK FACTS
- **What it is:** a practical set of **exactly 22 playbooks** from ENISA (the EU Agency for Cybersecurity) for **small and medium-sized manufacturers** of products with digital elements. Based on ENISA's PDF "Secure by Design and Default Playbook: A Practical Guide to Secure by Design and Default Principles for SMEs" (version 1, July 2026), republished as checklists at github.com/enisaeu/enisa-sbd-playbook (licence **CC-BY-4.0**, last updated 31 July 2026). PDF: https://www.enisa.europa.eu/sites/default/files/2026-07/ENISA_Secure_By_Design_and_Default_Playbook_v1.pdf
- **Split:** **14 Secure by Design** playbooks (6 Architectural Foundations + 8 Operational Integrity) and **8 Secure by Default** playbooks (4 Default Hardening + 4 Guided Protection). Secure by Design = protection built in from conception; Secure by Default = the product ships in the most secure configuration reasonably possible.
- **Every playbook has the same five parts:** Principle, Objective, Checklist, Minimum evidence, Release gate (a tick-box list to clear before a release ships).
- **It is guidance, NOT law, and NOT a legal mapping:** ENISA states it is "a practical starting point rather than an exhaustive or prescriptive implementation framework" and "does not provide legal guidance". Progressive adoption "does not suggest delaying applicable requirements or controls, particularly those arising from legal obligations, including under the CRA", which "take precedence". ENISA does NOT publish a clause-by-clause mapping to the Cyber Resilience Act: do not claim that a playbook satisfies a CRA requirement.
- **Intended readers:** software developers and engineers, technical product managers, SME security leads, system architects; "particularly relevant to SME manufacturers developing products with digital elements".
- **Deep-dive on the law it sits beside:** Cyber Resilience Act explainer https://brubru.beresol.eu/eucanon/2024-2847_cra/ (see guide `cyber_resilience_act`).

## The 22 playbooks
**Secure by Design: Architectural Foundations (6):** 1 Trust boundaries and threat modelling; 2 Least privilege; 3 Strong identity and authentication architecture; 4 Attack surface minimisation; 5 Defence in depth; 6 Open design (security must not depend on secrecy of the design).
**Secure by Design: Operational Integrity (8):** 7 Life-cycle management; 8 User-centric design; 9 Secure coding and verification practices; 10 Logging, monitoring and alerting; 11 Configuration and change management; 12 Incident response and recovery; 13 Vulnerability and patch management; 14 Supply-chain controls.
**Secure by Default: Default Hardening (4):** 15 Minimisation of default services; 16 Restrictive initial access; 17 Secure communication by default; 18 Unique device identity and secrets by default.
**Secure by Default: Guided Protection (4):** 19 Mandatory security onboarding; 20 Automated maintenance and updates; 21 Transparent security posture; 22 Secure recovery and ownership life cycle.

## Progressive adoption (the suggested order)
1. **Establish context and priorities:** playbook 1 (threat modelling) first, to decide scope for the rest.
2. **Foundational engineering baseline:** playbooks 9 (secure coding), 10 (logging), 13 (vulnerability and patch management), 14 (supply chain), 16, 17, 18 and 20.
3. **Broaden:** the remaining applicable playbooks, according to product context and risk. Availability-sensitive products may need playbook 12 early; products with reset, ownership transfer or decommissioning may need playbook 22 early. The sequence is illustrative: later does not mean less important.

## What the release gates ask for (examples read in the playbooks)
- **Vulnerability and patch management (13) and Supply-chain controls (14):** an **SBOM or dependency inventory** generated and stored for the release; dependency and static-analysis scans run for the release, with critical and high findings fixed or covered by a documented exception that has an owner and an expiry date.
- **Restrictive initial access (16) and Unique device identity (18):** no shared or default credentials in production builds; unique credentials and a unique cryptographic identity per device or instance.
- **Automated maintenance and updates (20):** security updates enabled by default, deliverable independently of feature updates, cryptographically verified before installation, and failed updates must not leave the product unusable.
- **Secure communication by default (17):** external communications encrypted and authenticated from the first connection; plain-text protocols disabled.
- **Mandatory security onboarding (19):** the product cannot enter normal operation before the critical security set-up is completed.

## Where it fits
Think of it as an engineering checklist that supports compliance work under the **Cyber Resilience Act** (security by design and by default, vulnerability handling, updates) and sits beside ENISA's other tools (the European Vulnerability Database, the CSIRT incident taxonomy). Which CRA obligation applies to a given product, and from which date, comes from the Regulation itself, not from these playbooks.

## FAQ
**Are the ENISA Secure by Design playbooks mandatory?** No. They are voluntary guidance. Legal obligations (for example under the CRA) apply regardless and take precedence.
**Do they give presumption of conformity with the CRA?** No. A presumption of conformity under the CRA is tied to harmonised standards (and, where adopted, EU cybersecurity certification schemes), not to this guidance.
**Can I reuse the playbooks?** The GitHub text is under CC-BY-4.0: reuse with attribution to ENISA.
**How many playbooks are there?** Exactly 22: 14 Secure by Design and 8 Secure by Default.
