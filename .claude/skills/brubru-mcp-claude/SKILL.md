---
name: brubru-mcp-claude
description: Everything about the Brubru MCP and connecting it to Claude (and other hosts). The canonical endpoint, the tool surface, the three auth methods + host matrix (why claude.ai web needs ?key=), how to mint a user a key, connector branding, verification curls, and troubleshooting. Use when connecting a user/prospect to Brubru MCP in Claude, debugging "no tools available", minting an MCP key, or extending the MCP to a new host.
argument-hint: ["connect" (default, walk a user through Claude) | "verify" | "mint <email>" | "troubleshoot"]
allowed-tools: ["Read", "Bash", "Edit", "mcp__postgres__query"]
---

# Brubru MCP — connect to Claude (and beyond)

The Brubru MCP exposes Brubru's EU-policy intelligence to any AI assistant as MCP
tools. This skill is the operational + reference guide for wiring it into Claude,
minting keys, branding the connector, verifying, and troubleshooting. It also
carries the hard-won "how it actually works across hosts" knowledge so we can turn
it into the reusable Beresol "any API -> MCP" playbook.

Full background: `memory/project_brubru_mcp_everywhere_2026_07.md` +
`memory/project_mcp_simplification_2026_07_28.md`.

## Canonical facts (do not get these wrong)

- **Endpoint = the Railway ORIGIN:** `https://brubru-production.up.railway.app/api/mcp`
  - `https://brubru.beresol.eu/api/mcp` **DOES NOT WORK** — SiteGround serves the SPA
    there; `/api/*` is not proxied to the backend. Always use the Railway URL.
- **Transport:** hand-rolled JSON-RPC 2.0 over HTTP POST (`backend/api/mcp_http.py`).
  Verified compatible with the claude.ai web connector. `initialize` is unauthenticated;
  `tools/list` and `tools/call` require the key.
- **Tool surface (one front door):** `ask_brubru` is PRIMARY — one free-text question
  returns matching policy guides + relevant EU laws (CELEX + EUR-Lex) + live procedure
  status. Five advanced tools remain (search_eu_legislation, search_knowledge_guides,
  get_procedure_status, get_calendar_events, search_eprs). Registry: `services/mcp/tools.py`.
- **Counts are runtime-computed** (`services/mcp/stats.py`) — never hardcode them.
- **Billing:** each call debits the key owner's euro balance, EXCEPT `role=admin`
  users, who are billing-exempt.

## Auth — three methods, and the host matrix

Key precedence (`_extract_key` in `mcp_http.py`), highest first:
1. `Authorization: Bearer brubru_live_...`  (most secure)
2. `X-API-Key: brubru_live_...`
3. `?key=brubru_live_...` / `?api_key=...`  in the URL

**Why the query string matters (the core lesson):** claude.ai's "Add custom connector"
dialog (web AND Desktop Connectors UI) only offers **OAuth Client ID/Secret** — there
is NO field for a bearer header. So the key must ride in the URL. Same pattern as
Tavily (`mcp.tavily.com/mcp/?tavilyApiKey=...`). Keys-in-URL is less private (logs,
history) — fine for a revocable admin/test key, but OAuth is the eventual answer.

| Host | Connector UI accepts | Connect with |
|---|---|---|
| claude.ai web / Desktop (Connectors UI) | URL (+ optional OAuth) | `?key=` URL |
| Claude Desktop (Edit Config JSON) | `url` + `headers` | Bearer header |
| Cursor / Cline / Continue / VS Code | JSON config | Bearer header |
| ChatGPT / Gemini / DeepSeek | (to validate) | `?key=` URL or the OpenAPI Action |

## Sub-command: connect (default) — walk a user through Claude

1. **Get/mint a key** (see "mint" below). Confirm whether the user is admin (exempt)
   or needs balance (blue tier top-up).
2. **Give them the ready URL** (key in the query string):
   ```
   https://brubru-production.up.railway.app/api/mcp?key=<their_brubru_live_key>
   ```
3. **claude.ai (web or Desktop) — Connectors UI:**
   - Settings -> Connectors -> Add custom connector.
   - Name: `Brubru`. URL: the `?key=` URL above. Leave the OAuth fields **blank**.
   - Connect -> should show **6 tools** (ask_brubru + 5). New chat -> `@Brubru` or just ask.
4. **Claude Desktop config file** (alternative, header auth) — Settings -> Developer ->
   Edit Config, then merge:
   ```json
   { "mcpServers": { "brubru": {
       "url": "https://brubru-production.up.railway.app/api/mcp",
       "headers": { "Authorization": "Bearer brubru_live_..." } } } }
   ```
   Fully quit + reopen Claude Desktop.
5. Ask a real question to prove it end-to-end, e.g. "What's the status of the AI Act?".

## Sub-command: mint <email> — issue a key

Look up the user, then mint. Admins are billing-exempt; others need balance.
```python
# python3.12 from backend/ ; user_id from: SELECT id,role FROM users WHERE email=...
import uuid
from core.database import SessionLocal
from models.api_key import ApiKey
db = SessionLocal()
plaintext, inst = ApiKey.generate(uuid.UUID("<user_id>"),
    name="MCP <purpose> <date>", scopes=["*"], expires_in_days=None)
db.add(inst); db.commit(); print(plaintext)   # plaintext shown ONCE — hashed at rest
```
Give the plaintext to the user; treat it like a password. Revoke before any demo/share
(`UPDATE api_keys SET revoked_at=now() WHERE id=...` or via /api). The key is a secret:
never place another user's key in a URL you send them beyond their own.

## Sub-command: verify — prove the endpoint live

```bash
KEY=brubru_live_...
URL="https://brubru-production.up.railway.app/api/mcp"
# probe (no auth)
curl -s "$URL" | python3 -m json.tool
# tools/list via ?key= (no headers) — must return 6 tools
curl -s -X POST "$URL?key=$KEY" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
# tools/call the front door
curl -s -X POST "$URL?key=$KEY" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"ask_brubru","arguments":{"question":"What is CBAM?"}}}'
```

## Connector branding (the logo) — UNSOLVED, and a landmine

Claude's connector shows the **Railway icon**, not Brubru's. Two attempts failed
(30 Jul), and one of them broke everything — read before touching:

- **Origin favicon does NOT work.** The backend serves `/favicon.ico` + `/favicon.png`
  (`backend/main.py`), but claude.ai does not use the backend origin favicon for the
  connector icon — it still shows Railway after a clean re-add. Harmless, left in place.
- **NEVER add `icons`/`websiteUrl`/`title` to `initialize.serverInfo`.** Doing so
  (commit 2fe721f3) BROKE the claude.ai connector: Claude validates the initialize
  result, rejected the extra Implementation fields, treated the server as invalid, and
  fell into a failing OAuth-registration flow ("Couldn't register with Brubru's sign-in
  service"). It looks exactly like "claude.ai requires OAuth" but it is NOT — it is a
  malformed handshake. Keep `SERVER_INFO = {name, version}` only. curl-valid does not
  mean claude.ai-client-valid; always test the real connector after any handshake change.

Branding Claude's connector remains an open question (likely OAuth AS metadata
`logo_uri` once Option B lands). Deferred.

## Troubleshooting

- **"This connector has no tools available."** -> almost always (a) a **truncated key**
  (a char dropped on paste — the key ends `...db12e`), or (b) the **wrong URL**
  (brubru.beresol.eu instead of the Railway origin). Rule these out before suspecting
  transport. Verify with the `?key=` `tools/list` curl above.
- **"Couldn't register with Brubru's sign-in service" / "not a valid MCP server"** ->
  the `initialize` handshake is malformed for Claude's validator. Check `SERVER_INFO`
  is `{name, version}` ONLY — extra fields break it (see branding section). NOT an
  OAuth requirement.
- **Wrong/Railway icon** -> known-unsolved; origin favicon does not rebrand Claude's
  connector. Leave it; do not add serverInfo icons to "fix" it (that breaks connect).
- **xlsx/export or import errors on prod but not local** -> prod installs
  `requirements-light.txt`; see `feedback_prod_uses_requirements_light`.
- **Tool call fails with insufficient balance** -> non-admin key with €0 balance; top up
  or use an admin key (exempt).

## Key files

- `backend/api/mcp_http.py` — HTTP JSON-RPC transport, auth (`_extract_key`), serverInfo/icons.
- `backend/services/mcp/tools.py` — tool registry + handlers (ask_brubru router).
- `backend/services/mcp/stats.py` — runtime corpus counts.
- `backend/api/mcp_openapi.py` — ChatGPT custom-GPT OpenAPI spec.
- `backend/main.py` — `/favicon.ico` + `/favicon.png` origin branding.
- `frontend/src/pages/mcp_page.tsx` — the public `/mcp` connect page (6 langs).

## Next: OAuth (Option B — not built yet)

The no-key-in-URL answer, and what ChatGPT/Gemini/DeepSeek connectors also prefer.
claude.ai does OAuth discovery on the origin: `/.well-known/oauth-protected-resource`
+ `/.well-known/oauth-authorization-server` + dynamic client registration + `/authorize`
+ `/token`, then MCP requests carry the issued token mapped to the user's api_key/balance.
This is the reusable substrate to productise as "Beresol makes MCPs out of any API".
