# Amendator Featured Examples — 14-Day Staleness Audit

**Date:** 2026-05-14
**Auditor:** Remote agent (claude-sonnet-4-6)
**Scope:** `public.amendator_featured_examples` table, created by migration 042 on 2026-04-30

---

## 1. Git Activity Since 2026-04-30

| File | Commits since 2026-04-30 |
|------|--------------------------|
| `backend/scripts/rotate_amendator_examples.py` | **0** (file was added in initial bulk commit) |
| `backend/api/amendator_examples.py` | **0** (same) |
| `docs/marketing/linkedin_*.md` | **0** (no LinkedIn posts created) |

**Key finding: zero /news runs have invoked the rotation script in 14 days.**

The repository contains 45+ commits since 2026-04-30, covering API v1 envelope work, committee meetings, funding tenders, monitoring, vocabulary endpoints, and a KB sweep (13 May). None touched the Amendator examples pipeline.

---

## 2. Seed State (as of migration 042, 2026-04-30)

The migration seeded 10 items. The task brief notes that user-curated cleanup left **6 verified items active** by end of 2026-04-30 — meaning 4 items were deactivated at the DB level on that day (not tracked via git). The audit script will report the live count when run against prod.

### Original 10 seed items

| # | Title | CELEX | Source | Notes |
|---|-------|-------|--------|-------|
| 0 | EU Inc. (28th Regime Corporate Framework) | 52026PC0321 | `manual` | Kept |
| 1 | Better Regulation Communication COM(2026) 380 | 52026DC0380 | `news` | DC — not amendable |
| 2 | AccelerateEU Communication COM(2026) 370 | 52026DC0370 | `news` | DC — not amendable |
| 3 | Waste Shipment Regulation (WSR) + DIWASS | 32024R1157 | `news` | Regulation — amendable |
| 4 | Violence Against Women Directive 2024/1385 | 32024L1385 | `news` | Directive — amendable |
| 5 | Digital Services Act (DSA) | 32022R2065 | `news` | Regulation — amendable |
| 6 | AI Act — Regulation (EU) 2024/1689 | 32024R1689 | `news` | Regulation — amendable |
| 7 | Industrial Accelerator Act | intcom:Ares(2025)3570423 | `manual` | `intcom:` — not amendable |
| 8 | MFF 2028-2034 — COM(2025) 570 | 52025PC0570 | `news` | Proposal — may be amendable |
| 9 | EU-Mercosur ITA — Provisional Application | 22026A00184 | `news` | Agreement — not amendable |

### Document-type gap (secondary finding)

The seed did not set the `document_type` column on any row (all NULL). The API filter is:

```sql
AND (document_type IS NULL OR document_type = ANY(:amendable))
```

This means **all 10 rows pass the filter**, including Communications (52026DC\*), the `intcom:` inter-service consultation reference, and the ITA agreement — none of which are amendable. Consequence: the Amendator UI may show URLs that the parser cannot structure. This is a pre-existing gap from the initial seeding, not introduced by /news rotation.

**Recommended follow-up (not in scope of this PR):** backfill `document_type` values on the seed rows using the CELEX prefix pattern, then deactivate non-amendable entries that are not `source='manual'`.

---

## 3. Stale Items Analysis

**Stale threshold:** 30 days (added_at < 2026-04-14)

As of 2026-05-14, all items are 14 days old. **No items cross the 30-day threshold today.** Migration 043 would deactivate 0 rows if applied now.

First potential stale date: **2026-05-30** (30 days after seeding).

---

## 4. Manually Pinned Items (Protected)

Two items carry `source='manual'` and must never be auto-deactivated by migration scripts or the rotation script:

| Title | CELEX | Notes |
|-------|-------|-------|
| EU Inc. (28th Regime Corporate Framework) | 52026PC0321 | User-verified, high-value example |
| Industrial Accelerator Act | intcom:Ares(2025)3570423 | User-pinned; `intcom:` URL will fail Amendator parser — consider replacing with a public EUR-Lex URL when available |

---

## 5. Recommendation

### Primary: Investigate why /news isn't surfacing new amendable files

Zero rotations in 14 days is the most significant finding. The `/news` skill is supposed to call `rotate_amendator_examples.py` in Step 3.2 when it surfaces new legislative files. This did not happen once in 14 days despite 45+ commits to the codebase and daily news cycles.

**Likely causes to investigate:**
- `/news` Step 3.2 may not have a feeder sub-step that identifies amendable legislative files and calls the rotation script.
- The `/morning` skill's Phase 3D (daily sweep) may not include Amendator rotation.
- Rotation may require manual invocation but was never triggered.

**Recommended action:** Add an explicit sub-step to `/news` Step 3.2 that queries the day's legislative news for files with CELEX prefixes matching `3{year}[RLD]`, `5{year}PC`, or `5{year}DC` (after filtering for amendable types), then calls the rotation script for each new candidate that passes `--verify` (≥5 recitals, ≥3 articles).

### Cadence: Keep as ad-hoc for now

With 0 /news additions in 14 days, there is no empirical basis for a recurring monthly sweep. Thresholds for recommending monthly: ≥8 /news additions in a 14-day window OR >3 stale items. Neither is met.

Re-evaluate after the feeder step is wired up and 2-4 weeks of actual rotation data are available.

---

## 6. Artefacts Produced by This Audit

| File | Purpose |
|------|---------|
| `backend/scripts/audit_amendator_examples.py` | Read-only prod report script (run manually) |
| `backend/migrations/043_amendator_stale_sweep_2026_05_14.sql` | Safe to apply now; deactivations are a no-op today; position repack is live |
| `docs/audits/amendator_examples_audit_2026_05_14.md` | This report |

---

## 7. Manual Steps After PR Merge

1. Run `python3.12 backend/scripts/audit_amendator_examples.py` against prod to get live counts.
2. Review the `[WARN]` lines (NULL document_type, active non-amendable entries).
3. Apply `backend/migrations/043_amendator_stale_sweep_2026_05_14.sql` in Supabase SQL editor.
4. Wire up the /news feeder step (see §5 above).
5. Re-run audit after 2-4 weeks of /news rotation to reassess monthly-cadence recommendation.
