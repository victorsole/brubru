"""End-to-end test of /api/v2/dpp against the real database.

Auth is overridden so the test exercises the handlers and the data, not the API-key
plumbing. Asserts the canonical contract: list nulls the body, detail returns it, and
every law carries full text.
"""
import sys
from pathlib import Path

root = Path("/Users/victorsole/Documents/GitHub/brubru")
sys.path.insert(0, str(root / "backend"))

from dotenv import load_dotenv

load_dotenv(root / ".env")

from fastapi.testclient import TestClient

from main import app
from api.v1._deps import api_user_with_rate_limit
from models.user import User


def _fake_user():
    u = User()
    u.id = "test"
    u.email = "test@brubru.local"
    u.subscription_tier = "blue"
    u.is_admin = True
    return u


app.dependency_overrides[api_user_with_rate_limit] = _fake_user
client = TestClient(app)

RESOURCES = ["legal-framework", "sectors", "registry", "standards",
             "data-points", "guidance", "audiences", "news", "events"]

passed = failed = 0


def check(label, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS  {label}")
    else:
        failed += 1
        print(f"  FAIL  {label}  {detail}")


print("=== directory ===")
r = client.get("/api/v2/dpp")
check("GET /api/v2/dpp returns 200", r.status_code == 200, r.text[:120])
if r.status_code == 200:
    body = r.json()
    counts = body[0]["item_counts"] if body else {}
    print(f"        item_counts = {counts}")
    check("directory reports a non-empty item_counts", bool(counts))

print("\n=== list endpoints (body must be NULL on list) ===")
first_ids = {}
for res in RESOURCES:
    r = client.get(f"/api/v2/dpp/{res}?limit=3")
    if r.status_code != 200:
        check(f"GET /{res}", False, f"HTTP {r.status_code} {r.text[:90]}")
        continue
    env = r.json()
    items = env.get("data") or env.get("items") or []
    total = env.get("total") or env.get("meta", {}).get("total")
    check(f"GET /{res} -> 200, total={total}", True)
    check(f"  /{res} is NOT empty", (total or 0) > 0, "resource has no rows")
    if items:
        first_ids[res] = items[0]["id"]
        it = items[0]
        check(f"  /{res} list has the 5 datapoints",
              all(k in it for k in
                  ("public_url", "body_txt", "body_html", "document_date", "creation_date")),
              str(sorted(it.keys())))
        check(f"  /{res} list nulls body_txt (cheap list)", it["body_txt"] is None)
        check(f"  /{res} list carries public_url", bool(it["public_url"]))

print("\n=== detail endpoints (body must be POPULATED) ===")
for res, iid in first_ids.items():
    r = client.get(f"/api/v2/dpp/{res}/{iid}")
    if r.status_code != 200:
        check(f"GET /{res}/{iid}", False, f"HTTP {r.status_code}")
        continue
    it = r.json()
    check(f"/{res}/{iid} body_txt populated",
          bool(it.get("body_txt")), f"len={len(it.get('body_txt') or '')}")
    check(f"/{res}/{iid} body_html populated", bool(it.get("body_html")))

print("\n=== every law carries FULL TEXT, no exceptions ===")
r = client.get("/api/v2/dpp/legal-framework?limit=100")
laws = r.json().get("data", [])
check("legal-framework returns 13 acts", len(laws) == 13, f"got {len(laws)}")
short = []
for law in laws:
    d = client.get(f"/api/v2/dpp/legal-framework/{law['id']}").json()
    n = len(d.get("body_txt") or "")
    if n < 5000 or "FULL TEXT" not in (d.get("body_txt") or ""):
        short.append((law["title"][:48], n))
check("every act body is full text (>5k chars, marked FULL TEXT)",
      not short, f"thin: {short}")
if laws:
    sizes = sorted((len(client.get(f"/api/v2/dpp/legal-framework/{x['id']}").json()["body_txt"])
                    for x in laws))
    print(f"        act body sizes: min={sizes[0]:,} median={sizes[len(sizes)//2]:,} max={sizes[-1]:,}")

print("\n=== search hits the body ===")
r = client.get("/api/v2/dpp/legal-framework?q=unique registration identifier&limit=5")
hits = r.json().get("data", [])
check("q= searches into body_txt", len(hits) >= 1, f"got {len(hits)}")
print(f"        matched: {[h['title'][:44] for h in hits][:3]}")

print("\n=== 404 on a bad id ===")
r = client.get("/api/v2/dpp/sectors/99999999")
check("unknown id returns 404", r.status_code == 404, f"HTTP {r.status_code}")

print(f"\n=== {passed} passed / {failed} failed ===")
sys.exit(1 if failed else 0)
