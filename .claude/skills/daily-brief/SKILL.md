---
name: daily-brief
description: Compose and send the daily EU brief email. Drafts 10 headlines in Brubru style, sends a test to hello@beresol.eu for review, then sends to all subscribers ONLY after explicit user approval.
argument-hint: "optional: brubru news items to include"
---

# Daily Brief Email

**CRITICAL: NEVER send the daily brief to all subscribers without the user's explicit "OK" or "send" confirmation in the terminal. This is a hard rule with no exceptions.**

The daily brief workflow:
1. Pull today's headlines from the database (saved by `/news --save`)
2. Rewrite headlines in Brubru style (concise, professional, no em-dashes)
3. Build the HTML email with hover colour cycling and CTA button
4. Send a TEST email to hello@beresol.eu
5. Present the test to the user for review
6. User reviews and requests changes (or approves)
7. Apply changes if needed, re-send test
8. ONLY when user says "OK" / "send" / "go" -> send to all subscribers

## Step 1: Check Headlines

```bash
cd /Users/victorsole/Documents/GitHub/brubru/backend
python3.12 scripts/send_daily_brief.py
```

This previews today's headlines and recipient count. If no headlines exist, warn the user to run `/news --save` first.

Present the headlines as a numbered list:

```
TODAY'S HEADLINES (YYYY-MM-DD):

  1. [EC] Commission adopts Industrial Accelerator Act
  2. [EP] Parliament votes on AI Act implementing measures
  ...

  Recipients: X users + Y pre-users + Z extras = TOTAL
```

## Step 2: Draft Brubru News Items

If the user passed arguments, use them as Brubru product news items. Otherwise, suggest 2-3 items based on what was implemented recently (new knowledge guides, features, improvements).

Brubru news items go in the "New in Brubru" box in the email. Examples:
- "Brubru now covers 58 EU policy domains with verified knowledge guides"
- "New: Committee of the Regions plenary calendar in My EU Calendar"
- "Improved answer accuracy with lower hallucination rate"

Present the suggested items and ask the user to confirm or edit them.

## Step 3: Send Test Email

Send the daily brief ONLY to hello@beresol.eu for review:

```bash
cd /Users/victorsole/Documents/GitHub/brubru/backend
python3.12 -c "
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
sys.path.insert(0, '.')
from core.database import SessionLocal
from services.daily_brief_email import _fetch_headlines, _build_brief_email_html
from services.email_service import EmailService

db = SessionLocal()
headlines, brief_date = _fetch_headlines(db)
db.close()

if not headlines:
    print('[ERROR] No headlines found')
    sys.exit(1)

brubru_news = [
    # INSERT BRUBRU NEWS ITEMS HERE
]

html = _build_brief_email_html(
    headlines, brief_date, 'hello@beresol.eu',
    is_welcome=False, is_registered_user=True,
    brubru_news=brubru_news if brubru_news else None,
)

service = EmailService()
ok = service.send(
    to='hello@beresol.eu',
    subject=f'[TEST] Brubru Daily Brief: {brief_date}',
    html_body=html,
)
print(f'[OK] Test email sent to hello@beresol.eu' if ok else '[ERROR] Failed to send test')
"
```

After sending, tell the user:

```
TEST EMAIL SENT to hello@beresol.eu
  Subject: [TEST] Brubru Daily Brief: YYYY-MM-DD
  Headlines: 10
  Brubru news: X items

  Please check your inbox and let me know:
  - OK to send to all subscribers?
  - Any headlines to rewrite?
  - Any Brubru news items to add/remove/change?
```

## Step 4: Review Loop

Wait for user feedback. The user may:
- **Approve**: "OK", "send", "go", "looks good" -> proceed to Step 5
- **Request changes**: "Change headline 3 to...", "Remove the Brubru news", "Add this item" -> make changes and re-send test
- **Reject**: "Not today", "skip" -> do NOT send, end the skill

If changes are requested:
1. Note the specific changes
2. If headline text needs changing, the headlines come from the database (`daily_briefs` table). Use SQL to update:
   ```sql
   UPDATE daily_briefs SET headline = 'New headline text' WHERE brief_date = 'YYYY-MM-DD' AND priority = N;
   ```
3. Re-send the test email
4. Present again for review

**Loop until the user explicitly approves or rejects.**

## Step 5: Send to All Subscribers

ONLY after explicit user approval:

```bash
cd /Users/victorsole/Documents/GitHub/brubru/backend
python3.12 scripts/send_daily_brief.py --send \
  --extra raquel.correadomenech@europarl.europa.eu \
  --extra alexander.rudawski@comcast.net \
  --extra david.devantcerezo@efpia.eu \
  --extra sergicorbalan@yahoo.com \
  --extra silvia.gambino@europarl.europa.eu \
  --extra-file /Users/victorsole/Documents/GitHub/brubru/docs/marketing/campaigns/brussels.md \
  --news "ITEM_1" "ITEM_2" "ITEM_3"
```

Replace ITEM_1, ITEM_2, ITEM_3 with the approved Brubru news items.

Report the results:

```
DAILY BRIEF SENT
  Sent: X
  Failed: Y
  Skipped (already received): Z
  Breakdown: A users + B pre-users + C extras
```

## Step 6: Log Results

After sending, update `memory/email_sending_log.md` with the results:
- Date
- Recipients sent/failed/skipped
- Brubru news items included
- Any issues encountered

## Headline Writing Rules (MANDATORY)

### Brubru Style
Headlines must be engaging, concise, and written for busy policy professionals who scan quickly. They are NOT institutional press releases. Good Brubru headlines:
- Lead with the "so what" or the tension, not the procedure number
- Use active voice and present tense where possible
- Name specific people, institutions, and stakes
- Add context that makes the reader want to click (deadlines, numbers, consequences)
- Never use em-dashes or "--", use colons and commas instead

**Bad:** "Commission Implementing Decision (EU) 2026/582 of 11 March 2026 concerning certain emergency measures relating to foot and mouth disease in Cyprus"
**Good:** "Foot-and-mouth emergency in Cyprus: Commission extends import controls"

**Bad:** "Energy ministers prepare to give the grids package a political jolt"
**Good:** "Energy Council on Monday 16 March: can ministers agree on the EUR 584 billion Grids Package?"

### Dates Must Include Day Names
Every date in a headline MUST include the day of the week. Never write just "16 March" -- write "Monday 16 March". For ranges: "Monday 16 to Tuesday 24 March". This helps readers immediately orient themselves in the institutional calendar.

### People Must Include Role and Origin
When mentioning a person, always include their role and country/institution. Never write just "Commissioner Kos" -- write "Commissioner Marta Kos (Enlargement, Slovenia)". For MEPs: include political group and country.

### Source URL Verification (MANDATORY)
Every headline URL must point to the correct, working source. Before sending the test email:
1. Verify each URL is reachable (HTTP 200 or 301/302 redirect, NOT 404/500)
2. Verify the URL matches the headline topic (e.g., a headline about TikTok DSA must link to DSA enforcement content, not a random EUR-Lex page)
3. Prefer official institutional sources: EUR-Lex for legislation, OEIL for procedures, europarl.europa.eu for EP documents, ec.europa.eu for Commission publications
4. For Politico/Contexte/media sources, keep the original scraper URL (these are the actual article links)
5. Never use placeholder or guessed URLs. If unsure, use the institutional landing page rather than a broken deep link.

### Source Attribution (MANDATORY)
The source label shown under each headline must reflect the **actual source** (Politico EU, Contexte EU, Official Journal, etc.), NOT the institutional category. The `source` field in the `daily_briefs` table has the real source name. The code already uses `source` over `_category_label(category)`. When reviewing the test email, verify that no headline says "European Commission" or "EU Institutions" when the article actually came from Politico, Contexte, or another media outlet.

### Chatbot Coverage Verification (MANDATORY)
Before finalising headlines, verify that every headline's `suggested_query` will be answered well by Brubru's chatbot. For each headline:

1. Run the suggested query through the knowledge loader to check guide matching
2. If NO guide matches, either:
   - Rewrite the suggested query to match existing triggers, or
   - Flag it as a gap (the user may want to skip this headline or create a guide)
3. Never send a daily brief that directs users to ask questions Brubru cannot answer

```python
from knowledge_base.knowledge_loader import KnowledgeLoader
loader = KnowledgeLoader()
loader.load_all()
for query in suggested_queries:
    results = loader.search_guides(query)
    if not results:
        print(f'[WARN] No guide for: {query}')
```

## Important Notes

- Use `python3.12` (not `python3`)
- Headlines come from `/news --save` which populates the `daily_briefs` table
- The script has duplicate-send protection (`daily_brief_sends` table) -- safe to retry
- Permanent extras: Raquel (EP), Alexander (Comcast), David (EFPIA), brussels.md contacts
- Unsubscribed addresses are automatically excluded
- Gmail daily limit is ~2,000 recipients. Daily brief uses ~200 (individual sends)
- Style rules: no em-dashes or "--", use colons and commas. Real hyperlinks. Brubru palette hover colours.
- The email has hover colour cycling (blue, purple, green, amber, red) on headline rows and a gradient CTA button
- **NEVER skip the test email step. NEVER send to all without user approval.**
