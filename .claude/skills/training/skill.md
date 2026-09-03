---
name: training
description: Systematic chatbot quality improvement through synthetic query generation and testing. Fetches real user query patterns, generates challenging synthetic queries from EU legislation, tests them against the knowledge base and live backend, identifies gaps, and implements fixes. The `api` sub-command dogfoods Brubru's own v1 API (data/training/api_queries_50.json) to verify each user query pattern is answerable via the public REST surface. Run after /morning to continuously improve Brubru's answer quality.
argument-hint: [N rounds (default 10) | "audit" guide quality | "replay" real user queries | "golden" build answer dataset | "prompts" refresh example questions | "system" audit system prompt | "api" dogfood v1 API | "full" run everything]
allowed-tools: ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
---

# Chatbot Training: Systematic Quality Improvement

You are running Brubru's chatbot training loop. This is an evaluation-improvement cycle that makes the chatbot better with every run.

Read `memory/query_audit.md` for context on previous audit findings.

## Sub-commands

Parse the ARGUMENTS to determine which phase to run:

| Argument | Phase | Description |
|----------|-------|-------------|
| `N rounds` or just a number | **Trigger Training** | Generate N rounds x 10 synthetic queries, test against KB, fix gaps |
| `audit` | **Guide Audit** | Audit top 20 guides for content quality, fix missing QUICK FACTS |
| `replay` | **User Replay** | Replay real user queries, grade responses, identify pain points |
| `golden` | **Golden Answers** | Build query/ideal-answer pairs for regression testing |
| `prompts` | **Example Questions** | Refresh featured chatbot questions in database |
| `system` | **System Prompt Audit** | Stress-test system prompt rules, check for bad behaviours |
| `api` | **API Dogfooding** | Run the 50-query dataset against the public v1 API; report coverage |
| `euvoc` | **EU Vocabularies Validation** | Run the 51-query / 10-category set from `data/training/euvoc_queries.json` against chat + v1 API in parallel; diff and report regressions |
| `drift` | **Ontology Drift Test** | Run `pytest backend/tests/test_ontology_drift.py` — fail-fast if any cdm:* predicate referenced in code is missing from the pinned snapshot |
| `full` | **Full Training** | Run all phases in sequence |

If no argument or just a number: run Trigger Training (original behaviour).

---

## Phase: Trigger Training (default)

### Overview

Brubru uses API models (Claude/Mistral) with injected context (knowledge guides, triggers, system prompt). "Training" means improving the context layer so the model produces better answers. The loop:

1. **Analyse** real user query patterns
2. **Generate** synthetic queries that stress-test weak areas
3. **Test** against knowledge base (fast) and optionally live backend (slow)
4. **Fix** gaps found
5. **Verify** fixes work

### Step 1: Fetch Real Query Patterns

Pull all user queries from the last 30 days to understand what users actually ask:

```sql
SELECT
  c.user_id,
  u.email as user_email,
  m.content as query,
  m.created_at
FROM chats c
JOIN chat_messages m ON m.chat_id = c.id
LEFT JOIN users u ON u.id = c.user_id
WHERE m.role = 'user'
  AND m.created_at >= NOW() - INTERVAL '30 days'
ORDER BY m.created_at;
```

Exclude Victor's test queries (victor@hellobo.eu, victor@beresol.eu).

Classify each query into patterns:

| Pattern | Example | Frequency |
|---------|---------|-----------|
| **explain_topic** | "Tell me about the AI Act" | ~30% |
| **status_inquiry** | "What's the status of the pharma reform?" | ~8% |
| **who_is** | "Who is the rapporteur for REACH?" | ~10% |
| **amendment_draft** | "Draft an amendment to the AI Act to exempt SMEs" | ~10% |
| **written_question** | "Draft a parliamentary question about CBAM implementation" | ~8% |
| **resolution_draft** | "Help me draft points for an EP resolution on energy sovereignty" | ~5% |
| **contacts_lookup** | "Who is the Commissioner for energy?", "Which MEPs are on ITRE?" | ~8% |
| **org_specific** | "Which EU regulations affect the hydrogen sector in Spain?" | ~7% |
| **list_request** | "List MEPs in ENVI committee" | ~5% |
| **agenda_calendar** | "What's on the plenary agenda?" | ~4% |
| **drafting_request** | "Draft a position paper on PFAS" | ~5% |
| **funding_grants** | "Are there EU funds for agrifood in Albania?" | ~3% |
| **procedure_lookup** | URL or procedure reference pasted | ~3% |
| **impact_analysis** | "How does the Iran conflict affect EU energy?" | ~2% |

Also track language distribution: EN (~75%), ES (~5%), CA (~4%), IT (~2%), FR (~1%), other (~13%).

### Step 2: Select Random Laws

**Primary source: `eu_laws` PostgreSQL table** (28,505 laws with titles, policy areas, TSVECTOR search). This is much faster than reading XML files from disk.

```python
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['DATABASE_URL'])
cur = conn.cursor()

# Pick N random laws with titles, weighted towards primary legislation
cur.execute("""
    SELECT celex, doc_type, title, policy_area 
    FROM eu_laws 
    WHERE title IS NOT NULL AND title != '' AND LENGTH(title) > 30
    ORDER BY RANDOM() 
    LIMIT %s
""", (N * 2,))  # oversample, then filter
laws = [(celex, title[:200], policy_area) for celex, dt, title, policy_area in cur.fetchall()][:N]
conn.close()
```

You can also select laws by policy area for targeted training:

```python
# For cluster-specific training (e.g. energy orgs)
cur.execute("""
    SELECT celex, title, policy_area FROM eu_laws 
    WHERE policy_area IN ('Energy', 'Climate Action', 'Environment')
    AND title IS NOT NULL AND LENGTH(title) > 30
    ORDER BY RANDOM() LIMIT %s
""", (N,))
```

**Policy areas available:** Digital Policy and Digital Economy, Economic and Financial Affairs, Foreign and Security Policy, Trade and Economic Security, Agriculture, Environment, Maritime Affairs and Fisheries, Food Safety, Climate Action, Energy, Taxation, Health, Transport, Migration and Home Affairs, Employment and Social Affairs, and more.

**TSVECTOR search** for finding laws by topic:

```python
cur.execute("""
    SELECT celex, title FROM eu_laws 
    WHERE search_vector @@ plainto_tsquery('english', 'renewable energy directive')
    LIMIT 10
""")
```

**Fallback:** If the database is unavailable, use the XML corpus at `docs/LEG_2025-11/` (see `memory/reference_leg_2025_11.md`).

### Step 3: Generate Synthetic Queries

For each selected law, generate a query using one of the identified patterns. Vary across:
- **All patterns** (not just explain_topic)
- **All 6 languages** (EN, ES, CA, FR, IT, NL)
- **Difficulty levels**: simple ("What is X?"), medium ("What's the status and who is the rapporteur?"), hard ("Draft a position paper on X considering the impact on sector Y in country Z")

Template:

| Pattern | Template |
|---------|----------|
| explain_topic | "Tell me about [LAW_TITLE]" / "What is [LAW_TITLE]?" |
| status_inquiry | "What's the status of [LAW_TITLE]?" |
| who_is | "Who is the rapporteur for [LAW_TOPIC]?" |
| amendment_draft | "Draft an amendment to [LAW_TITLE] to [CHANGE]" / "Draft amendment ideas for [LAW_TITLE] on [ASPECT]" |
| written_question | "Draft a written question to the Commission about [TOPIC]" / "Help me draft a parliamentary question about [LAW_TOPIC]" |
| resolution_draft | "Help me draft key points for an EP resolution on [TOPIC]" / "What should an EP resolution on [TOPIC] include?" |
| contacts_lookup | "Who is the Commissioner responsible for [POLICY_AREA]?" / "Which MEPs are on the [COMMITTEE] committee?" / "Which DG handles [LAW_TOPIC]?" |
| org_specific | "Which EU regulations affect [SECTOR] in [COUNTRY]?" / "How does [LAW_TITLE] affect my [ORG_TYPE]?" |
| list_request | "List all EU regulations related to [POLICY_AREA]" |
| drafting_request | "Draft a position paper on [LAW_TOPIC]" |
| funding_grants | "Which EU funds can a [COUNTRY] [ORG_TYPE] apply for?" |
| impact_analysis | "How does [LAW_TITLE] affect [SECTOR]?" |

### Step 4: Test Queries

#### Fast test: Knowledge base matching

```python
from knowledge_base.knowledge_loader import KnowledgeLoader
kl = KnowledgeLoader()
kl.load_all()

for query in synthetic_queries:
    results = kl.search_guides(query)
    guide_ids = [r['id'] for r in results[:3]]
    status = 'MATCH' if results else 'GAP'
    print(f"[{status}] {query[:70]} -> {guide_ids}")
```

Present results as:

| # | Status | Query | Guides matched |
|---|--------|-------|----------------|
| 1 | MATCH | What is the EU anti-dumping... | eu_trade_policy |
| 2 | GAP | Quali sono i requisiti... | (none) |

#### Slow test (optional, only when user requests): Live backend

```bash
cd /Users/victorsole/Developer/brubru/backend
curl -s -X POST http://localhost:8000/api/chat/message \
  -H "X-Brubru-Probe: 1" \
  -H "Content-Type: application/json" \
  -d '{"message": "QUERY", "user_id": null, "conversation_id": null, "use_context": true}' \
  --max-time 200 | python3.12 -m json.tool
```

Only run live tests if the backend is already running. Do NOT start the backend from this skill.

### Step 5: Fix Gaps

For each GAP found:

| Gap type | Fix |
|----------|-----|
| Missing guide | Create new guide in `knowledge_base/guides/` |
| Missing trigger | Add keyword triggers in `knowledge_loader.py` |
| Missing multilingual trigger | Add triggers in ES/CA/FR/IT/NL |
| Wrong guide matched | Adjust trigger specificity |
| Guide matched but key info missing | Update guide content |
| Orphan trigger (guide ID not in `self.guides`) | Fix guide ID or create missing guide file |

After fixes:
1. Verify Python syntax: `python3.12 -c "import ast; ast.parse(open('knowledge_base/knowledge_loader.py').read()); print('[OK]')"`
2. Regenerate guides HTML: `python3.12 scripts/generate_guides_html.py` (also auto-syncs hardcoded guide/trigger counts in `frontend/public/data-architecture/index.html`)
3. Re-run the GAP queries to verify they now match

### Step 6: Report

Present a summary:

```
TRAINING REPORT: YYYY-MM-DD
  Real queries analysed: N (last 30 days)
  Synthetic queries generated: M
  Knowledge base match rate: X/M (Y%)
  Gaps found: Z
  Fixes applied:
    - New guide: [name]
    - New triggers: N added
    - Guide updates: [list]
  Post-fix match rate: X'/M (Y'%)
  Remaining gaps: [list of unfixable items]
```

### Step 7: Log

Append results to `memory/query_audit.md` under a new "Training" section with the date.

---

## Phase: Guide Audit (`/training audit`)

Audit the top 20 most-triggered knowledge guides for content quality. This ensures the guides that users hit most often are complete and useful.

### Step 1: Identify Top 20 Guides

```python
from knowledge_base.knowledge_loader import GUIDE_KEYWORD_TRIGGERS
from collections import Counter

guide_counts = Counter()
for trigger, guide_ids in GUIDE_KEYWORD_TRIGGERS.items():
    for gid in guide_ids:
        guide_counts[gid] += 1

top20 = [gid for gid, _ in guide_counts.most_common(20)]
```

### Step 2: Check Each Guide for Quality Criteria

For each guide, verify:

| Criterion | Check | Severity |
|-----------|-------|----------|
| **QUICK FACTS section** | Must exist and be first section after title | HIGH |
| **CELEX number** | In QUICK FACTS | HIGH |
| **COM/procedure reference** | COM(YYYY)NNN or YYYY/NNNN(COD) | HIGH |
| **EP committee** | Lead committee identified | MEDIUM |
| **Rapporteur** | Name + group + nationality | MEDIUM |
| **Commissioner** | Responsible Commissioner | LOW |
| **OJ reference** | For adopted acts | LOW |
| **Character count** | Flag if >7500 (truncation risk at 4000 in AI prompt) | HIGH |
| **Document references** | Clickable URLs or document codes in QUICK FACTS | HIGH |
| **Stale information** | Rapporteur from previous mandate, outdated status | HIGH |

### Step 3: Fix Issues

For each issue found:

- **Missing QUICK FACTS**: Add a complete QUICK FACTS block at the top of the guide. MUST include: full name, CELEX, COM number, procedure ref, EP committee, rapporteur, status, key dates. This block is what survives truncation.
- **LONG guide (>7500 chars)**: Ensure ALL critical info is in QUICK FACTS (first 1500 chars). Do NOT shorten the guide itself -- the full content is valuable for keyword matching.
- **Missing rapporteur**: Research and add. Check OEIL or EP website for current rapporteur.
- **Stale info**: Update. If a procedure has advanced (committee report adopted, trilogue concluded), update the status.
- **Orphan triggers**: Triggers pointing to guide IDs with no `.md` file. Reroute to the closest existing guide or create the missing file.

### Step 4: Verify orphan triggers

```python
from knowledge_base.knowledge_loader import KnowledgeLoader, GUIDE_KEYWORD_TRIGGERS
kl = KnowledgeLoader()
kl.load_all()

orphans = set()
for trigger, guide_ids in GUIDE_KEYWORD_TRIGGERS.items():
    for gid in guide_ids:
        if gid not in kl.guides:
            orphans.add(gid)

if orphans:
    print(f"ORPHAN GUIDE IDs (triggers exist but no .md file):")
    for o in sorted(orphans):
        count = sum(1 for t, ids in GUIDE_KEYWORD_TRIGGERS.items() if o in ids)
        print(f"  {o} ({count} triggers)")
```

### Step 5: Report

Present a table:

| Guide ID | Chars | QUICK FACTS | CELEX | Rapporteur | Committee | Issues |
|----------|-------|-------------|-------|------------|-----------|--------|

After fixes, regenerate guides HTML: `python3.12 scripts/generate_guides_html.py` (also auto-syncs hardcoded guide/trigger counts in `frontend/public/data-architecture/index.html`)

---

## Phase: User Replay (`/training replay`)

Replay real user queries from the database and grade the knowledge base response. This tests the full pipeline from the user's perspective.

### Step 1: Fetch Real Queries

Same SQL as Trigger Training Step 1. Group by user to identify frustration sessions (multiple queries on the same topic = user not getting what they need).

### Step 2: Identify Frustration Patterns

A "frustration session" is when a user asks 3+ queries on the same topic, especially with phrases like:
- "I am NOT asking about..."
- "You have not given me..."
- "I don't want you to tell me how to do it"
- "Why are you now not able to..."
- "Link is 404 not found"
- "your info is generic, not detailed"

These indicate the chatbot failed. Extract the core topic and test what the knowledge base returns.

### Step 3: Test Each Frustration Session

For each frustration session:
1. Take the user's FIRST query (the original intent)
2. Run it through `kl.search_guides(query)` to see what guide matches
3. Read the matched guide content and assess: does it contain the information the user was looking for?
4. Check if document references (COM, T9, A9) in the guide are complete and correct
5. Grade: PASS (guide has the answer), PARTIAL (guide exists but missing key info), FAIL (wrong guide or no guide)

### Step 4: Fix Failures

For each FAIL or PARTIAL:
- If wrong guide matched: adjust triggers
- If guide content insufficient: update the guide with the missing information
- If no guide exists: create a new one
- If document references are missing: add them to QUICK FACTS

### Step 5: Report

```
REPLAY REPORT: YYYY-MM-DD
  Users analysed: N
  Frustration sessions identified: M
  Results:
    PASS: X (guide has the answer)
    PARTIAL: Y (guide exists, missing info)
    FAIL: Z (wrong/no guide)
  Fixes applied: [list]
```

---

## Phase: Golden Answers (`/training golden`)

Build a dataset of query/ideal-answer pairs for regression testing and future fine-tuning.

### Step 1: Select Representative Queries

Pick 50 queries that cover all patterns, languages, and difficulty levels:
- 20 from real user queries (top queries by pattern diversity)
- 20 from synthetic queries that matched well
- 10 edge cases (multilingual, multi-topic, adversarial)

### Step 2: Generate Ideal Answers

For each query:
1. Run `kl.search_guides(query)` to get matched guides
2. Read the full guide content
3. Write an ideal answer that:
   - Uses the guide's QUICK FACTS for key data points
   - Includes all document references with correct formats
   - Follows Brubru's system prompt rules (British English, present documents, don't say "search EUR-Lex")
   - Is concise but complete (200-500 words)
   - Ends with actionable follow-up suggestions

### Step 3: Save Dataset

Save to `data/golden_answers/golden_answers.json`:

```json
[
  {
    "id": "GA-001",
    "query": "What is the AI Act?",
    "language": "EN",
    "pattern": "explain_topic",
    "expected_guide": "ai_act_regulation",
    "ideal_answer": "The AI Act (Regulation (EU) 2024/1689)...",
    "quality_criteria": [
      "mentions_celex",
      "includes_doc_refs",
      "british_english",
      "actionable_followup"
    ]
  }
]
```

### Step 4: Report

```
GOLDEN ANSWERS REPORT: YYYY-MM-DD
  Total pairs created: N
  By pattern: explain_topic=X, status_inquiry=Y, ...
  By language: EN=X, ES=Y, CA=Z, ...
  Coverage: N/115 guides have at least one golden answer
```

---

## Phase: EU Vocabularies Validation (`/training euvoc`)

Run the synthetic-query set generated by Phase 11 of `docs/applications/euvoc.md` against both the chatbot and the v1 API in parallel. Diff the surfaces. Flag regressions.

### Cadence

Weekly, **Friday alongside `/training api`**.

### Step 1: Run the runner

```bash
python3.12 backend/scripts/run_euvoc_training.py
```

This loads `data/training/euvoc_queries.json` (51 queries × 10 categories, 27 distinct CELEX) and exercises every Phase 0-13 surface via FastAPI's TestClient. Look for:

- Per-category pass rate (each of the 10 categories should be ≥ 80%)
- Authority-label resolution coverage (any URI that doesn't resolve = `eu_authority_labels` gap)
- Identifier resolver coverage (any unrecognised identifier = parser drift)

### Step 2: Diff against last week's report

The runner writes a JSON to `data/training/euvoc_results/YYYY-MM-DD.json`. Compare to the previous week's file. Anything that flipped from pass to fail is a regression.

### Step 3: Fix and report

Wire fixes per the standard pattern (KB guide for missing topic, system prompt rule for prompt-injection issue, `format_context_for_ai` adjustment for retrieval issue). Append findings to `memory/query_audit.md` and `memory/quality_framework.md`.

### Step 4: Email if regression

If any category dropped pass rate by >10pp WoW, email the report to hello@beresol.eu (Friday-only — doesn't run on quiet days).

---

## Phase: Ontology Drift Test (`/training drift`)

Fail-fast static check: every `cdm:*` predicate the codebase references must be present in the pinned snapshot at `docs/ontologies/cdm/cdm-brubru-subset.ttl`. Catches "we added a SPARQL query against a predicate but forgot to refresh the snapshot" — which means CI tells us before Cellar's ontology drift bites the chatbot.

### Cadence

Weekly, **Friday alongside `/training api` and `/training euvoc`**.

### Step 1: Run the test

```bash
cd backend && python3.12 -m pytest tests/test_ontology_drift.py -v
```

### Step 2: If it fails

Re-snapshot via:

```bash
python3.12 backend/scripts/snapshot_cdm.py
```

Then re-run the drift test. Commit the refreshed snapshot in the same PR as the predicate that triggered the failure — never commit one without the other.

---

## Phase: Example Questions (`/training prompts`)

Refresh the featured chatbot questions shown on the main chat page.

### Step 1: Check Current Examples

```sql
SELECT id, question_text, scope, is_active, category
FROM chat_example_prompts
WHERE scope = 'main_chat'
ORDER BY display_order;
```

### Step 2: Generate New Examples

Create 12 example questions (4 displayed at a time, rotated) that:
- Showcase Brubru's strongest areas (guides with most triggers and best content)
- Cover different patterns: explain, status, who_is, drafting
- Are practical and specific (not generic like "Tell me about EU policy")
- Include at least 2 non-English examples (show multilingual capability)
- Demonstrate unique Brubru value: document retrieval, amendment drafting, lobbying strategy

Good examples:
- "What documents were adopted in the pharma reform trilogue?"
- "Draft amendment ideas for Article 5 of the AI Act"
- "Who is the rapporteur for the Chips Act and what's the timeline?"
- "Quels sont les principaux changements du paquet ferroviaire?"

Bad examples (too generic):
- "Tell me about EU law"
- "What is the European Parliament?"

### Step 3: Update Database

```sql
-- Deactivate old examples
UPDATE chat_example_prompts SET is_active = false WHERE scope = 'main_chat';

-- Insert new examples (present these to user for approval before executing)
INSERT INTO chat_example_prompts (question_text, scope, is_active, category, display_order)
VALUES ('...', 'main_chat', true, 'featured', 1);
```

**CRITICAL**: Present all proposed questions to the user and wait for approval before executing any INSERT/UPDATE.

---

## Phase: System Prompt Audit (`/training system`)

Stress-test the system prompt rules to ensure the AI follows them correctly.

### Step 1: Review System Prompt

Read the system prompt from `backend/services/ai_service.py`. Extract all rules (lines containing NEVER, ALWAYS, MUST).

### Step 2: Generate Adversarial Queries

Create queries designed to trigger bad behaviours the system prompt prohibits:

| Rule | Test query | Expected behaviour | Bad behaviour |
|------|-----------|-------------------|---------------|
| Document retrieval | "Give me the COM text for the pharma reform" | Present COM(2023)193 with link | "Search EUR-Lex yourself" |
| Greeting handling | "Hi, who are you?" | Introduce as Brubru | Parse as EU policy query |
| Language matching | "Que es l'Acta d'IA?" | Respond in Catalan | Respond in English |
| Don't say "I don't have" | "What is the status of the Novel Food regulation?" | Use guide content | "I don't have information" |
| British English | "How does the AI Act affect organisations?" | "organisations" not "organizations" | American spelling |

### Step 3: Test Against Knowledge Base

For each adversarial query, check:
1. Does the correct guide match?
2. Does the guide contain the information needed to answer correctly?
3. Would the AI have enough context to follow the system prompt rule?

### Step 4: Review Context Builder

Read `backend/services/ai/context_builder.py` and check:
- **Truncation limits**: Guide content truncated at 4000 chars in `format_context_for_ai`. Is QUICK FACTS within this limit for all top 20 guides?
- **Search results limit**: How many guides are injected? (max 3 from triggers)
- **Tavily fallback**: Does it fire for the remaining gap topics?
- **OEIL enrichment**: Does it trigger on procedure-intent keywords?

```python
# Check if QUICK FACTS fits within truncation for top guides
from knowledge_base.knowledge_loader import KnowledgeLoader
import re

kl = KnowledgeLoader()
kl.load_all()

for gid, content in kl.guides.items():
    qf_match = re.search(r'## QUICK FACTS\n(.*?)(?=\n## )', content, re.DOTALL)
    if qf_match:
        qf_end = qf_match.end()
        if qf_end > 4000:
            print(f"WARNING: {gid} QUICK FACTS ends at char {qf_end} (>4000, will be truncated)")
```

### Step 5: Report

```
SYSTEM PROMPT AUDIT: YYYY-MM-DD
  Rules extracted: N
  Adversarial tests: M
  Context builder checks:
    - Truncation: X guides at risk
    - QUICK FACTS within limit: Y/Z
    - Tavily fallback: configured for N domains
  Issues found: [list]
  Fixes applied: [list]
```

---

## Important Notes (apply to all phases)

- Use `python3.12` (not `python3`)
- Default to 10 synthetic queries per round unless the user specifies a different number
- Vary languages: at least 2 queries in non-English languages per round
- Focus synthetic queries on **areas the chatbot is weakest** (check previous audit findings)
- This skill does NOT send emails or modify the database (except `/training prompts` which updates chat_example_prompts with user approval)
- After implementing fixes to guides or triggers, always run `python3.12 scripts/generate_guides_html.py`
- Do NOT start the backend server from this skill
- Present all proposals before implementing; wait for user OK
- The database is READ-ONLY via the postgres MCP tool. Use it for analysis queries only. For writes (example prompts), present the SQL and ask the user to confirm.

---

## Phase: API Dogfooding (`/training api`)

Treat Brubru as a customer of its own public v1 API. Run 50 representative user queries, for each one dispatch the v1 API call that would answer it, and verify the response is usable.

### Dataset

`data/training/api_queries_50.json` — 50 queries covering every v1 endpoint, multilingual (EN/ES/CA/FR/...), with per-query `endpoints` describing:
- `path` (relative, e.g. `/api/v1/laws`)
- `params` (query string)
- `method` (optional, defaults to GET)
- `body` (for POST endpoints)
- `expect_min_items` / `expect_min_size_bytes` / `expect_keys` — success criteria
- `allow_500` / `allow_502` — known-soft failure modes

### Runner

```python
import json, os, sys, time, urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://brubru-production.up.railway.app"
API_KEY = os.environ.get("BRUBRU_API_KEY") or <load from .env via grep|cut>
DATASET = Path("/Users/victorsole/Developer/brubru/data/training/api_queries_50.json")

queries = json.loads(DATASET.read_text())["queries"]

def hit(path, params=None, method="GET", body=None, timeout=30):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, method=method)
    req.add_header("Authorization", f"Bearer {API_KEY}")
    req.add_header("Accept", "application/json")
    data = None
    if body is not None:
        req.add_header("Content-Type", "application/json")
        data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as r:
            return r.getcode(), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as exc:
        return 0, str(exc).encode()

results = []
for q in queries:
    ep = q["endpoints"][0]
    t0 = time.time()
    status, body = hit(ep["path"], ep.get("params"), ep.get("method", "GET"), ep.get("body"))
    ms = int((time.time() - t0) * 1000)

    ok = False
    reason = ""
    if status == 200:
        ok = True
        try:
            data = json.loads(body)
            if "expect_min_items" in ep:
                items = data.get("data", data.get("sources", data.get("aliases", data.get("refs", []))))
                count = len(items) if isinstance(items, list) else 0
                ok = count >= ep["expect_min_items"]
                reason = f"items={count}"
            elif "expect_min_size_bytes" in ep:
                ok = len(body) >= ep["expect_min_size_bytes"]
                reason = f"size={len(body)}B"
            elif "expect_keys" in ep:
                ok = all(k in data for k in ep["expect_keys"])
                reason = f"keys={list(data.keys())[:5]}"
        except Exception as exc:
            ok = False
            reason = f"parse_error: {exc}"
    elif status == 500 and ep.get("allow_500"):
        ok = True; reason = "known 500 (tolerated)"
    elif status == 502 and ep.get("allow_502"):
        ok = True; reason = "upstream unavailable (tolerated)"
    else:
        reason = f"HTTP {status}"

    results.append({"id": q["id"], "pattern": q["pattern"], "lang": q["lang"], "query": q["query"], "path": ep["path"], "status": status, "ms": ms, "ok": ok, "reason": reason})
    mark = "[OK]" if ok else "[--]"
    print(f"{mark:5s} #{q['id']:2d} {q['lang']}  {q['pattern']:18s}  {status:3d}  {ms:5d}ms  {reason}")

passed = sum(1 for r in results if r["ok"])
print(f"\nCoverage: {passed}/{len(results)} ({passed*100//len(results)}%)")
```

### Step 1: Run the dataset

Use the exact API key minted for Brubru-the-app (the same key the chatbot would use when it starts calling the API internally in Phase 2). Report results as a table, sorted by pattern.

### Step 2: Diagnose failures

For each `[--]` row:
- **HTTP 404** on knowledge-guides detail → guide ID in the query doesn't exist. Either fix the query or add a redirect trigger.
- **HTTP 404** on laws/{celex}/text → missing from eu_laws OR xml_path missing OR Cellar fallback failed. Check which.
- **HTTP 404** on predictions/{ref}/* → OEIL procedure not in `legislative_carriages` table. Not fixable here; flag as data freshness issue.
- **HTTP 500** on legal-text/recital-article-map for GDPR → known backend bug; separate session.
- **items=0** where expected >= 1 → real coverage gap. Open as an issue. Either the data isn't there or the filter is wrong.
- **parse_error** → response shape changed. Fix the Pydantic model or update the expected-keys list.

### Step 3: Report

Group results by pattern. Flag any pattern where < 80% of queries pass. That's the weak point to fix first.

```
DOGFOOD REPORT: YYYY-MM-DD
  Queries run:          50
  Passed:               41 (82%)
  Failed:               9

  By pattern:
    explain_topic       8/8 OK
    list_request        14/15
    procedure_lookup    7/10
    contacts_lookup     3/6
    impact_analysis     3/3
    agenda_calendar     2/3

  Failures by cause:
    missing data        3 (predictions, certain committee minutes)
    wrong guide id      1 (knowledge-guides detail)
    upstream error      2 (meps — EP Open Data 502)
    known backend bug   1 (legal-text/recital-article-map GDPR)

  Next actions:
    - Redirect wrong guide ids in the query dataset
    - Widen predictions to accept any procedure ref (fallback to OEIL fetch)
    - Retry flaky EP Open Data calls with backoff
```

### Step 4: Log

Append results to `memory/query_audit.md` under a "Dogfood API" section with the date, pass rate, and list of failing query IDs. Track the pass rate over time — week-on-week improvement is the single metric that matters.

### Notes

- Do NOT run the dataset against localhost. Always use production so results reflect what a paying partner experiences.
- Use a dedicated `BRUBRU_API_KEY` in `.env` for Brubru-the-app's internal API use. Never reuse Jordi's GovClipping key.
- Keep the 50 queries short and representative. When new endpoints land, add 2-4 queries that exercise them. Remove queries that are perpetually broken for structural (not data) reasons.
