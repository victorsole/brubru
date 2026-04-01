# Cohesion Policy Audit

## QUICK FACTS
- Topic: Cohesion policy audit framework, error rate methodology, Arachne risk scoring, assurance chain
- Scope: Shared management auditing for 8 EU funds (ERDF, ESF+, Cohesion Fund, JTF, EMFAF, AMIF, ISF, BMVI)
- Framework regulation: Common Provisions Regulation (EU) 2021/1060
- Responsible DGs: DG REGIO, DG EMPL
- Audit body: Joint Audit Directorate for Cohesion (DAC), 5 geographic sectors + 1 horizontal
- Materiality threshold: <2% acceptable, 2-5% concerning, >5% material (payment interruption/suspension), >10% critical
- Flat-rate corrections: 5% (minor), 10% (significant), 25% (serious), 100% (total failure)
- Arachne: Data-mining risk scoring tool (green/yellow/orange/red), mandatory from 2021-2027 for certain checks
- Annual assurance deadline: 15 February (MA declaration, AA audit opinion, accounts)
- Commission review deadline: 31 May (acceptance of accounts)
- Key legal references: Regulation (EU) 2021/1060, Delegated Regulation (EU) 2021/1702, ERDF/CF Regulation (EU) 2021/1058, ESF+ Regulation (EU) 2021/1057, JTF Regulation (EU) 2021/1056

Guide for Joint Audit Directorate for Cohesion (DAC) auditors and shared management control officers covering the audit framework, error rate methodology, Arachne risk scoring, and assurance chain.

## Shared Management Framework

### How Shared Management Works

Under shared management, the Commission delegates implementation to Member States while retaining overall responsibility:

| Level | Actor | Role |
|-------|-------|------|
| **EU** | European Commission (DG REGIO, DG EMPL) | Policy design, regulatory framework, audit and assurance, payments |
| **National** | Managing Authority (MA) | Programme implementation, project selection, first-level checks |
| **National** | Certifying Authority (CA) / Accounting Function | Expenditure certification, accounts preparation |
| **National** | Audit Authority (AA) | Independent system and operations audits |
| **EU** | European Court of Auditors (ECA) | External audit, Statement of Assurance (DAS) |

### Common Provisions Regulation (EU) 2021/1060

The CPR establishes common rules for 8 EU funds under shared management:
- ERDF (European Regional Development Fund)
- ESF+ (European Social Fund Plus)
- Cohesion Fund
- JTF (Just Transition Fund)
- EMFAF (European Maritime, Fisheries and Aquaculture Fund)
- AMIF (Asylum, Migration and Integration Fund)
- ISF (Internal Security Fund)
- BMVI (Border Management and Visa Instrument)

## Audit Architecture

### DAC Structure (Joint Audit Directorate for Cohesion)

| Sector | Coverage | Key Responsibilities |
|--------|----------|---------------------|
| **DAC.1** | Italy, Malta, Slovenia, Croatia, Finland, Denmark, Sweden | System audits + operations audits |
| **DAC.2** | France, Belgium, Luxembourg, Netherlands, Ireland | System audits + operations audits |
| **DAC.3** | Germany, Austria, Czechia, Slovakia, Hungary | System audits + operations audits |
| **DAC.4** | Spain, Portugal, Greece, Cyprus | System audits + operations audits |
| **DAC.5** | Poland, Romania, Bulgaria, Lithuania, Latvia, Estonia | System audits + operations audits |
| **DAC.A** | Horizontal: methodology, coordination, IT tools | Audit methodology development, ECA liaison |

### Audit Types

#### System Audits

| Element | Detail |
|---------|--------|
| **Purpose** | Assess whether management and control systems function effectively |
| **Frequency** | At least once per programming period; repeat if significant deficiencies found |
| **Scope** | Key requirements (KR1-KR15 for 2021-2027): designation criteria, selection procedures, management verifications, accounting, reporting |
| **Rating scale** | Category 1 (works well), Category 2 (works but improvements needed), Category 3 (works partially, substantial improvements needed), Category 4 (essentially does not work) |
| **Output** | System audit report with findings and recommendations |

#### Operations Audits

| Element | Detail |
|---------|--------|
| **Purpose** | Verify the legality and regularity of expenditure declared to the Commission |
| **Sample** | Statistical sampling from expenditure declared in accounting year |
| **Methodology** | MUS (Monetary Unit Sampling) or stratified random sampling |
| **Verification** | Check supporting documents (invoices, contracts, timesheets, delivery certificates), verify public procurement compliance, check eligibility of costs |
| **Error classification** | Systemic, random, or anomalous errors |
| **Output** | Individual audit observation letters + annual control report |

## Error Rate Methodology

### Calculation

The **total error rate** represents the estimated percentage of irregular expenditure in the population:

```
Total Error Rate = (Sum of errors in sample / Total expenditure in sample) x Projection factor
```

### Error Types

| Type | Description | Example |
|------|-------------|---------|
| **Quantified** | Financial impact can be precisely calculated | Ineligible expenditure (EUR 50,000 staff costs outside eligible period) |
| **Non-quantified** | Irregularity exists but financial impact cannot be precisely determined | Missing audit trail, incomplete documentation |
| **Systemic** | Error results from a system weakness affecting multiple operations | Failure to apply public procurement rules |
| **Random** | One-off error in specific operation | Arithmetic mistake in cost claim |
| **Anomalous** | Non-representative error (excluded from projection) | Fraud by single beneficiary (not indicative of system failure) |

### Materiality Threshold

| Error Rate | Assessment | Commission Action |
|------------|-----------|------------------|
| **< 2%** | Acceptable | Reasonable assurance; normal payment flow |
| **2-5%** | Concerning | Enhanced monitoring; targeted system audits; possible warning letter |
| **> 5%** | Material | Interruption or suspension of payments; financial corrections |
| **> 10%** | Critical | Suspension of payments; possible programme designation review |

### Financial Impact Calculation

For each error:
1. Identify the irregular expenditure amount
2. Calculate the EU co-financing rate
3. Apply the co-financing rate to get the EU financial impact
4. Sum all errors in the sample
5. Project to the population using the appropriate statistical method

## Arachne Risk Scoring Tool

### Overview

Arachne is a data-mining and enrichment tool that cross-references EU-funded project data with external databases to identify fraud indicators and operational risks.

### Data Sources

| Source | Data Type |
|--------|-----------|
| **Programme data** | Beneficiaries, projects, contracts, expenditure from managing authorities |
| **External databases** | Company registries, insolvency records, press articles, PEP (Politically Exposed Persons) lists, sanctions lists |
| **Orbis (Bureau van Dijk)** | Company financial data, ownership structures |

### Risk Categories

| Category | Indicators | Example |
|----------|-----------|---------|
| **Procurement risk** | Single bidder, short bidding periods, contract splitting | Contract awarded without competition |
| **Fraud risk** | Beneficiary connected to sanctioned entities, shell companies, PEPs | Company shares directors with known fraud cases |
| **Conflict of interest** | Ownership links between beneficiary and contractor | Subcontractor owned by beneficiary's family |
| **Eligibility risk** | Company created shortly before application, no employees | SPV created solely for EU funding |
| **Concentration risk** | Single beneficiary receiving multiple grants | Same entity in many projects across programmes |
| **Reputation risk** | Negative press, legal proceedings, insolvency | Beneficiary in bankruptcy proceedings |

### Risk Scoring

| Score | Meaning | Recommended Action |
|-------|---------|-------------------|
| **Green** | Low risk | Standard management verifications |
| **Yellow** | Medium risk | Enhanced desk checks, additional documentation requests |
| **Orange** | High risk | On-the-spot verification, in-depth audit |
| **Red** | Very high risk | Priority audit, possible referral to OLAF |

### Limitations

- Arachne is a **risk identification tool**, not a fraud detection system
- Risk alerts require human analysis and verification
- Data quality depends on the completeness of programme data submitted by MAs
- Not all Member States use Arachne (voluntary for 2014-2020; mandatory from 2021-2027 for certain checks)

## Designation of Authorities

### Designation Criteria (Art. 71 CPR 2021/1060)

| Authority | Key Requirements |
|-----------|-----------------|
| **Managing Authority** | Internal control framework, adequate staffing, segregation of functions, IT systems for monitoring and reporting |
| **Accounting function** | (May be within MA) Accurate accounts, annual financial statements, accounting system capturing all transactions |
| **Audit Authority** | Functionally independent from MA and CA, adequate audit staff, compliance with international audit standards |

### Designation Process

1. Member State **designates** authorities (no prior Commission approval needed in 2021-2027, unlike 2014-2020)
2. MA submits **management declaration** and **annual summary of audits** with first accounts
3. AA issues **audit opinion** on the functioning of the management and control system
4. Commission **reviews** the package and decides on annual acceptance of accounts

## Interruption and Suspension of Payments

### Interruption (Art. 97 CPR)

| Element | Detail |
|---------|--------|
| **Trigger** | Evidence of significant deficiency in management and control system |
| **Duration** | Maximum 6 months (extendable to 12 months at MS request) |
| **Decision** | Authorising Officer by Delegation (AOD) -- operational level |
| **Scope** | Can target specific priority axes or the entire programme |
| **Lifting** | When corrective measures are taken and verified |

### Suspension (Art. 98 CPR)

| Element | Detail |
|---------|--------|
| **Trigger** | Serious deficiency that has not been corrected; MS fails to take necessary action |
| **Duration** | Until corrective action is taken |
| **Decision** | Commission Implementing Decision |
| **Scope** | All or part of interim payments |
| **Consequence** | More severe than interruption; formal Commission decision |

## Financial Corrections

### Net Financial Corrections (Art. 104 CPR)

| Method | When Used | Calculation |
|--------|-----------|-------------|
| **Individual corrections** | Specific operations with identified errors | Exact amount of irregular expenditure |
| **Flat-rate corrections** | Systemic deficiencies; individual quantification not possible | 5%, 10%, 25%, or 100% of expenditure |
| **Extrapolated corrections** | Statistical sample reveals error rate | Error rate applied to population |

### Flat-Rate Correction Levels

| Rate | System Deficiency Level |
|------|----------------------|
| **5%** | Minor weaknesses in one area of the management and control system |
| **10%** | Significant weaknesses in one or more areas |
| **25%** | Serious deficiencies across multiple areas |
| **100%** | Total failure of the management and control system |

## Annual Assurance Chain

### Sequence

1. **Managing Authority**: Management declaration + annual summary (by 15 February)
2. **Accounting function**: Accounts for the accounting year (by 15 February)
3. **Audit Authority**: Annual control report + audit opinion (by 15 February)
4. **Commission review**: Examination of the assurance package (by 31 May)
5. **Commission decision**: Acceptance of accounts + determination of amount chargeable (by 31 May)
6. **Annual clearance**: Payment of balance or recovery of excess pre-financing

### Audit Authority Opinions

| Opinion | Meaning |
|---------|---------|
| **Unqualified** | Accounts are complete, accurate, and true; expenditure is legal and regular |
| **Qualified** | Material matters but limited to specific areas/amounts |
| **Adverse** | Pervasive material deficiencies |
| **Disclaimer** | Unable to obtain sufficient evidence |

## Key Legal References

- **Common Provisions Regulation (EU) 2021/1060**: Shared management framework
- **Commission Delegated Regulation (EU) 2021/1702**: Audit methodology details
- **ERDF/CF Regulation (EU) 2021/1058**: Regional development and cohesion fund
- **ESF+ Regulation (EU) 2021/1057**: Social fund rules
- **JTF Regulation (EU) 2021/1056**: Just Transition Fund
- **OLAF Regulation (EU, Euratom) 883/2013**: Anti-fraud investigations
- **European Court of Auditors Annual Reports**: Benchmark for audit findings

## Cohesion Policy Mid-Term Review (March 2026)

DG REGIO published the results of the mid-term review of cohesion policy programmes (2021-2027) on 27 March 2026. The mid-term review assesses the performance of all cohesion policy programmes and may lead to:
- Reallocation of funds between priority axes within programmes
- Transfer of resources between funds (e.g., from ERDF to ESF+ or vice versa)
- Adjustments to programme targets and milestones
- Updated performance frameworks

EVP Raffaele Fitto discussed the future cohesion policy framework during a visit to Austria (27 March 2026), signalling the Commission's early thinking on post-2027 cohesion policy design. DG REGIO published the full mid-term review results on 1 April 2026, covering all programme adjustments and performance assessments. Fitto also met Belgian government leaders (31 March 2026) to discuss cohesion priorities.

## Cross-References

- See also: `eu_budget_emu_law.md` for OLAF/EPPO and discharge procedure
- See also: `employment_future_of_work.md` for ESF+ programme details
- See also: `eu_financial_regulation_procurement.md` for procurement rules applied by beneficiaries
- See also: `commission_guide.md` for DG REGIO and DG EMPL structures
