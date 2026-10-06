# CSIRT Reference Security Incident Taxonomy (RSIT)

## QUICK FACTS
- **What it is:** the **Reference Security Incident Taxonomy (RSIT)**, the classification scheme the **EU CSIRTs community** uses to label cybersecurity incidents the same way across countries. Created by **ENISA and TF-CSIRT** (the Reference Security Incident Taxonomy Working Group, approved 26 September 2018; the need was agreed at the 51st TF-CSIRT meeting, The Hague, 15 May 2017). It builds on the earlier eCSIRT.net taxonomy.
- **Exactly 11 top-level classes and 39 incident types** (current version 1003; repository last updated 13 May 2026; licence **CC0**, public domain): **Abusive Content, Malicious Code, Information Gathering, Intrusion Attempts, Intrusions, Availability, Information Content Security, Fraud, Vulnerable, Other, Test.**
- **Examples per class:** Abusive Content (spam, harmful speech); Malicious Code (infected system, C2 server, malware distribution); Information Gathering (scanning, sniffing, social engineering); Intrusion Attempts (exploitation of known vulnerabilities, login attempts, new attack signature); Intrusions (privileged or unprivileged account compromise, application compromise, system compromise, burglary); Availability (denial of service, distributed denial of service, misconfiguration, sabotage, outage); Information Content Security (unauthorised access to or modification of information, data loss, leak of confidential information); Fraud (unauthorised use of resources, copyright, masquerade, phishing); Vulnerable (weak cryptography, DDoS amplifier, potentially unwanted accessible services, information disclosure, vulnerable system).
- **Voluntary reference scheme, NOT a legal form:** the NIS 2 Directive does NOT oblige entities to use it and it is NOT the Article 23 significant-incident report. It is a shared vocabulary for CSIRTs.
- **Where it is now recommended:** ENISA's **Interoperability Guidelines v1.0 for Cross-Border Cyber Hubs** (published 10 April 2026 under Article 6(4) of the Cyber Solidarity Act) tell hubs to start with cyber threat intelligence sharing based on "the EU based taxonomy already adopted by the CSIRTs Network", i.e. this taxonomy.
- **Source:** github.com/enisaeu/Reference-Security-Incident-Taxonomy-Task-Force (human-readable `humanv1.md`, machine-readable MISP machine-tag file `machinev1`, and a mapping to MITRE ATT&CK).
- **Related guides:** `nis2_directive` (incident reporting, Article 23), `cyber_solidarity_act` (Cross-Border Cyber Hubs), `enisa_european_cybersecurity_agency`.

## FAQ
**Which taxonomy do EU CSIRTs use to classify incidents?** The ENISA and TF-CSIRT Reference Security Incident Taxonomy: 11 classes, 39 incident types.
**Is the taxonomy mandatory under NIS 2?** No. It is a voluntary shared vocabulary; NIS 2 reporting follows Article 23.
**Can I reuse it?** Yes: CC0.
**Is it the same as the ENISA Threat Landscape categories or the EU vulnerability database?** No. It classifies incidents; the vulnerability database lists vulnerabilities.
