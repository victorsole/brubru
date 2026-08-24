# EU Payment Services Law: PSD2 today, PSD3 and the PSR tomorrow

## QUICK FACTS
- **PSD2 is the law in force**: Directive (EU) 2015/2366 on payment services in the internal market. It governs BOTH consumer conduct rules (authorisation of transactions, liability, refunds) AND the licensing and supervision of payment institutions.
- **The reform splits those two halves.** PSD3 (a directive) keeps only licensing and prudential supervision. The **PSR** (a regulation) takes all conduct and liability rules, including consumer redress. A regulation applies directly and identically in all 27 Member States, which removes the national divergence that PSD2's directive form created.
- **Status as of 19 August 2026: NOT in force.** Both files sit at **"Awaiting Council's 1st reading position"**. The ECON committee approved the texts agreed in interinstitutional negotiations on **5 May 2026**. Indicative plenary sitting date: **14 December 2026**.
- **Entry into force is not application.** Entry into force is 20 days after publication in the Official Journal. The PSR then **applies 21 months later**; PSD3 has the same 21-month transposition deadline. The verification-of-payee liability regime waits **27 months**. Realistic effective date: **2028 to 2029**.
- **PSD2 is not repealed until 21 months after PSD3 enters into force**, so PSD2 and its national transpositions remain fully applicable for years.
- **Verification of Payee is ALREADY binding**, but through a different instrument: Article 5c of Regulation (EC) 260/2012, inserted by the Instant Payments Regulation (EU) 2024/886. Euro-area PSPs had to comply by **9 October 2025**. This is the single most important operative rule in force today.
- **Strong Customer Authentication (SCA)** and the duty to run **transaction-monitoring mechanisms** come from Commission Delegated Regulation (EU) 2018/389, Article 2, in force since 14 September 2019.
- Rapporteurs: **René Repasi (S&D)** for the PSR, **Morten Løkkegaard (Renew)** for PSD3. Lead committee ECON.
- Spanish transposition of PSD2: **Real Decreto-ley 19/2018**, **Real Decreto 736/2019** and **Orden ECE/1263/2019**.

## WHY THE SPLIT MATTERS

PSD2 is a directive. Each Member State transposed it separately, and national supervisors and courts read it differently. The Advocate General of the Court of Justice noted in March 2026 that payment service providers in several Member States had, by default, adopted the practice of refusing immediate refunds by alleging customer fault, and that the EU legislature amended the rule precisely to stop that.

Moving conduct rules into a regulation removes that margin. From application day, the refund rules are the same text everywhere, with no transposition layer in between.

## THE FOUR INSTRUMENTS IN FORCE TODAY

1. **Directive (EU) 2015/2366 (PSD2)** - consent (Art 64), user obligations (Art 69), notification and the 13-month long-stop (Art 71), burden of proof on the provider (Art 72), refund by end of the next business day (Art 73), payer liability and the EUR 50 cap (Art 74).
2. **Regulation (EC) 260/2012 as amended by Regulation (EU) 2024/886** - Article 5c, verification of payee. Binding on euro-area PSPs since 9 October 2025. Article 5c(1)(d) expressly covers payment channels that do NOT require the payer to enter an IBAN or a payee name, which is how mobile-number schemes such as Bizum work. Article 5c(8) creates a refund duty on the payer's PSP where the breach caused a defectively executed transaction.
3. **Commission Delegated Regulation (EU) 2018/389** - SCA and secure communication. Article 2 requires transaction-monitoring mechanisms that detect unauthorised or fraudulent transactions, analysing each payment against the user's normal usage and taking account of at least the amount of each transaction and known fraud scenarios.
4. **Directive (EU) 2019/713** - the criminal-law framework on fraud and counterfeiting of non-cash means of payment.

## WHAT THE PSR WILL ADD

- **Article 59, liability for impersonation fraud.** Where a consumer is manipulated by a third party pretending to be the consumer's own payment service provider, using communication channels attributed to that provider, and this leads to subsequent fraudulent AUTHORISED payment transactions, the PSP must refund the full amount. Conditions: the consumer notifies the PSP and reports the fraud to the police, both without undue delay. Recital 80a confirms the channels include the provider's telephone number, email address, website and mobile application.
- Article 59(2): 15 business days from notification and the police report to refund or to justify a refusal.
- Article 59(4): burden of proof on the PSP, which must also invite the consumer to explain the events before concluding gross negligence, and cannot treat silence as proof. The consumer is not expected to provide information beyond what such a consumer can reasonably be expected to have.
- Article 59(-1): PSPs must have robust technical safeguards preventing fraudsters replicating their communication channels.
- **Article 59a(5)**: electronic communications providers must detect and prevent use of their services for impersonation fraud, including manipulation of calling line identification.
- Article 50 (payee name and identifier discrepancies), Article 56 (liability for unauthorised transactions), Article 57 (liability for incorrect application of the matching verification service, applicable at 27 months).

## THE GAP THE REFORM CLOSES

PSD2 regulates the operation the customer never ordered. It does not regulate the operation the customer ordered while deceived into believing the instruction came from the bank. That gap is why such cases currently turn on national case law about vitiated consent, and why PSR Article 59 was written.

Until the PSR applies, the arguments available for deception cases are: the verification-of-payee duty in force since October 2025, the transaction-monitoring duty, and national case law.

## COMMON MISTAKES TO AVOID

- Do not present the PSR as applicable law. It is not, and will not be before 2028.
- Do not confuse entry into force with application. They are 21 months apart.
- Do not say PSD2 is being repealed imminently. It stands for years yet.
- Do not treat verification of payee as part of the PSR. It is already binding through the Instant Payments Regulation.

## RELATED GUIDES
- `eu_payment_fraud_consumer_redress` - what a defrauded customer can actually claim, and how.
- `target_services_payment_systems` - the Eurosystem infrastructure behind instant payments.
- `dora_digital_operational_resilience` - ICT risk obligations that overlap with PSP security duties.
