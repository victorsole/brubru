"""End-to-end test of the "Brubru DPP" MCP server at /api/mcp/dpp.

Exercises the real JSON-RPC transport against the real database with an admin
key (billing-exempt), and asserts the things that actually break MCP servers:

  * the `initialize` result carries serverInfo with name+version ONLY. Extra
    fields there once broke the claude.ai connector, and the factory means one
    mistake would now break every mounted server at once.
  * the two servers stay distinct: different names, different tool counts.
  * every tool returns without raising, and returns something non-empty.
  * `search` then `fetch` round-trips, because ChatGPT depends on that pair.
  * OAuth discovery names the DPP resource, not /api/mcp.
"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from dotenv import load_dotenv

load_dotenv(root.parent / ".env")

from fastapi.testclient import TestClient
from sqlalchemy import text

from core.database import SessionLocal
from main import app

client = TestClient(app)
MAIN, DPP = "/api/mcp", "/api/mcp/dpp"

passed = failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


def rpc(path, method, params=None, key=None):
    url = f"{path}?key={key}" if key else path
    body = {"jsonrpc": "2.0", "id": 1, "method": method}
    if params is not None:
        body["params"] = params
    return client.post(url, json=body).json()


def admin_key():
    """A plaintext admin key, minted fresh so the test never depends on one."""
    import uuid as _uuid

    from models.api_key import ApiKey

    db = SessionLocal()
    try:
        uid = db.execute(
            text("SELECT id FROM users WHERE role = 'admin' ORDER BY created_at LIMIT 1")
        ).scalar()
        if not uid:
            return None
        plaintext, inst = ApiKey.generate(
            _uuid.UUID(str(uid)), name="test_dpp_mcp (ephemeral)",
            scopes=["*"], expires_in_days=None,
        )
        db.add(inst)
        db.commit()
        return plaintext, inst.id
    finally:
        db.close()


def revoke(key_id):
    db = SessionLocal()
    try:
        db.execute(text("UPDATE api_keys SET revoked_at = now() WHERE id = :i"),
                   {"i": key_id})
        db.commit()
    finally:
        db.close()


print("=== identity: two servers, one transport ===")
for path, name, count in ((MAIN, "Brubru", 15), (DPP, "Brubru DPP", 11)):
    res = rpc(path, "initialize", {"protocolVersion": "2024-11-05"})["result"]
    check(f"{path} serverInfo.name == {name!r}", res["serverInfo"]["name"] == name,
          str(res["serverInfo"]))
    check(f"{path} serverInfo has name+version ONLY (connector landmine)",
          set(res["serverInfo"]) == {"name", "version"}, str(res["serverInfo"]))
    probe = client.get(path).json()
    check(f"{path} probe reports {count} tools", probe["tools_available"] == count,
          str(probe["tools_available"]))

print("\n=== OAuth discovery names the right resource ===")
d = client.get("/.well-known/oauth-protected-resource/api/mcp/dpp").json()
check("DPP discovery resource ends /api/mcp/dpp",
      d.get("resource", "").endswith("/api/mcp/dpp"), d.get("resource"))
d2 = client.get("/.well-known/oauth-protected-resource/api/mcp").json()
check("main discovery still ends /api/mcp",
      d2.get("resource", "").endswith("/api/mcp"), d2.get("resource"))
check("DPP discovery advertises the same authorization server",
      d.get("authorization_servers") == d2.get("authorization_servers"))


print("\n=== the 401 challenge must name THIS resource ===")
import re as _re
for _path, _expect in ((MAIN, "/api/mcp"), (DPP, "/api/mcp/dpp")):
    _r = client.post(_path, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    _hdr = _r.headers.get("WWW-Authenticate", "")
    _m = _re.search(r'resource_metadata="([^"]+)"', _hdr)
    check(f"{_path} 401 carries a resource_metadata pointer", bool(_m), _hdr)
    if _m:
        _doc = client.get(_m.group(1).split("testserver", 1)[1]).json()
        # A fixed pointer here would send a DPP client to metadata declaring
        # /api/mcp, binding its OAuth token to the wrong audience.
        check(f"{_path} challenge declares {_expect}",
              _doc.get("resource", "").endswith(_expect), _doc.get("resource"))
# the bare document must survive for clients that probe it directly
_bare = client.get("/.well-known/oauth-protected-resource")
check("bare oauth-protected-resource still served", _bare.status_code == 200,
      str(_bare.status_code))

minted = admin_key()
if not minted:
    print("\n[SKIP] no admin user; cannot exercise tools")
    sys.exit(1 if failed else 0)
KEY, KEY_ID = minted

try:
    print("\n=== tools/list ===")
    tools = rpc(DPP, "tools/list", key=KEY)["result"]["tools"]
    names = [t["name"] for t in tools]
    check("DPP lists 11 tools", len(tools) == 11, str(len(tools)))
    check("every tool has a description and schema",
          all(t.get("description") and t.get("inputSchema") for t in tools))
    check("search + fetch present (ChatGPT requires the pair)",
          {"search", "fetch"} <= set(names), str(names))
    check("the gateway is NOT exposed here (it 401s over OAuth)",
          "query_brubru_api" not in names)

    print("\n=== every tool runs ===")
    CALLS = [
        ("ask_dpp", {"question": "When does the textile passport become mandatory?"}),
        ("dpp_law", {"query": "registry"}),
        ("dpp_when", {"sector": "textile"}),
        ("dpp_data_points", {"query": "carbon footprint"}),
        ("dpp_standards", {}),
        ("dpp_registry", {}),
        ("dpp_updates", {"limit": 5}),
        ("dpp_consultations", {"query": "textile"}),
        ("dpp_forum", {}),
        ("search", {"query": "unique registration identifier"}),
    ]
    for name, args in CALLS:
        out = rpc(DPP, "tools/call", {"name": name, "arguments": args}, key=KEY)
        ok = "result" in out and not out.get("error")
        body = str(out.get("result", out))[:70]
        check(f"{name} returns without error", ok, str(out.get("error"))[:110])
        if ok:
            check(f"  {name} returns content", len(str(out["result"])) > 60, body)

    print("\n=== search -> fetch round-trip (the ChatGPT path) ===")
    s = rpc(DPP, "tools/call",
            {"name": "search", "arguments": {"question": "x", "query": "ESPR"}}, key=KEY)
    import json as _json

    txt = s["result"]["content"][0]["text"]
    results = _json.loads(txt).get("results", [])
    check("search returns results", len(results) > 0, txt[:100])
    if results:
        first = results[0]["id"]
        f = rpc(DPP, "tools/call", {"name": "fetch", "arguments": {"id": first}}, key=KEY)
        ftxt = _json.loads(f["result"]["content"][0]["text"])
        check(f"fetch({first}) returns text", bool(ftxt.get("text")),
              str(ftxt)[:110])


    print("\n=== response size: an MCP result goes straight into a context ===")
    import json as _j
    from services.mcp.dpp_tools import handle_dpp_law, handle_fetch, handle_dpp_data_points

    def _tok(obj):
        return len(_j.dumps(obj, default=str)) // 4

    # The regression this guards: dpp_law(query='textile', full_text=True) once
    # returned SIX acts of full legal text, 285,000 tokens, and fetch on the ESPR
    # returned 91,000. Both "worked" and both would have broken the client.
    check("dpp_law with a broad query + full_text stays small (returns a choice)",
          _tok(handle_dpp_law(query="textile", full_text=True)) < 4_000)
    check("dpp_law on one act is capped under 15k tokens",
          _tok(handle_dpp_law(celex="32024R1781", full_text=True)) < 15_000)
    check("dpp_law contains= returns passages, not the act",
          _tok(handle_dpp_law(celex="32026R1778", contains="granularity")) < 8_000)
    check("fetch on an act is capped under 15k tokens",
          _tok(handle_fetch("dpp:1842784")) < 15_000)
    check("dpp_data_points (all 71) stays under 25k tokens",
          _tok(handle_dpp_data_points()) < 25_000)

    print("\n=== scoping: a main-server tool must NOT exist here ===")
    out = rpc(DPP, "tools/call",
              {"name": "search_sanctions", "arguments": {"query": "x"}}, key=KEY)
    check("search_sanctions is unknown on the DPP server",
          bool(out.get("error")), str(out)[:110])
finally:
    revoke(KEY_ID)
    print("\n[cleanup] ephemeral test key revoked")

print(f"\n=== {passed} passed / {failed} failed ===")
sys.exit(1 if failed else 0)
