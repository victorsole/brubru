# Data Quality Query Template

Formal query template for Eurostat statisticians writing to National Statistical Institutes (NSIs) about data anomalies detected during validation.

## Query Reference

| Field | Value |
|-------|-------|
| **Query ID** | [ESTAT/UNIT/YYYY/NNN, e.g. ESTAT/G2/2026/042] |
| **Issuing unit** | [Eurostat unit code and name, e.g. G.2 -- International Trade in Services] |
| **Contact** | [Name, email, phone] |
| **Date** | [Date of query] |
| **Response deadline** | [Date -- typically 15-20 working days] |
| **Addressee (NSI)** | [NSI name and country, e.g. INSEE (France)] |
| **NSI contact** | [Name and email of designated NSI counterpart, if known] |

---

## Data Reference

| Field | Value |
|-------|-------|
| **Domain** | [Statistical domain, e.g. ITSS, FATS, FDI, SBS, Short-term statistics] |
| **Dataset** | [Eurostat dataset code, e.g. bop_its6_det] |
| **Reference period** | [Year/quarter, e.g. 2025-Q3, or annual 2024] |
| **Data transmission date** | [Date the data was received from NSI] |
| **Legal basis** | [Regulation, e.g. Regulation (EU) 2019/2152, Art. X] |

---

## Variable(s) Flagged

| Variable | Code | Description |
|----------|------|-------------|
| [Variable 1] | [EBOPS/NACE/other code] | [e.g. SI -- Telecommunications, computer, and information services] |
| [Variable 2] | [Code] | [Description if multiple variables affected] |

---

## Observed Anomaly

### Description

[Describe the anomaly in precise statistical terms. Include:]

- **Current value:** [Reported value, e.g. EUR 2,340 million (credits)]
- **Previous period value:** [e.g. EUR 890 million (credits, 2025-Q2)]
- **Year-on-year change:** [e.g. +163% compared to 2024-Q3]
- **Expected range:** [Based on time series analysis, e.g. EUR 800-1,100 million]
- **Cross-country comparison:** [If relevant, e.g. "Value exceeds the combined total of 5 comparable economies"]

### Supporting Evidence

| Evidence Type | Detail |
|---------------|--------|
| **Partner country mirror data** | [e.g. "Partner X reports EUR 1,200 million (debits) for same flow, compared to your EUR 2,340 million (credits) -- asymmetry of EUR 1,140 million"] |
| **Alternative source** | [e.g. "BPM6 balance of payments data for the same period shows EUR 950 million"] |
| **Time series chart** | [Reference to attached chart if applicable] |
| **Seasonal pattern** | [e.g. "Typical Q3 seasonal factor is 1.05; observed value implies factor of 2.63"] |

### Plausibility Threshold Breached

| Threshold | Type | Value |
|-----------|------|-------|
| [e.g. Year-on-year change > 50%] | [Automatic validation rule / Manual review trigger] | [Actual: +163%] |
| [e.g. Bilateral asymmetry > 30%] | [Bilateral reconciliation threshold] | [Actual: 95%] |

---

## Requested Clarification

Please provide an explanation for the observed anomaly. Specifically, we would like to understand whether the change is due to:

| # | Possible Explanation | Please Confirm (Yes/No) | Details |
|---|---------------------|-------------------------|---------|
| 1 | **Methodology change** (new data source, revised estimation method, reclassification) | [ ] | [If yes, describe the change and its expected impact] |
| 2 | **Coverage change** (new reporters added, reporting threshold change, improved coverage) | [ ] | [If yes, specify which reporters or categories are newly covered] |
| 3 | **One-off event** (large transaction, corporate restructuring, merger/acquisition, IP relocation) | [ ] | [If yes, describe the event and estimated impact on the series] |
| 4 | **Data error** (transmission error, unit error, sign error, misclassification) | [ ] | [If yes, please provide corrected data by the deadline below] |
| 5 | **Revision of previous periods** (back data revised but not yet transmitted) | [ ] | [If yes, please transmit revised back data simultaneously] |
| 6 | **Other** | [ ] | [Please explain] |

---

## Data Correction (If Applicable)

If the anomaly is due to an error, please provide corrected data in the standard transmission format:

| Period | Variable | Original Value | Corrected Value | Reason |
|--------|----------|---------------|-----------------|--------|
| [Period] | [Code] | [Value] | [Value] | [Brief reason] |

Please submit corrections via [eDAMIS / EDAMIS4 / other transmission channel] by **[deadline date]**.

---

## Response Instructions

1. **Deadline:** Please respond by **[date]** (15 working days from the date of this query)
2. **Channel:** Reply to this email / Submit via [eDAMIS / other system]
3. **Format:** Free text explanation + corrected data file if applicable
4. **Escalation:** If no response is received by the deadline, this query will be escalated to the Eurostat Director and may be raised at the next Working Group meeting

---

## Eurostat Internal Notes (Do Not Send)

| Field | Note |
|-------|------|
| **Previous queries on same topic** | [Reference to past queries, if any] |
| **Known NSI issues** | [e.g. "This NSI has had coverage issues with ITSS data since 2023"] |
| **Impact on EU aggregate** | [e.g. "This value accounts for 15% of EU-27 total for this EBOPS item; correction would reduce EU total by ~8%"] |
| **Working Group discussion** | [If applicable: "Raised at BSTG meeting of [date]; NSI committed to investigate"] |
| **Follow-up action** | [e.g. "If error confirmed, request revised back data for 2024-Q1 to 2025-Q3"] |

---

**Template version:** 2.0
**Last updated:** February 2026
**Maintained by:** Eurostat Quality Unit (A.4)
