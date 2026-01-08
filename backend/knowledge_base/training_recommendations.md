# Brubru Training Recommendations Based on Difficult Questions

**Date:** November 29, 2025
**Source:** User chat sessions analysis

## Summary of Findings

Analyzed 8 difficult questions across 3 chat conversations. Identified key gaps in Brubru's knowledge base and capabilities.

## Critical Improvement Areas

### 1. Real-Time Legislative Procedure Tracking ⭐⭐⭐ (HIGH PRIORITY)

**Problem:** Users expect up-to-date information on where proposals stand in the legislative process (Council positions, committee votes, etc.)

**Current Gap:** Brubru lacks access to:
- Council working group status
- Real-time procedure tracking
- Committee positions and voting records

**Recommended Solution:**
- Integrate with Oeil (Legislative Observatory) database
- Build scraper for Council press releases and conclusions
- Create automated tracking of legislative procedure stages

**Example Question:**
> "In terms of next steps, any news on where the Council stands?" (on digital euro)

---

### 2. Commission Opinions and Fiscal Surveillance Documents ⭐⭐⭐ (HIGH PRIORITY)

**Problem:** User explicitly asked for Commission's assessment of Portugal's draft budgetary plan. Brubru couldn't retrieve it.

**Current Gap:** No access to:
- Commission Opinions on Draft Budgetary Plans
- European Semester country-specific documents
- Fiscal surveillance assessments

**Recommended Solution:**
- Integrate EUR-Lex API for automated document retrieval
- Build scraper for European Semester documents
- Index Commission Opinions by country and year
- Create specialized retrieval for fiscal governance documents

**Example Question:**
> "What is the conclusion the Commission´s assessment of Portugal´s draft budgetary plan?"

**User Expectation:** Real-time document lookup and analysis (user asked "Could you not consult it for me?")

---

### 3. Economic Governance Data ⭐⭐ (MEDIUM PRIORITY)

**Problem:** Questions about Excessive Deficit Procedures require real-time economic data

**Current Gap:**
- Latest country-specific recommendations
- Real-time fiscal data
- EDP status updates

**Recommended Solution:**
- Scrape European Semester country reports
- Index fiscal surveillance data
- Track EDP status for all member states

**Example Question:**
> "Why did the European Commission keep the excessive deficit procedure for Romania in abeyance?"

---

## What's Working Well ✅

1. **Adopted Legislation Knowledge:** Brubru correctly answered questions about the AI Act with accurate implementation timeline
2. **EU Officials Database:** Correctly identified Henna Virkkunen and her role
3. **General Information Guidance:** Provided helpful directions on where to find Commission opinions

## Priority Action Items

### Immediate (This Month)
1. ✅ Fix `user_id` and `document_ids` field issue in chat API (COMPLETED)
2. 🔲 Build EUR-Lex API integration for Commission Opinions
3. 🔲 Create scraper for Council conclusions and press releases

### Short-term (Next 3 Months)
1. 🔲 Integrate Oeil legislative procedure tracking
2. 🔲 Build European Semester document indexing system
3. 🔲 Create EDP status tracking for all member states

### Long-term (6+ Months)
1. 🔲 Real-time legislative procedure dashboard
2. 🔲 Automated fiscal surveillance monitoring
3. 🔲 Predictive analysis of legislative outcomes

## Data Sources to Integrate

1. **EUR-Lex API** - For Commission Opinions and official documents
2. **Oeil Database** - For legislative procedure tracking
3. **European Semester Portal** - For country-specific recommendations
4. **Council Press Releases** - For Council positions
5. **European Commission Economic Databases** - For fiscal data

## Training Data Created

- `training_data_difficult_questions.json` - Structured dataset with questions, responses, and improvement areas
- This document - Recommendations for systematic improvements

## Next Steps

1. Review these recommendations with the development team
2. Prioritize integration projects based on user needs
3. Create tickets for each integration
4. Set up automated scrapers for high-priority data sources
5. Develop testing framework to validate improvements against these difficult questions
