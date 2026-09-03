---
name: daily-brief
description: "[DEPRECATED 22 May 2026 — use /brief instead] Original daily brief skill, kept for archival reference. The Brubru Brief format (memory feedback_brubru_brief_new_format) replaces it. New sessions should invoke /brief."
argument-hint: "deprecated — use /brief"
allowed-tools: ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
---

# Daily Brief Email [DEPRECATED — use /brief]

> **This skill is deprecated since 22 May 2026.** Invoke `/brief` instead — it implements the Brubru Brief format (institutional-depth, variable cadence, no codes in lead, BCC distribution + EUTR matching). The instructions below are retained as an archival reference for the pre-11-May daily-cadence workflow.

# Daily Brief Email

**CRITICAL: NEVER send the daily brief to all subscribers without the user's explicit "OK" or "send" confirmation in the terminal. This is a hard rule with no exceptions.**

The daily brief workflow:
1. Pull today's headlines from the database (saved by `/news --save`)
2. Curate to **5 headlines** (default). More than 5 only if the day's news genuinely warrants it -- assess and propose to the user, never default to more.
3. Rewrite headlines in Brubru style (concise, professional, no em-dashes)
4. **Verify Brubru can answer each headline topic** by testing against the knowledge base. If a topic has no guide match or weak coverage, fix it (add content, triggers) BEFORE sending the brief. Never send a headline Brubru cannot answer well.
5. Build the HTML email with hover colour cycling and CTA button
6. Send a TEST email to hello@beresol.eu
7. Present the test to the user for review
8. User reviews and requests changes (or approves)
9. Apply changes if needed, re-send test
10. ONLY when user says "OK" / "send" / "go" -> send to all subscribers

## Step 1: Check Headlines

```bash
cd /Users/victorsole/Developer/brubru/backend
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

**CLI flags do NOT compose**: in `send_daily_brief.py::main()` the `elif` chain orders `--list` → `--verify-urls` → `--test` → `--send`. Passing both `--test` and `--verify-urls` short-circuits at `--verify-urls` and the test email NEVER sends. The `--test` branch already calls `verify_headline_urls(db)` internally before sending. Always pass only ONE of `{--verify-urls, --test, --send}`. (Set 7 May 2026 after the test email failed to deliver because both `--test` and `--verify-urls` were passed together.)

Send the daily brief ONLY to hello@beresol.eu for review:

```bash
cd /Users/victorsole/Developer/brubru/backend
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
  Headlines: 5
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
cd /Users/victorsole/Developer/brubru/backend
python3.12 scripts/send_daily_brief.py --send \
  --extra raquel.correadomenech@europarl.europa.eu \
  --extra alexander.rudawski@comcast.net \
  --extra david.devantcerezo@efpia.eu \
  --extra sergicorbalan@yahoo.com \
  --extra silvia.gambino@europarl.europa.eu \
  --extra-file /Users/victorsole/Developer/brubru/docs/marketing/campaigns/brussels.md \
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

## Step 6: Check Unsubscribes and Bounces (MANDATORY)

**Always** run this after every send. Gmail DSN messages arrive 1-3 minutes after the batch, so wait **at least 2 minutes** before the bounce sweep. The runtime exposes `ScheduleWakeup` for this — schedule a 120-second wake-up and resume `/daily-brief` at this step when it fires. Never skip this check: chronic bouncers erode sender reputation and trigger Gmail throttling.

Two passes are required:

**Pass 1 — Gmail DSN scan (catches extras-file recipients the DB does not know about):**
Use the Gmail MCP tool `search_threads` with the query below. Include TRASH because Gmail frequently files bounces in Trash or Spam automatically.

```
(subject:"Delivery Status" OR subject:"undeliverable" OR subject:"failure notice" OR subject:"Mail Delivery" OR from:mailer-daemon OR from:postmaster) newer_than:1d
```

Also include `includeTrash: true`. For each DSN, extract the failed recipient email and the reason (e.g. `Address not found`, `550 permanent failure`, `Recipient Unknown`).

**Pass 2 — DB unsubscribe/bounce events:**

```sql
-- New unsubscribes
SELECT email, preferences->>'daily_brief_unsubscribed' as unsubscribed
FROM users
WHERE preferences->>'daily_brief_unsubscribed' = 'true'
ORDER BY email;

-- Bounce/unsubscribe events today
SELECT event_type, event_metadata->>'email' as email, created_at
FROM pre_user_events
WHERE event_type IN ('unsubscribe', 'daily_brief_unsubscribe', 'email_bounce')
AND created_at >= CURRENT_DATE
ORDER BY created_at DESC;
```

Report:

```
UNSUBSCRIBE CHECK:
  Total unsubscribed: X
  New today: Y (list emails if any)
  Notable: any paying users who unsubscribed
```

If a paying subscriber (yellow/blue tier) has unsubscribed, flag it to the user as a retention concern.

**Auto-unsubscribe chronic bouncers.** Any address that returns a permanent DSN (`Address not found`, `550`, `Recipient Unknown`, `mailbox full` repeated for 3+ consecutive days) should be added to the unsubscribe list so future sends skip it. Insert a `daily_brief_unsubscribe` row in `pre_user_events` with the email in `event_metadata` — the new `_load_unsubscribed_extras()` filter in `scripts/send_daily_brief.py` will pick it up automatically. Example:

```sql
INSERT INTO pre_user_events (id, pre_user_id, event_type, ab_variant, event_metadata, created_at)
VALUES (gen_random_uuid(), gen_random_uuid()::text, 'daily_brief_unsubscribe', 'A',
        jsonb_build_object('email', 'bouncing.address@example.com', 'note', 'Chronic bouncer auto-unsubscribed YYYY-MM-DD: [reason]'),
        NOW());
```

For addresses already in the `users` table, set `preferences.daily_brief_unsubscribed = true` instead.

## Step 7: Log Results

After sending, update `memory/email_sending_log.md` with the results:
- Date
- Recipients sent/failed/skipped
- Brubru news items included
- Any issues encountered
- Unsubscribe count (total + new)

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

### Brubrufied Headline Format (MANDATORY)

Each headline in the email has three layers:
1. **Headline** (what happened) -- links to the original source
2. **Suggested question** in italics -- the "so what" hook that makes the reader curious
3. **"Ask Brubru" button** -- links to `brubru.beresol.eu/main?q=...` which pre-fills the chat input

The `suggested_query` column in `daily_briefs` drives both the question text and the CTA link. **Every headline MUST have a suggested_query.** This is what turns the daily brief from a news digest into a Brubru engagement funnel.

Good suggested queries:
- Are personalised and actionable ("What does this mean for EU importers?")
- Create curiosity ("How does this affect my sector?")
- Cannot be fully answered by reading the headline alone

Bad suggested queries:
- Just restate the headline ("What are the EHDS implementing rules?")
- Are too generic ("Tell me more about this")

### Per-Headline Brubru Feature CTA (MANDATORY)

Brubru is no longer just a chatbot. Each headline in the brief MUST point the reader to the **specific Brubru feature** that lets them act on the topic — not just the chat. Brubru's canonical feature tree (`memory/project_brubru_feature_tree.md`): Chat, Amendator, My EU Bubble (Dashboard, My Files, Position Analysis, My EU Calendar, Predictions, EC Public Consultations, Documents, Amendments, Legislative Tracker, Analytics), EU Law Comply, Tenderator, API.

**CTA URL canonical paths (source: `memory/reference_brubru_feature_urls.md`; cross-check `frontend/src/App.tsx` if in doubt):**

| Feature | URL |
|---------|-----|
| Chat (pre-filled query) | `https://brubru.beresol.eu/main?q=<URL-encoded query>` |
| Amendator | `https://brubru.beresol.eu/amendator` |
| My EU Bubble — Dashboard | `https://brubru.beresol.eu/my-eu-bubble` |
| My EU Bubble — My Files | `https://brubru.beresol.eu/my-eu-bubble?tab=my_files` |
| My EU Bubble — Position Analysis | `https://brubru.beresol.eu/my-eu-bubble?tab=position_analysis` |
| My EU Bubble — My EU Calendar | `https://brubru.beresol.eu/my-eu-bubble?tab=eu_calendar` |
| My EU Bubble — Predictions | `https://brubru.beresol.eu/my-eu-bubble?tab=predictions` |
| My EU Bubble — EC Public Consultations | `https://brubru.beresol.eu/my-eu-bubble?tab=consultations` |
| My EU Bubble — Documents | `https://brubru.beresol.eu/my-eu-bubble?tab=documents` |
| My EU Bubble — Amendments | `https://brubru.beresol.eu/my-eu-bubble?tab=amendments` |
| My EU Bubble — Legislative Tracker | `https://brubru.beresol.eu/my-eu-bubble?tab=legislative` (NOT `tracker`) |
| My EU Bubble — Analytics | `https://brubru.beresol.eu/my-eu-bubble?tab=analytics` |
| **EU Law Comply** | `https://brubru.beresol.eu/eulawcomply` **(no hyphens — `/eu-law-comply` 404s)** |
| Tenderator | `https://brubru.beresol.eu/tenderator` |
| API | `https://brubru.beresol.eu/api` |

**Incident 28 April 2026:** daily brief shipped with `/eu-law-comply` (with hyphens) on 5th headline CTA. URL 404s; 128 recipients hit a dead link. Always cross-reference this table or `App.tsx` before drafting CTA URLs.

Pick the feature that best matches the headline's intent:

| Headline intent | Right feature CTA |
|-----------------|-------------------|
| "X has been adopted / proposed" | Chat (ask Brubru about it) + Legislative Tracker (track it) |
| "Amendments tabled in committee X" | Amendator (draft amendments) + My EU Bubble > Amendments |
| "Group Y / MEP Z position on file X" | Position Analysis + Predictions |
| "Council / EUCO summit" | My EU Calendar + Predictions |
| "Commission consultation opens" | EC Public Consultations (one-click reply) |
| "New compliance obligation" | EU Law Comply (gap analysis) |
| "TED tender / Horizon call" | Tenderator |
| "New EU data source" | API (subscribe to feed) |

Each headline's HTML block must include a small secondary CTA next to (or below) the "Ask Brubru" button that links to the relevant feature. The verifier in Step 4 (Chatbot Coverage Verification) must also check that the corresponding feature is actually live and useful for the topic — never link to a feature that returns an empty state for the headline's CELEX/OEIL ref.

If headline-level feature CTAs are not yet wired in `daily_brief_email.py`, propose the change to the user, do NOT silently ship a brief without them. The CTA can be a one-line prefix ("Track this in your Legislative Tracker →") until the proper button styling is added.

### Chatbot Coverage Verification (MANDATORY)

Before finalising headlines, verify that every headline's `suggested_query` will be answered well by Brubru's chatbot. For each headline:

1. Run the suggested query through the knowledge loader to check guide matching
2. If NO guide matches or coverage is weak:
   - Fix it: add content to the relevant guide, add triggers, or create a new guide
   - Only then proceed to send
3. **Never send a daily brief that directs users to ask questions Brubru cannot answer well**

```python
from knowledge_base.knowledge_loader import KnowledgeLoader
loader = KnowledgeLoader()
loader.load_all()
for query in suggested_queries:
    results = loader.search_guides(query)
    if not results:
        print(f'[WARN] No guide for: {query}')
```

### Suggested Query SQL Pattern

When curating headlines, always set the `suggested_query` column:

```sql
UPDATE daily_briefs SET suggested_query = 'Your question here?' WHERE id = 'UUID';
```

## Important Notes

- Use `python3.12` (not `python3`)
- Headlines come from `/news --save` which populates the `daily_briefs` table
- **Default: 5 headlines.** More only if the day's news genuinely warrants it -- assess and propose to the user
- The script has duplicate-send protection (`daily_brief_sends` table) -- safe to retry
- Permanent extras: Raquel (EP), Alexander (Comcast), David (EFPIA), brussels.md contacts
- Unsubscribed addresses are automatically excluded
- Gmail daily limit is ~2,000 recipients. Daily brief uses ~200 (individual sends)
- Style rules: no em-dashes or "--", use colons and commas. Real hyperlinks. Brubru palette hover colours.
- The email has hover colour cycling (blue, purple, green, amber, red) on headline rows and a gradient CTA button
- "Ask Brubru" buttons link to `/main?q=...` (NOT `/chat` -- that route does not exist)
- The feature line at the bottom ("Brubru tracks X legislative files, Y guides...") is dynamic -- no need to update manually
- **NEVER skip the test email step. NEVER send to all without user approval.**
