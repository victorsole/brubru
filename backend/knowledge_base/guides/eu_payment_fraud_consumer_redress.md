# Payment Fraud: what a defrauded bank customer can claim, and how

## QUICK FACTS
- **Verification of Payee is a NAME-to-IBAN MATCH CHECK.** The bank compares the payee name the customer typed against the name that actually holds the destination account, and reports whether they match, before the payment is authorised. The duty begins and ends with that comparison: no document is examined, no person is identified, and nothing in it belongs to the customer due diligence regime. State the obligation as a match check on a name against an account number.
- **The bank bears the burden of proof.** If the customer denies authorising a transaction, it is the payment service provider that must prove the transaction was authenticated, correctly recorded, and unaffected by a technical failure. The mere record of the payment instrument being used is NOT enough to prove authorisation, nor fraud or gross negligence by the customer. PSD2 Article 72; Spain, Real Decreto-ley 19/2018 Article 44.
- **Unauthorised transactions must be refunded by the end of the next business day (D+1).** The ONLY exception is reasonable suspicion of fraud by the customer, communicated in writing to the competent national authority. PSD2 Article 73(1); Spain, RDL 19/2018 Article 45.1.
- **Gross negligence must be more than mere negligence.** PSD2 recital 72 requires a significant degree of carelessness. The bank must prove it.
- **Verification of Payee is binding since 9 October 2025.** Article 5c of Regulation (EC) 260/2012, inserted by Regulation (EU) 2024/886. The bank must let the payer validate who really owns the destination account BEFORE authorising. Article 5c(1)(d) expressly covers channels that require neither IBAN nor payee name. Article 5c(8) creates a refund duty where breach causes a defective execution. **This obligation applies whether or not the transaction was authorised, which is what makes it the strongest argument available today.**
- **Banks must monitor transactions.** Delegated Regulation (EU) 2018/389 Article 2: mechanisms detecting unauthorised or fraudulent transactions, analysed against the user's normal usage, taking account of at least the amount of each transaction and known fraud scenarios.
- **The decisive distinction**: an operation the customer never ordered (strong regime, D+1) versus an operation the customer ordered while deceived (contested; turns on vitiated consent and on the verification-of-payee duty).
- Spain, complaint deadlines: the bank's customer service must answer within **15 business days**, one month maximum in exceptional cases (RDL 19/2018 Article 69). Long-stop for notifying an unauthorised transaction: **13 months** (Article 43).

## THE THREE BUCKETS

Sort every disputed euro into one of three buckets before arguing anything.

**A. Operations the customer never ordered.** Card-not-present charges made with stolen card data, transfers initiated by the fraudster with stolen credentials. Full D+1 refund regime, burden on the bank, EUR 50 cap at most and often not even that.

**B. Operations the customer ordered while deceived.** The customer pressed the buttons, believing the instruction came from the bank. PSD2 does not regulate this. The arguments are: consent obtained by impersonation is not real and informed consent; the verification-of-payee duty was breached; transaction monitoring failed.

**C. Money that never left the customer's own holdings.** Funds moved to the customer's own card or another of their own products. Not a loss to a third party. Recover administratively by asking for the credit balance back, not by litigating. Always check for this: fraudsters often have the victim load their own card so they can spend it later.

## CJEU: C-70/25, Advocate General Rantos, 5 March 2026

Reference from the District Court of Koszalin, Poland. A customer was phished, the fraudster made an unauthorised payment, and the bank refused to refund alleging gross negligence.

**Proposed answer**: Articles 73(1) and 74(1) of PSD2 preclude a payment service provider from refusing an immediate refund by alleging the payer's gross negligence.

Reasoning worth citing:
- The two articles govern **two distinct stages**: immediate refund first, allocation of liability later.
- The **only** exception to immediate refund is suspicion of the payer's own fraud, notified in writing to the national authority.
- Article 73(1) is **fully harmonised**; Member States may not add exceptions.
- If the bank later establishes gross negligence, **the bank must sue the customer** to recover.
- Footnote 22 records that PSPs in several Member States refuse refunds by default on this ground, and that the legislature amended Article 73(1) precisely to stop that practice.

**Status: pending.** Only the Opinion is on file; no judgment. An Advocate General's Opinion does not bind the Court. Cite it as conclusiones, never as a judgment. Distinguished from **Veracash (C-665/23, 1 August 2025)**, which concerned a customer who notified late.

## SPANISH CASE LAW

- **Tribunal Supremo, 9 April 2025** (Ibercaja, SIM swapping, EUR 56,474.63). Use of credentials is not automatically consent; consent must be real and informed. Burden on the bank. Gross negligence must be "algo mas que la mera negligencia". The bank is also liable for failing to react to prior risk signals such as multiple transfers at unusual hours for large amounts. Contract clauses exonerating the bank for illegitimate access are void.
- **Juzgado de Primera Instancia num. 8 de Murcia, 28 September 2025** - condemned **BBVA** to refund EUR 5,977 plus interest and costs. Calls and messages simulating the bank; the customer transferred her own funds. The court extended the Supreme Court doctrine beyond phishing to someone who disposes of funds "de forma equivocada por engano o estafa, de tal forma que si supiera la verdad no lo haria", because "la verdadera voluntad del usuario de banca es no mover el dinero de su cuenta". Also: "No es de recibo que lleguen transferencias a cuentas corrientes con beneficiarios que son distintos al titular de la cuenta." First instance, appealable.
- **Audiencia Provincial de Valencia, 4 June 2025** - vishing, call simulating the bank's cybersecurity department, EUR 5,000. Sophisticated fraud creating a reasonable appearance of authenticity; the bank proved neither gross negligence nor how the data was compromised.
- **Audiencia Provincial de Asturias, 30 October 2025** - EUR 3,948.71 against Bankinter. The court expressly valued that the victim reported to the police the day after the events.
- **Audiencia Provincial de Madrid, 20 May 2022** - EUR 5,000 against Banco Santander, for failing to adopt sufficient measures such as active alerts against multiple consecutive withdrawals.

## WHAT TO ASK THE BANK IN WRITING

The single most useful request, because banks rarely answer it well:

> For each transfer, what result did the verification-of-payee service return: what account holder name did the beneficiary's provider return, was it a match, a close match or a mismatch, and what warning was displayed before the payment was authorised?

Also request: strong-authentication records with proof of dynamic linking to the specific amount and payee; whether transaction monitoring raised any alert and what was done; and whether the bank has notified the national authority in writing of reasonable grounds to suspect fraud by the customer.

## SPAIN: THE COMPLAINT ROUTE

1. **Bank's customer service (SAC)** - 15 business days, one month maximum. RDL 19/2018 Article 69.
2. **Banco de Espana, Departamento de Conducta de Entidades** - free, electronic filing, requires a prior SAC complaint. Not binding on the bank, but persuasive and useful evidence later.
3. **Civil courts** - juicio verbal up to EUR 6,000, juicio ordinario above. Lawyer and procurador compulsory above EUR 2,000. Contractual claims prescribe in five years (Civil Code Article 1964.2).
4. Criminal complaint: Spanish Criminal Code Article 249 (computer-enabled fraud), possibly Article 197 for the misappropriation of personal data.

## TELECOM ANGLE (SPAIN)

**Orden TDF/149/2025** (Plan Antiestafas) obliges operators, since 7 March 2025, to block calls presenting numbers not assigned by the CNMC and calls of international origin spoofing Spanish numbering. Request the call detail record as evidence.

## WHAT NOT TO DO

- Do not claim the PSR as applicable law. It is not in force and will not be before 2028.
- Do not assume a scheme label in a statement settles the legal category: an entry labelled "Bizum" may be documented on the bank's own transfer advice as a **SEPA instant credit transfer**, which puts it squarely inside the verification-of-payee obligation.
- Do not ask the beneficiary's bank to disclose the account holder's identity. They cannot; that goes through police and courts.
- Do not overstate the loss. Deduct any amount that stayed within the customer's own products.

## RELATED GUIDES
- `eu_payment_services_psd2_psd3` - the regime and the reform timeline.
- `target_services_payment_systems` - instant payments infrastructure and the VoP deadlines.
