# CLAUDE.md - AI Assistant Context for Brubru

This file provides context for AI assistants working on this codebase.

---

## AI Workflow Principles (Cherny Paradigm)

### Mindset

You are part of a **workforce**, not just an assistant. The human orchestrates multiple AI instances in parallel—think fleet commander, not typist.

### Institutional Memory Protocol

- Every mistake you make should be documented here as a rule
- Read this file completely—it contains lessons from past errors
- The longer this codebase evolves, the smarter you become
- **Document corrections**: If you do something wrong, expect a rule to be added

### Verification First

Always verify your own work:
- Run tests after code changes (`pytest` for backend, `npm test` for frontend)
- Check that builds succeed before considering work complete
- For UI changes, describe what should be tested manually
- **The AI doesn't just write code—it proves the code works**

### Checkpoint Commits During Long Sessions

During multi-step work sessions (morning routine, feature builds, knowledge base overhauls), commit checkpoints after each logical phase:

- After knowledge guide updates: `chore: checkpoint -- N guides updated`
- After system prompt changes: `chore: checkpoint -- system prompt rules added`
- After context builder fixes: `chore: checkpoint -- context builder improvements`

This enables "try and rollback" methodology: if a later step breaks something, revert to the last checkpoint. Start from a clean git state, commit frequently, accept or roll back.

### Quality Over Speed

Use thorough reasoning. The "compute tax" upfront eliminates the "correction tax" later. Fewer corrections = faster overall.

---

## Project Overview

Brubru is an AI-powered strategic advocacy assistant for EU policy professionals. It combines conversational AI with legislative tools to help users analyse policies, draft amendments, and navigate EU institutional processes.

## Tech Stack

**Frontend:** React 18 + TypeScript + Vite 7.x
**Backend:** FastAPI (Python 3.11+) + SQLAlchemy 2.0
**Database:** PostgreSQL 15+ (Supabase → migrating to Google Cloud SQL)
**AI (Chat):** Open-model chain. **NO ANTHROPIC** (removed 6 Aug 2026: too expensive). Order in `multi_provider_service.py`, rebuilt 11 Sep 2026 after one request failed on all six providers: **Cerebras gpt-oss-120b (primary) → Gemini 2.5-flash → Scaleway (EU-hosted, paid, the lane that answers when both free tiers 429) → Mistral (reads ~30% of context) → Groq qwen3.6-27b (free tier's output cap refuses normal answers) → OpenAI (paid)**. NVIDIA removed (model end-of-life). `/api/chat/health` reports the live chain: trust it over this line. qwen wraps thinking in `<think>`: strip via `_strip_think()`, never a bare regex. Every SDK client sets `max_retries=0`: the chain IS the retry (`memory/feedback_provider_chain_max_retries_zero.md`). `/api/chat/stream` is the ONLY path the UI calls; anything added to `chat()` alone ships dead (`memory/feedback_chat_stream_is_the_only_real_path.md`).
**Hosting:** SiteGround (frontend), Railway.app (backend)

## Key Commands

```bash
# Frontend development
cd frontend && npm run dev

# Backend development
cd backend && python -m uvicorn main:app --reload

# Build frontend
cd frontend && npm run build

# Run backend tests
cd backend && pytest

# Database migrations
cd backend && alembic upgrade head

# Seed test users (13 users with Professional/Starter tiers)
python3.12 -m backend.scripts.seed_test_users
```

## File Naming Convention

**All files use `snake_case`** — with one documented exception.

**Exception:** `frontend/src/App.tsx` and `frontend/src/App.css` retain Vite's default PascalCase because they are the framework-conventional root component and stylesheet referenced directly by Vite's build pipeline. Do not rename without auditing every Vite/Vitest config and package-lock reference.

- `chat_interface.tsx` (correct)
- `ChatInterface.tsx` (incorrect)
- `ai_service.py` (correct)
- `AiService.py` (incorrect)

React components are exported in PascalCase despite snake_case filenames.

## Project Structure

```
brubru/
├── frontend/src/
│   ├── pages/          # Route pages (main_page.tsx, etc.)
│   ├── components/     # UI components by feature
│   ├── services/       # API clients
│   ├── hooks/          # Custom React hooks
│   └── i18n/           # Internationalization (6 languages: EN, FR, NL, ES, CA, IT)
│
├── backend/
│   ├── api/            # FastAPI routers
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response models
│   ├── services/       # Business logic
│   │   ├── ai/         # AI-specific services
│   │   ├── scrapers/   # EU institutional data scrapers
│   │   └── compliance/ # EU law compliance checking
│   ├── core/           # Config, database, security
│   └── knowledge_base/ # Static EU institutional data
```

## Main Features

1. **Brubru Chat** - AI chat with EU policy context (`backend/api/chat.py`)
2. **Amendator** - Legislative amendment editor (Akoma Ntoso XML)
3. **My EU Bubble** - RSS feed aggregator from EU sources
4. **EU Law Comply** - Compliance gap analysis
5. **Document Generator** - AI-powered position papers, MEP briefings, talking points (`backend/api/generate.py`)
6. **My EU Calendar** - Multi-source institutional calendar (`backend/api/eu_calendar.py`)
7. **Admin Panel** - User/subscription management (restricted)

## Important Patterns

- **AI Context:** `backend/services/ai/context_builder.py` injects EU-specific context
- **Scrapers:** `backend/services/scrapers/` fetch data from 15+ EU sources
- **Auth:** Custom JWT with Google/LinkedIn OAuth (no Supabase SDK dependency)
- **Payments:** Stripe integration for modular subscriptions (9 products, 18 price IDs)
- **i18n:** 6 supported languages: English, French, Dutch, Spanish, Catalan, Italian (the languages Victor speaks). **Never claim 23 EU languages.** i18next locales: en, es, ca, fr, it, nl

## Environment Variables

Required in `.env`: `SUPABASE_URL`, `SUPABASE_KEY` (database/auth).
- Chat-chain keys in Tech Stack order (Cerebras, Gemini, Scaleway, Mistral, Groq, OpenAI). **No Anthropic** in chat; OpenAI is the paid last resort and also serves transcription/embedding fallbacks.
- `STRIPE_SECRET_KEY` - Payments
- 18 Stripe Price IDs (see Pricing Model section below)

## Code Style

- British English for all user-facing text (analyse, colour, behaviour)
- Irvin font (The New Yorker) for typography
- WCAG 2.1 Level AA accessibility compliance
- Conventional Commits for git messages

## API Endpoints

Backend runs on `http://localhost:8000`:
- `POST /api/chat` - AI chat endpoint
- `GET /api/amendments` - Amendment CRUD
- `GET /api/rss-feeds` - RSS feed management
- `POST /api/generate/*` - AI document generation (position papers, MEP briefings, talking points)
- `GET /api/eu-calendar/events` - EU Calendar events with filters
- `POST /api/eu-calendar/sync` - Calendar sync from all sources (Professional/Admin)
- `GET /api/subscriptions/plans` - Full pricing breakdown (all plans, modules, bundles)
- `POST /api/stripe/create-checkout-session` - Create Stripe checkout (`{plan, billing_period}`)
- API docs at `/docs` (Swagger UI)

## Database

PostgreSQL via Supabase. Key tables:
- `users` - User profiles
- `chat_conversations` / `chat_messages` - Chat history
- `amendments` - Legislative amendments
- `eu_laws` - Cached EU legislation
- `rss_feeds` / `rss_entries` - RSS data
- `eu_calendar_events` - EU institutional calendar events
- `user_calendar_subscriptions` - Calendar reminders/subscriptions

## Canonical Numbers of the EU Legal Corpus

LEG_2025-11 (Nov 2025 Publications Office bulk export): **8,710 distinct laws / 28,513 OJ publications / 61,219 translatable XML files**. One law can span multiple files (REACH=7, AI Act=14). Always cite the triple; `28,505` is deprecated.

## Testing

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test

# E2E
npx playwright test
```

## Test Users

13 pre-configured test users for development and training (see `docs/users.md`):

- **Professional plan / Blue tier (5):** Charlotte Berends, Marga Payola, Daniel Roldán, Aleix Sarri, Nick Ligthart
- **Starter/Advocate plan / Yellow tier (8):** Robin Loos, Joan González, Sergi Duarte, Meritxell Vicheto, Bo, Marc Desmond, Andrés López, Jaume Bernis

Password: `test123` (except Meritxell: `test23`)

Seed script: `backend/scripts/seed_test_users.py`

## Deployment

- **Frontend:** SiteGround (brubru.beresol.eu) - static build from `frontend/dist/`
- **Backend:** Railway.app (brubru-production.up.railway.app) - auto-deploys from main branch
- **Database:** Supabase PostgreSQL (migrating to Google Cloud SQL)
- **Docker:** `docker-compose up -d` for local development

---

## Predictions Feature (February 2026)

**Full reference:** See `memory/predictions.md`. AI-powered legislative outcome predictions in My EU Bubble. 6 API endpoints under `/api/predictions/`. Yellow tier: 10/month. Blue tier: unlimited + Council. Key files: `api/predictions.py`, `services/predictions/`, `predictions_tab.tsx`.

## EU Calendar Feature (February 2026)

**Full reference:** See `memory/eu_calendar.md`. 6 data sources, month/week/day views. Key files: `api/eu_calendar.py`, `services/scrapers/eu_calendar_sync_service.py`, `eu_calendar_tab.tsx`. CLI: `python scripts/sync_eu_calendar.py`. Yellow tier: full access. Blue tier: AI summary + sync.

## Pricing Model: Modular A La Carte + Bundles (February 2026)

**Full reference:** See `memory/pricing.md`. Internal gating still uses white/yellow/blue tiers.

**Quick reference:** Starter 39/mo, Advocate 59/mo, Professional 99/mo (only blue tier), EP 49/mo. 14-day free trial, no permanent free tier. 9 Stripe Products, 18 Price IDs.

**User-facing text rules:** Never reference White/Yellow/Blue tiers. Use plan names. CTA: "Start Free Trial", "Subscribe", "Get Professional".

---

## Learned Rules

**Full reference:** `memory/learned_rules.md` — full history of rules accumulated from past corrections. Read when working on a topic you have not touched recently.

**Always-on critical rules** (most common pitfalls — full detail in `memory/learned_rules.md`):

- **Short terminal answers (hard rule, Victor, 1 Oct 2026).** No long answers in the Terminal: only what is absolutely necessary. Detail goes in the session MD, not the reply.
- **Never spawn subagents or workflows unasked (7 Oct 2026, Victor):** they burn tokens and plan usage. Work inline or with a no-LLM script, and ask before any fan-out. Memory: `feedback_do_not_spawn_agents_unasked_they_burn_usage`.
- **Never leave files staged in the shared tree (7 Oct 2026):** a parallel session's plain `git commit` swept 20 of my guides into its pushed commit. Stage and commit in one command with explicit paths; push a specific SHA when another session's commit sits on top. Memory: `feedback_git_add_in_a_shared_tree_is_swept_into_another_sessions_commit`.
- **Never test ONE dimension and state it as universal (31 Aug 2026), and verify the INSTRUMENT before acting on a surprising reading (1 Sep 2026).** Enumerate the axis; print the table. An impossible number proves a broken measurement, not a finding: 4 false readings in one session (a >100% ratio on unjoinable tables, a harness that reimplemented production matching, `$?` after a pipe, a stale temp file). Never reimplement a production path in a test harness. `memory/feedback_never_generalise_from_one_dimension.md`, `memory/feedback_verify_the_instrument_before_the_reading.md`.
- **Audit every implementation (set 27 June 2026).** After shipping any code change, script, migration, scraper edit, prompt rewrite, deploy — run a self-audit pass for inconsistencies, bugs, false positives, edge cases the prompt didn't name. Document the lesson. Two steps: ship + audit; never combine. Full pattern: `memory/feedback_audit_implementation_after_every_change.md`.
- **Learn the EU, teach Brubru (set 27 June 2026).** The strategic posture every session: deepen Claude's own EU expertise (treaties, institutions, files, actors, jurisprudence, OJ, OEIL, doceo, EUR-Lex, Cellar, EuroVoc) and feed every learning back into Brubru via knowledge guides + triggers + API endpoints + MEUB surfaces. If Claude's EU knowledge plateaus, Brubru plateaus. Read primary sources, never paraphrase press as primary. Full pattern: `memory/feedback_learn_eu_teach_brubru.md`.
- **Brubru = 6 languages** (EN, FR, NL, ES, CA, IT). Never claim 23.
- **Founder name: Victor Solé** (accent on Solé ONLY; Victor is NEVER written Víctor; HTML: `Victor Sol&eacute;`).
- **No emojis in codebase.** Use MDI icons (frontend) or `[OK]`/`[INFO]`/`[ERROR]` prefixes (backend).
- **Document retrieval:** AI MUST present T9-/A9-/PE-/COM- references with clickable URLs from knowledge guides. Never say "search EUR-Lex yourself."
- **Responsive design (hard rule, every frontend change):** every page must work cleanly at smartphone 375px (iPhone SE), 393px (iPhone 14 Pro), tablet portrait 768px (iPad), tablet landscape 1024px (iPad Pro), laptop 1440px (14-inch MacBook), desktop 2560px (27-inch monitor). Mandatory CSS breakpoints: `>1024px` full-width grids, `@media (max-width: 1024px)` drop 4-col grids to 2 cols, `@media (max-width: 900px)` drop any remaining 3-col grids to 2 cols (cards get cramped at ~245px each between 768-1024 without this), `@media (max-width: 767px)` stack to 1 col + hero font ≤1.9rem + hide header CTA + shrink padding to 1.25rem. Post-build: drag-test 375px to 2560px; zero horizontal scroll, zero cramped cards. Set 15 May 2026 after the EU Canon landing page shipped with a 768-1024 gap.
- **CTA-strip Pexels background on canon + deep-dive pages** (set 15 May 2026): Pexels image + brand gradient overlay, different from hero, photographer credit in footer. Template: `memory/feedback_canon_cta_strip_pexels.md`, else copy `frontend/public/eucanon/*/index.html`.
- **A fix on the branch is NOT a fix in production (28 July 2026).** Before claiming a fix is live: `git merge-base --is-ancestor <fix-sha> <deployed-tip>`, then a behavioural probe. A green deploy log proves nothing. Incident: prod served 405 guides not 538 and applied zero post-processing to streamed answers for a week, because the deploy worktree branches off `origin/main` and drops feature-branch fixes. Memory: `feedback_deploy_tip_must_contain_the_fix`.
- **On-disk presence is NOT deployability (14 Sep 2026).** A guide or asset can exist locally and pass every check while production cannot serve it because git does not track it; the ranker gates on `if guide_id in self.guides`, so a trigger silently falls through to weak content matching. `audit_guide_triggers.py` globs the disk, `check_knowledge_integrity.py` reads `git ls-files`: when two checks disagree, work out which question each asks, never average them. `git add` clears it. Memory: `feedback_on_disk_is_not_deployable`.
- **A client found it first: audit the whole chain (23 Sep 2026).** Joana (Terraqui) sent us a TRIS notification our paid DPP watch should have caught: feed frozen since March, throttling read as "missing", watch never read TRIS, watch never ran daily (a MANDATORY line in a skill is a reminder unless the cron runs it), and `\b` is a BACKSPACE in PostgreSQL (use `\y`). Keep a per-client source ledger (`backend/data/client_sources/`, `scripts/client_source_ledger.py`). Memory: `feedback_client_found_it_first`.
- **A reference written into a guide must resolve at its authority (30 Sep 2026).** The chat turns procedure and CELEX references into links and states them as fact, so a wrong one reaches users as a confident broken link: it cited the Return Regulation as 2025/0033(COD), which OEIL says does not exist (it is 2025/0059(COD)). Before a guide ships, open every new procedure reference on OEIL and every CELEX on Cellar; never derive one. Audit that day: 13 of 203 guide references do not exist, 1 points at a different file. List: `memory/guide_procedure_ref_audit_2026_09_30.md`.
- **A press release is a signpost: carry the document it names (9 Oct 2026).** The RRF guide held the 7 Oct press release's figures but not the report behind them, COM(2026) 546 final, though the release linked it; Cellar had the record two days late and a client found it first. When a press release, news item or post names a report, act or communication, the guide bullet carries that document's identifier (COM/SWD/JOIN or CELEX/OJ) and its link, opened and verified at the authority, or says "document not yet published". `scripts/sync_com_register.py` lists COM documents the register has and Cellar lacks (run it in `/news` Step 0). Memory: `feedback_press_release_names_the_document`.
- **A new value must reach every mirror; one owner per field (24 Sep 2026).** The calendar response schema keeps its own copy of the event-type enum: one `tris_standstill` row failed every `/events/range` call for 13 min. Two scheduled OEIL writers flipped joint files' committees each run. Grep for mirrors when adding a value; give each column one writer; after a push, call the real route in-process before "done".
- **Guide QUICK FACTS must be impossible to misread; trigger keys stay unique (16 Sep 2026).** The chat expanded "PfE"/"ESN" wrongly and said "unanimity" over a guide that said qualified majority. Spell out every acronym, give each category its own bullet with its count ("exactly two"), write "X, NOT Y" where the model may assume Y, then ask production via `/api/chat/stream`. Extend an existing `GUIDE_KEYWORD_TRIGGERS` key in place and AST-assert zero duplicates after every edit (426 duplicate keys once cost 250 guide links). Memory: `feedback_quick_facts_must_be_unambiguous_to_the_model`, `feedback_trigger_dict_duplicate_keys_kill_edits`.
- **A quote or place on a public slide must be ABOUT that topic and name that entity in its source sentence (16 September 2026).** Fuzzy matching published "Odesa" for a sentence naming Kryvyi Rih; review caught a Council enlargement quote and an ECR European Security Council quote placed on a Canada slide. Read the full published sentence and its neighbours before any quote or place goes public. Memory: `feedback_quote_must_be_about_the_slide_topic`.
- **/news must always show ALL scraped items (set 30 June 2026).** Display the full scrape ledger — HIGH, MEDIUM **and** LOW/agency buckets in full, never only high/medium. The priority classifier is keyword-crude and misclassifies; Victor reviews the complete list to catch signal it buries. Proposals tables may focus on the actionable subset, but the raw Part 1 display must be complete. Memory: `feedback_news_show_all_scraped_items.md`.
- **Canonical tree (updated 19 June 2026).** 6 products: **My EU Bubble** (25 sub-tabs in order: 1.1 Overview, 1.2 Policy Interests, 1.3 My Documents, 1.4 News, 1.5 My Tracked Files, 1.6 My OJ, 1.7 Amendments, 1.8 Comparator, 1.9 Legislative Train: state of play, 1.10 Votes, 1.11 My EU Calendar, 1.12 Transcripts, 1.13 Council Watch, 1.14 MEP Watch, 1.15 Plenary Order of Business, 1.16 Parliamentary Questions, 1.17 EU Public Consultations, 1.18 Lobby Meetings, 1.19 Position Analysis, 1.20 Predictions, 1.21 Brubru Databases, 1.22 Research & Evidence, 1.23 Stakeholder Mapping, 1.24 Strategy Docs, 1.25 Tender Docs), **Amendator**, **Chat**, **EU Law Comply**, **Tenderator**, **API**. Never invent non-canonical tabs.
- **Guide triggers: plain substring, NO accent folding, no connector tolerance (27 Aug 2026).** An unaccented non-English key can never fire: `'edat minima xarxes socials'` misses *"l'edat **mínima per a les** xarxes socials"*. Write every non-English trigger **accented, in the phrasing people actually type**, connectors included; add the unaccented form as well, never instead. Finish with a **live retrieval test** in each language plus 2 negatives, not just a duplicate audit (scored 6/10 before the accented variants were added). `memory/feedback_triggers_no_accent_folding.md`.
- **Catalan output must be accented:** sóc, perquè, política, Brussel·les, regulació.
- **Supabase Data API grants are mandatory on new `public.*` tables (set 15 May 2026).** Order in every new-table migration: CREATE TABLE → ENABLE RLS → CREATE POLICY → GRANT (public-read: anon+authenticated SELECT, service_role ALL; user-owned: authenticated CRUD, service_role ALL). Default grant removed 30 Oct 2026 — replay (staging spin-up / restore / new env) breaks without explicit GRANT. Full template + audit + 5 backfilled migrations (041/042/064/065/069): `memory/feedback_supabase_data_api_grants.md`.
- **API endpoint documentation is mandatory.** Every new `/api/v1/*` route ships with a plain-English `summary=` (no CELEX/ECLI/EURIO/CORDIS/SPARQL jargon as primary names) and a 5-section Markdown `description=` (**What it does** / **When to use it** / **Input** / **Try it** / **You get back**). When the endpoint is added or its description changes, run `/postman` in the same session to mirror the rename + description into the published collection. Touching an undocumented endpoint = retrofit it in the same commit. Full template + anti-patterns: `memory/feedback_api_endpoint_documentation_required.md`.
- **Week-ahead (Friday brief):** verify every item against primary EU source (doceo, college-agenda, consilium) before sending. Never trust `eu_calendar_events` DB blindly.
- **Verify any Commission meeting date / College announcement against the EC Transparency Register tentative-agenda PDF before asserting it anywhere (brief, LinkedIn, guide, calendar) — set 26 May 2026.** Trade press + a stale `college_agenda.md` are not enough. Two register URLs + the Playwright→`api/files`→`pdftotext` recipe (highest `SEC(YYYY)NNNN` = live agenda): `memory/feedback_ec_tentative_agenda_primary_source.md`. If the agenda date says "(tbc)", hedge — never assert hard adoption.
- **.env in shell:** never `source .env`. Use `grep '^VAR=' .env | cut -d= -f2-`.
- **Frontend module mismatch:** `rm -rf node_modules package-lock.json && npm install --legacy-peer-deps`.
- **Knowledge guides:** QUICK FACTS block at top. Prompt injection cap 4,000 chars in `format_context_for_ai`. After bulk trigger changes, run orphan audit.
- **`legislation_acronyms.json` only holds REAL legislation acronyms.** It is a linkifier TARGET list, not a glossary: anything in it becomes a EUR-Lex URL Brubru asserts is a law. Never add institutions or treaties (ECB, ESMA, EEC, GATT, NATO...). Incident 18 May 2026: EEC and GATT both mapped to the impossible CELEX `32658R0087` and reached a paying subscriber. Collisions are enforced in code + 47 tests, but **nothing stops a bad entry being added** — that stays human. `memory/feedback_legislation_acronyms_only_real_acts.md`.
- **/session-summary must overwrite memory/day_before.md every session** as its first persistent action. This file is the ONLY context-recovery input for the next morning's `/day-before`. Skipped 18/20/21 April 2026, costing a reconstruction from git log. **Companion rule (28 May 2026):** the session MD must be populated in real time, step by step, not batched at the end.
- **Seed / test fixtures in production-shared tables must be filterable at query time (22 Apr 2026)**: a synthetic transcript fed fabricated tallies to the chat. Exclude seed rows at every retrieval stage; give fixture-prone tables an `is_test` column. `memory/feedback_seed_fixtures_contaminate_prod.md`.
- **/morning Phase 3 cadence — DAILY vs FRIDAY split (27 April 2026, API moved to DAILY 28 April).** DAILY: Chat (KB/triggers/system prompt) + Calendar + Archive sweep + passive My Files/Tracker (OEIL sync) + API hero URL. FRIDAY only: EU Law Comply matrix + Tenderator + Documents templates + Predictions/Position snapshot invalidation. ON USER REQUEST: Amendator example URL, EC Consultations. Codified in `.claude/skills/morning/SKILL.md` Phase 3 (3D + 3F); Mon-Thu carry-overs queue to `memory/friday_sweep_queue.md`.
- **Archive feature (migration 041, 27 April 2026):** `archived_at`/`archived_reason` on user track tables; `scripts/auto_archive_old_items.py` runs in /morning Phase 3D. Full text: `memory/learned_rules.md`.
- **/news Step 5b LinkedIn post is mandatory (set 27 April 2026).** Every /news run must end with a draft LinkedIn post saved to `docs/marketing/linkedin_YYYY_MM_DD_daily_update.md`. Goal: institutional drumbeat showing Brubru is updated daily across the whole product. Template + quality bar in `.claude/skills/news/SKILL.md` Step 5b. Victor publishes manually; Claude never posts to LinkedIn directly.
- **Negation paradox in guide WARNINGs + system prompt (27-28 April 2026).** Never name a forbidden identifier inside its own "do not cite X" warning — that RE-PRIMES the model to emit X. Applies to BOTH knowledge guides AND `_build_system_prompt()` in `services/ai_service.py`. Fix: scrub all named identifier values; describe the FORMAT only (e.g. "PE-numbers: PE + digits + sub-version") never the value. Also: named-MEP / fabricated-tally seed fixtures move to `tests/` with `is_test=True` markers — production grep-paths are themselves a re-priming surface. Memory: `feedback_negation_paradox_in_warnings.md`.
- **CLI wrapper parity (27 Apr 2026).** When a parameter is added to a service function (`services/*.py`), audit every CLI wrapper in `scripts/*.py` that calls it, or the feature ships dead (`235086d4` added `feature_map` but never wired `send_daily_brief.py`; fixed with `--feature INDEX:LABEL:URL`). Memory: `feedback_cli_wrapper_parity`.
- **Bulk outreach must use SMTP-level BCC (27 Apr 2026).** Any `send_batch_*.py` uses ONE SMTP connection with multiple RCPT TO (one MIMEText, To=hello@beresol.eu, 0.5s between RCPTs); per-recipient `EmailService.send()` reconnects each time and hits the Gmail throttle near 80-100. Env var is `SMTP_PASSWORD`; if unset, abort rather than fall back. Memory: `feedback_send_batch_use_bcc`.
- **CELEX numbering ≠ OEIL procedure numbering (set 30 April 2026).** Never derive a CELEX from an OEIL ref — independent counters. Look up the COM document number first, then convert. When in doubt, read `legislative_carriages.celex_numbers` from the DB. Full chain + incident (Greek financial assistance mis-derived as Firearms Trafficking) + pre-flight verifier: `memory/feedback_celex_vs_oeil.md` + `memory/feedback_amendator_url_verification.md`.
- **addyosmani/agent-skills plugin** — engineering-discipline skills; on-demand only, not inside Brubru daily routines. Full guide: `memory/reference_addyosmani_agent_skills.md`.
- **Argparse `nargs="+"` is an anti-pattern for repeatable flags (29 Apr 2026, 3rd incident).** Repeatable flags use `action="append"`: with `nargs="+"` repeated invocations silently overwrite earlier values (`--feature`, `--news`, `--week-ahead` in `send_daily_brief.py`). Fixing one occurrence means auditing ALL argparse decorators in that file in the same commit. Memory: `feedback_cli_wrapper_parity`.
- **NEVER jump between /morning phases without explicit user OK (1 May 2026, 2nd violation).** Every phase transition in `/morning` and any multi-phase orchestrator (`/news`, `/audit-queries`, `/daily-brief`, `/send-batch`) needs its own "ok" / "proceed". **ONE consent at the top is NOT a global pass.** The cost of pausing is low; the cost of an unwanted deploy, email or DB write is high. If the user pre-authorises several phases, still announce each with a one-line "starting Phase X". [x](feedback_morning_routine.md)
- **DG-specific subdomains beat the generic presscorner for Commission press releases (1 May 2026).** Fetch `<dg-subdomain>.ec.europa.eu/news/<slug>_en` first; the presscorner print endpoint 404s. Full text: `memory/learned_rules.md`.
- **Beresol logo in every design footer (set 1 May 2026).** Every `/brubru-design` output (slide, post, hero, infographic, deep-dive, quote/table card) must include `/assets/beresol-logo.png` on a LIGHT footer (white/cream) paired with the Brubru CTA. NEVER apply `filter: brightness(0) invert(1)` to brand logos. Hero can be dark; footer is a light rest zone. Full template: `.claude/skills/brubru-design/SKILL.md` (hard rule #7).
- **SiteGround = `npm run build:prerender`, never a plain build (2nd incident 29 Sep 2026):** a plain build has no `app.html` and overwrites the prerendered `index.html`.
- **Test a send script's logging path before the real send (29 Sep 2026):** a log insert failed after email 1 and aborted the batch. Memory: `feedback_send_log_path_untested`.
- **lftp `--only-newer` silently skips files (set 4 May 2026).** Post-/siteground, curl `last-modified` on every changed user-visible HTML; force-push via `lftp put -O` if stale. Template: `feedback_lftp_only_newer_skips.md`.
- **Raw smtplib needs explicit `load_dotenv()` (set 4 May 2026).** Send scripts using `smtplib` directly (not via `services.email_service.EmailService`) must call `load_dotenv()` at the top or `os.environ.get("SMTP_PASSWORD")` returns None. `EmailService` auto-loads .env; raw smtplib does NOT. Memory: `feedback_send_script_dotenv_required.md`.
- **OEIL is the source of truth for rapporteur identity (set 4 May 2026).** Every deep-dive / chat KB refresh anchors on the OEIL procedure-file FIRST. Press, partner emails, cached content all lag. OEIL contradictions override local cache. Codified in `.claude/skills/deep-dive-refresh/SKILL.md` Step 1. Memory: `feedback_oeil_source_of_truth.md`.
- **RocketReach pattern guesses bounce ~50% on B2B firms (4 May 2026).** Email source order: Crunchbase contact email, then the live /contact page, RocketReach only as tie-breaker; downgrade any guessed row after one bounce. Memory: `feedback_rocketreach_unreliable.md`, `feedback_no_generic_inbox_sends.md`.
- **Sonnet for /brubru-design + LinkedIn drafting (set 4 May 2026).** Delegate via Agent tool with `model: "sonnet"`. Opus orchestrates (planning, audit-queries, judgment); Sonnet writes. Stall fallback: on 600s no-progress retry once, then fall back to Opus with `[stalled-Sonnet-fallback]` note. Memory: `feedback_use_sonnet_for_design_and_linkedin.md`.
- **A TODAY-dated unhandled scheduled drop HARD-BLOCKS Phase 0 (4 May 2026)** until Victor acknowledges it; tomorrow-dated ones are surfaced softly. Codified in `/day-before` Step 5; read BOTH copies of `scheduled_content_drops.md`.
- **/brubru-design Hard Rule #9: no "Day X of N" badges (4 May 2026).** Day context goes in the overline or hero text. `.claude/skills/brubru-design/SKILL.md`.
- **Modal portal mandate (6 May 2026):** a `position: fixed` overlay inside an AnimatedPage must `createPortal(modal, document.body)` (z-index 9999, role dialog). Pattern: `bubble/comparator_tab.tsx`. Full text: `memory/learned_rules.md`.
- **OEIL URL pattern (6 May 2026).** Legacy `oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference=...` 404s for recent procedures. Use `oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=...`; canonical builder `_oeil_url()` in `services/comparator/cell_extractors.py`. When fixing a URL/string-template bug, grep ALL generation paths (system prompt and guides too). Memory: `feedback_oeil_url_endpoint`.
- **`EurlexFetcher.CELEX_PATTERN` rejects two-letter proposal types (PC, JC, DC) (6 May 2026)**: widen the regex or call Cellar directly. Full text: `memory/learned_rules.md`.
- **Cellar PDF fallback for proposals (set 6 May 2026).** When Cellar XHTML 404s (proposals are PDF-only), fetch `publications.europa.eu/resource/celex/<celex>` with `Accept: application/pdf` → HTTP 300 multi-choice → grep `DOC_1` → parse with `pypdf`. Article/recital counts via regex max. Pattern shipped in `services/comparator/structure_extractor.py`. Cache to `eu_laws.extra_metadata.structure_counts`. Full template: `memory/feedback_cellar_pdf_fallback.md`.
- **Footer sidebar margin must match the sidebar side (6 May 2026):** `pagesWithSidebar` in `shared/footer.tsx` lists LEFT-sidebar pages only (`/main`, `/amendator`). Full text: `memory/learned_rules.md`.
- **Brief headlines, snippets and `suggested_query` never contain institutional codes (7 May 2026).** No COM/COD/INI/CELEX/A-/PE-/T-/IP codes or Reg/Dir numbers in hero text; use plain aliases ("AI Act", "28th Regime"). Codes allowed in URL targets, guides and sparingly in detailed snippets. Test before `--test`: could a journalist in Tokyo get the so-what without Googling a code? Memory: `feedback_daily_brief_no_institutional_codes`.
- **Brubru Brief replaces the daily brief (11 May 2026).** 1-3 sends a week, 3-10 headlines, no overlap with the 6 mainstream sources, send-worthiness gate; every headline carries a `suggested_query` pre-verified on prod. No em-dashes, emojis or institutional codes in hero text (extends to ALL Brubru-branded content). Unsubscribe covers 3 pools and always logs the event. Memory: `feedback_brubru_brief_new_format`.
- **EUTR sends require `email_verified=true` (11 May 2026, after 52+ bounces in 10 min).** Migration 063 added the column; all bulk sends filter `email_verified=true AND outreach_status NOT IN ('bounced','unsubscribed')`. Synthetic `info@<domain>` guesses are forbidden — they caused the bounce wave. EUTR send pool today is ZERO (47 named-prefix all pre-bounced) until manual internet-search verifies addresses. Memory: `feedback_eutr_email_verification_required.md`.
- **LinkedIn posts fact-checked line by line before publish (11 May 2026).** Every post draft (Brubru/Beresol/Victor) passes a fact-check table BEFORE being presented as ready: claim / source / verdict (TRUE/PARTIAL/SPECULATIVE/FALSE/UNVERIFIED) / note. Apply fixes to every non-TRUE row. Companion artefacts (slides, infographics) inherit the rule. Sonnet sub-agent drafts are NOT trusted without your own fact-check pass. Memory: `feedback_linkedin_post_factcheck_mandatory.md`.
- **Chat readiness verified via `/api/chat/message`, not MCP `top_guides` (11 May 2026).** MCP's `ask_brubru.top_guides` is a content-overlap retrieval-debug view, not what users see. Pass-1 keyword-trigger + LLM mediation produces the right answer even when overlap-ranking buries the right guide. Before any Brubru Brief / outreach claim about chat readiness, probe production directly via curl on `/api/chat/message`. 2 of 5 headlines on 11 May flagged red by top_guides actually worked perfectly on the real endpoint.
- **Marketing cadence Mon-Thu inside /morning (11 May 2026):** Mon post + slide, Tue reel, Wed outreach, Thu long-form, Fri `/competitors`; six languages. Plan: `memory/project_brubru_marketing_gtm_strategy_2026_05.md`.
- **The repo lives at `~/Developer/brubru` (moved 3 Sep 2026).** `~/Documents/GitHub/brubru` is STALE and iCloud-synced (evicted files fault: the old `git push` SIGBUS): never read, write or `cd` there; anything still resolving to it is a bug. Memory: `project_repo_lives_in_developer_not_icloud`.
- **Pack-objects SIGBUS on `git push` (22 May 2026, resolved by the 3 Sep repo move):** if it recurs, retry with `-c pack.window=0 -c pack.depth=0 -c pack.compression=0` and re-diagnose. Full text: `memory/learned_rules.md`.
- **Never hardcode an absolute `/Users/victorsole/...` repo path (3 Sep 2026).** Derive it from the file: `_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])` in `backend/scripts/*.py` and `backend/tests/*.py` (self-contained, not a shared helper: scripts run as `python3.12 -m backend.scripts.<name>`); `BACKEND="${0:A:h:h}"` in zsh. Configs count too (`.mcp.json`, `.claude/settings.json` hooks, skills, launchd). A wrong path never raises. Memory: `feedback_no_hardcoded_absolute_repo_paths`.
- **EP10 URL discipline (22 May 2026).** EP10 doceo URLs use `-10-` not `-9-`; adopted texts `P10_TA(YYYY)NNNN`, reports `A10-NNNN/YYYY`, resolutions `B10-NNNN/YYYY`. On a 404, **switch tool, never re-guess a similar path**: Tavily with a date range, then the scraper output, then ask the user. Working anchors: `europarl.europa.eu/news/en/press-room`, `/plenary/en/votes.html?tab=votes`, `/plenary/en/texts-adopted.html`, `/plenary/en/agendas.html`. Memory: `feedback_ep_url_no_guessing`.
- **Silence is not success (24 Aug 2026, five instances in one day).** A job that can fail must record it durably and not exit 0, never `except -> logger.warning` alone [a](feedback_silent_failure_reports_success.md). Count PERSISTED changes, not attempts; health flags are three-state so "untested" cannot read "healthy". An empty output is never absence (use `git cat-file -e <rev>:<path>`, not a relative pathspec) [b](feedback_empty_output_is_not_absence.md). `pool_pre_ping` fires on CHECKOUT, so it cannot protect a Session held across long network work [c](feedback_long_session_needs_reconnect.md).
- **A job that stores nothing must fail; measure on the user's path (25 Sep 2026).** `parl_questions` was green 5 months storing 0 rows (walled page); a quality eval measured `/api/chat/message`, not `/stream`. Exit non-zero on an empty source; eval through `/api/chat/stream` + probe header. Memory: `feedback_quality_measured_on_the_user_path`.
- **Public marketing: no institutional codes, and grep Brubru's code before any competitor comparison claim (22 May 2026).** Full text: `memory/learned_rules.md`; memory `feedback_linkedin_no_institutional_codes`.

---

## Strategic North Star: WAPU (Weekly Active Paid Users)

**WAPU = paid subscriber + 1 core action in 7 days.** Every feature must answer: "Does this grow WAPU?"

**Core actions:** AI chat query, document generated, file tracked/checked, amendment drafted/analysed, compliance report run.

**Targets:** 10 (Phase A, months 1-3), 25 (Phase B, months 4-6), 50 (Phase C, months 7-12).

**Full details:** See `memory/strategy.md` and `docs/business_plan/strategy.html`.

---

## Catalan EU Legislation Translation Pipeline (March 2026)

**Primary engine:** Softcatala NMT (`eng-cat-2024-09-24`, CTranslate2, local, free). **Fallback:** Claude Sonnet (`--engine sonnet`). Post-processing glossary corrects known errors (d'execució, ha adoptat, Comitè dels Estats membres). When in doubt on terminology, check Spanish EUR-Lex and assess the Catalan equivalent.

**Source:** 28,513 Formex V4 XML files in `docs/LEG_2025-11/`. **Output:** `frontend/public/legislacio-ue-catala/[celex]/index.html`.

**CLI:** `cd backend && python3.12 scripts/catalan_translate.py --translate path/to.xml --celex 32016R0679`. Add `--engine sonnet` for paid high-quality.

**Key files:** `backend/scripts/catalan_translate.py` (parser + translation + HTML generator). Spec: `docs/catalan-implementation.md`. Skill: `/catalan`. Memory: `memory/catalan_translation.md`.

**Brubru Catalan standard:** D'execució (not d'implementació), Ha adoptat (not ha aconseguit), Tenint en compte, Dictamen, Paràgraf, Comitè dels Estats membres. Always regenerate `frontend/public/guides/index.html` after guide changes.
