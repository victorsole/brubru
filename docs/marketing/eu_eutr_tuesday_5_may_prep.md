# EU-Wide EUTR English Send-Batch — Tue 5 May 2026 Prep Checklist

Source of truth: `memory/scheduled_content_drops.md` — entry "EU-wide EUTR English wave (Tue 5 May 2026)".
Script: `backend/scripts/send_batch_eu_eutr.py`
Estimated time to complete Steps 1–5: ~2 hours total (mostly waiting for Step 1 loader and Step 2 scraper).

---

## Pre-flight Inventory

### Countries and raw data (offline — CSV read, no DB)

| Country     | Raw orgs (`lobby_orgs_raw.csv`) | With email (`lobby_orgs_emails.csv`) | Status         |
|-------------|--------------------------------:|-------------------------------------:|----------------|
| Belgium     | 2,660                           | 240                                  | **Loaded** |
| Germany     | 2,101                           | 305                                  | **Loaded** |
| France      | 1,573                           | 191                                  | **Loaded** |
| Netherlands | 984                             | 201                                  | **Loaded** |
| Italy       | 1,024                           | 184                                  | **Queue Tue 5 May** |
| Austria     | 375                             | 58                                   | **Queue Tue 5 May** |
| Poland      | 377                             | 102                                  | **Queue Tue 5 May** |
| Ireland     | 294                             | 66                                   | **Queue Tue 5 May** |
| Sweden      | 394                             | 83                                   | **Queue Tue 5 May** |
| Denmark     | 312                             | 73                                   | **Queue Tue 5 May** |
| **Total (all 10)** | **10,094**               | **1,503**                            |                |

Loaded so far (4 countries): **7,318 raw orgs / 937 with verified emails**.
After loading remaining 6: **10,094 raw orgs / 1,503 with verified emails** in `transparency_register_orgs`.

701 of the first 937 fall inside the script's 8-cluster filter (trade, climate, energy, agriculture, finance, research, digital, social). Expect a similar ~75% yield from the 6 new countries → approximately 420 additional cluster-eligible orgs with emails.

### Script constants to edit before sending

| Constant | File + line | Current value |
|----------|-------------|---------------|
| `ISSUES_THIS_WEEK_SHORT` | `backend/scripts/send_batch_eu_eutr.py:61` | `"METSAF, Meta DSA, MFF 2028-2034, Mercosur, Better Regulation"` |
| `ISSUES_BULLETS` (list) | `backend/scripts/send_batch_eu_eutr.py:62–70` | 30 April content (METSAF, Meta DSA, Mercosur ITA, MFF, Better Regulation) |
| `subject` | `backend/scripts/send_batch_eu_eutr.py:261` | `f"Brubru for your EU public-affairs work: {ISSUES_THIS_WEEK_SHORT}"` |

---

## Step 1 — Load Remaining 6 Countries into `transparency_register_orgs`

Sanity-check the CSV files first (offline):

```bash
# Confirm source files exist and row counts match the table above
python3.12 -c "
import csv
from collections import Counter
raw = Counter()
emails = Counter()
with open('data/emails/lobby_orgs_raw.csv', newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        raw[r['head_country'].strip().upper()] += 1
with open('data/emails/lobby_orgs_emails.csv', newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        if r.get('contact_email','').strip():
            emails[r['head_country'].strip().upper()] += 1
for c in ['ITALY','AUSTRIA','POLAND','IRELAND','SWEDEN','DENMARK']:
    print(f'{c:<12} raw={raw[c]:>4}  email={emails[c]:>3}')
"
```

Expected output matches the table above (IT 1024/184, AT 375/58, PL 377/102, IE 294/66, SE 394/83, DK 312/73).

Run the loader (reads CSVs, inserts into DB, idempotent):

```bash
cd backend
python3.12 - << 'PYEOF'
import csv, sys, os
sys.path.insert(0, '.')

try:
    from dotenv import load_dotenv
    _ep = os.path.join(os.path.dirname(os.path.abspath('.')), '.env')
    if not os.path.isfile(_ep):
        _ep = '../.env'
    if os.path.isfile(_ep):
        load_dotenv(_ep)
except ImportError:
    pass

from core.database import SessionLocal
from sqlalchemy import text

COUNTRIES_TO_LOAD = {'ITALY', 'AUSTRIA', 'POLAND', 'IRELAND', 'SWEDEN', 'DENMARK'}

CLUSTER_KEYWORDS = {
    'trade':       ['trade', 'commerce', 'export', 'import', 'customs', 'wto', 'tariff', 'mercosur', 'supply chain'],
    'climate':     ['climate', 'green', 'environment', 'emission', 'carbon', 'biodiversity', 'nature', 'metsaf', 'sf6'],
    'energy':      ['energy', 'power', 'electricity', 'gas', 'nuclear', 'renewable', 'hydrogen', 'grid'],
    'agriculture': ['agriculture', 'food', 'farming', 'fisheries', 'rural', 'agri', 'crop', 'livestock'],
    'finance':     ['finance', 'banking', 'investment', 'capital', 'insurance', 'fintech', 'mifid', 'aml'],
    'research':    ['research', 'innovation', 'science', 'university', 'tech', 'r&d', 'horizon', 'startup'],
    'digital':     ['digital', 'data', ' ai ', 'artificial intelligence', 'cyber', 'dsa', 'dma', 'gdpr', 'platform'],
    'social':      ['social', 'labour', 'health', 'welfare', 'education', 'equality', 'migration', 'inclusion'],
}

def classify(row):
    blob = ' '.join([
        row.get('goals',''), row.get('activity_eu_legislative',''),
        row.get('sub_category',''), row.get('main_category',''),
    ]).lower()
    for cluster, kws in CLUSTER_KEYWORDS.items():
        if any(kw in blob for kw in kws):
            return cluster
    return 'social'

RAW_CSV   = '../data/emails/lobby_orgs_raw.csv'
EMAIL_CSV = '../data/emails/lobby_orgs_emails.csv'

email_map = {}
with open(EMAIL_CSV, newline='', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        em = (r.get('contact_email') or '').strip().lower()
        if em:
            email_map[r['identification_code']] = em

db = SessionLocal()
loaded, already_exists = 0, 0
try:
    with open(RAW_CSV, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            country = row['head_country'].strip().upper()
            if country not in COUNTRIES_TO_LOAD:
                continue
            try:
                cost = float(row.get('calculated_cost') or 0)
            except (ValueError, TypeError):
                cost = 0.0
            contact_email = email_map.get(row['identification_code'])
            cluster = classify(row)
            result = db.execute(text("""
                INSERT INTO transparency_register_orgs
                    (id, name, website, contact_email, policy_cluster, calculated_cost, country)
                SELECT gen_random_uuid(), :name, :website, :email, :cluster, :cost, :country
                WHERE NOT EXISTS (
                    SELECT 1 FROM transparency_register_orgs
                    WHERE name = :name AND country = :country
                )
            """), {
                'name':    row['original_name'].strip()[:500],
                'website': (row.get('web_site_url') or '').strip()[:500],
                'email':   contact_email,
                'cluster': cluster,
                'cost':    cost,
                'country': country,
            })
            if result.rowcount:
                loaded += 1
            else:
                already_exists += 1
    db.commit()
    print(f'[OK] Inserted {loaded} new rows | {already_exists} already existed | countries: IT/AT/PL/IE/SE/DK')
finally:
    db.close()
PYEOF
```

Expected: `[OK] Inserted ~2,776 new rows | 0 already existed | countries: IT/AT/PL/IE/SE/DK`
If `already_exists > 0` on a first run, the BE/DE/FR/NL loader may have included some of these orgs — that is safe, the WHERE NOT EXISTS guard prevents duplicates.

---

## Step 2 — Scrape Additional Emails

Web-scrape contact pages for orgs that have a `website` but no `contact_email`. Hit rate is 30–50% per country. The 4 already-loaded countries will also pick up emails they missed in the CSV.

```bash
cd backend
for c in belgium germany france netherlands italy austria poland ireland sweden denmark; do
    echo "--- scraping: $c ---"
    python3.12 scripts/scrape_eutr_emails.py --country "$c" --limit 200
done
```

This runs sequentially (~5–10 min per country, ~60–100 min total). Run in a tmux/screen session if needed.
Check progress: each country prints `[OK] Found N/200 (X% yield). Not found: Y.`

---

## Step 3 — Refresh `ISSUES_BULLETS` in `send_batch_eu_eutr.py`

The current 5 bullets reference 30 April content. By Tue 5 May the news cycle has moved.
Open `backend/scripts/send_batch_eu_eutr.py` and replace lines 61–70:

**Bullet template for 5 May (fill in based on /news run):**

| # | Slot | What to check | 30 Apr placeholder |
|---|------|---------------|--------------------|
| 1 | Most significant adoption since 1 May | Check College agenda (6 May preview: Social Package) | METSAF |
| 2 | Most significant EP committee/plenary action 4–5 May | Check OEIL + doceo for new committee votes | Meta DSA |
| 3 | Mercosur ITA day-4 update | Provisional application live since 1 May — cite first tariff-line impact | Mercosur ITA |
| 4 | MFF trilogue week-1 signal | Check if first round happened; cite any Presidency counter-offer | MFF |
| 5 | Fresh item from /news 5 May morning | Anything that moved Mon–Tue not covered above | Better Regulation |

**Edit instruction** — replace lines 61–70 in `backend/scripts/send_batch_eu_eutr.py`:

```python
# Replace ISSUES_THIS_WEEK_SHORT (line 61) with the 5 new file names, comma-separated:
ISSUES_THIS_WEEK_SHORT = "<File1>, <File2>, <File3>, <File4>, <File5>"

# Replace ISSUES_BULLETS (lines 62–70) with 5 new bullet strings.
# Each bullet must follow the pattern:
#   "<strong>TITLE — ONE-LINE FACTUAL HOOK</strong>. 2–3 sentences of context. Include CELEX or procedure ref."
ISSUES_BULLETS = [
    "<strong>... bullet 1 ...</strong>. ...",
    "<strong>... bullet 2 ...</strong>. ...",
    "<strong>... bullet 3 ...</strong>. ...",
    "<strong>... bullet 4 ...</strong>. ...",
    "<strong>... bullet 5 ...</strong>. ...",
]
```

**Quick `sed` for the short summary line only** (safe to use even without touching the full bullets):

```bash
sed -i 's/ISSUES_THIS_WEEK_SHORT = .*/ISSUES_THIS_WEEK_SHORT = "<File1>, <File2>, <File3>, <File4>, <File5>"/' \
    backend/scripts/send_batch_eu_eutr.py
```

For the bullets, use your editor — the strings contain `<strong>`, `–`, `&amp;` and other chars that trip up sed.

---

## Step 4 — Subject Line Refresh

The subject is constructed at `backend/scripts/send_batch_eu_eutr.py:261`:

```python
subject = f"Brubru for your EU public-affairs work: {ISSUES_THIS_WEEK_SHORT}"
```

The subject auto-updates once you update `ISSUES_THIS_WEEK_SHORT` in Step 3.
No separate edit needed unless you want a different subject format — in which case edit line 261 directly.

Current (30 Apr) subject:
> `Brubru for your EU public-affairs work: METSAF, Meta DSA, MFF 2028-2034, Mercosur, Better Regulation`

Target (Tue 5 May) subject:
> `Brubru for your EU public-affairs work: <5 hot files of this week>`

---

## Step 5 — Run Send Sequence

DO NOT run any of these commands before completing Steps 1–4.

```bash
cd backend

# 1. Preview: confirm cluster mix, country mix, recipient count (target ~100)
python3.12 scripts/send_batch_eu_eutr.py --preview

# 2. Test send to hello@beresol.eu only — read the email in Gmail before proceeding
python3.12 scripts/send_batch_eu_eutr.py --test

# *** STOP HERE — read the test email in Gmail. Only proceed when satisfied. ***

# 3. Live send — SMTP-level BCC to all ~100 recipients
python3.12 scripts/send_batch_eu_eutr.py --send
```

**What --preview prints:**
- `[INFO] Recipients eligible: N` — must be >= 50 to be worth sending; reschedule if < 30
- `[INFO] Cluster mix: {...}` — verify trade/climate/energy dominate (they map to Mercosur/METSAF/energy headlines)
- `[INFO] Country mix: {...}` — verify all 6 new countries appear alongside the original 4
- First 10 recipient rows: name, cluster, country, email

If `--preview` shows 0 recipients, Step 1 did not complete successfully — re-run the loader.

---

## Step 6 — Post-Send Checks

Run ~2 minutes after `--send` completes:

```bash
# Check Gmail for DSNs (bounce notifications)
# Gmail MCP: search_threads query="subject:(Delivery Status Notification) after:2026/05/05" in:inbox

# Log the send in memory/email_sending_log.md:
# Format:
# ## 2026-05-05 — EU EUTR English Wave (10 countries)
# - Script: backend/scripts/send_batch_eu_eutr.py
# - Recipients: N  |  Sent: N  |  Failed: N
# - Subject: "Brubru for your EU public-affairs work: <topics>"
# - Bounces at T+2min: N
# - Cluster mix: {trade: N, climate: N, ...}
# - Country mix: {BELGIUM: N, GERMANY: N, ...}
# - Notes: first EU-wide English wave; 6 new countries loaded same morning
```

Append to `memory/email_sending_log.md` manually or via `/session-summary` at end of session.
Cross-reference in `memory/query_audit.md` under the 6 May entry (funnel impact: did any EUTR orgs sign up?).

---

## Step 7 — Conversion Comparison

Check `memory/email_sending_log.md` for the Spanish VC wave (4 May) results, then compare:

| Scenario | What it means | Action |
|----------|---------------|--------|
| Both waves: 0% conversion | Landing-page or email-body friction, not audience mismatch | A/B test subject line; add social proof to landing page |
| Spanish VC > 0%, EU EUTR = 0% | Audience profile mismatch — EUTR orgs less ready to pay | Adjust targeting (filter by `calculated_cost > 500k`) |
| EU EUTR > 0%, Spanish VC = 0% | EUTR audience is a better fit | Double down on EUTR wave; expand to Tier 2 countries |
| Both > 0% | Template validated, audience validated | Plan Wave 2 at 21-day rotation (Mon 26 May) |

**Next scheduled wave:** Mon 26 May 2026 (21 days after this send).
Mark in `memory/scheduled_content_drops.md` as `[DELIVERED 2026-05-05]` after the send completes.
