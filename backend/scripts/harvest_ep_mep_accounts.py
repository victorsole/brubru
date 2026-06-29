"""Phase 4.2.1 step 2 — harvest official MEP social accounts from the EP Open Data API.

Pulls the current-MEP list (/api/v2/meps/show-current) then each MEP's detail (/api/v2/meps/{id}),
extracts the official `account` array (OnlineAccount: url + dcterms_type authority code), and
caches everything to JSON. Pure fetch, no DB writes. Paced + retried (EP API occasionally
read-times-out).
"""
import json
import sys
import time
import urllib.request

H = {"User-Agent": "BrubruBot/1.0 (https://brubru.beresol.eu; hello@beresol.eu)",
     "Accept": "application/ld+json"}
BASE = "https://data.europarl.europa.eu/api/v2/meps"
OUT = sys.argv[1] if len(sys.argv) > 1 else "ep_mep_accounts.json"


def get(u, tries=4):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception:
            time.sleep(2)
    return None


def main():
    cur = get(f"{BASE}/show-current")
    meps = cur["data"]
    print(f"current MEPs: {len(meps)}", flush=True)
    out = []
    for i, m in enumerate(meps):
        mid = m["identifier"]
        d = get(f"{BASE}/{mid}")
        rec = {"ep_id": mid, "label": m.get("label"),
               "givenName": m.get("givenName"), "familyName": m.get("familyName"),
               "country": m.get("api:country-of-representation"),
               "group": m.get("api:political-group"), "accounts": []}
        if d and d.get("data"):
            for a in d["data"][0].get("account", []):
                rec["accounts"].append({"url": a.get("id"),
                                        "type": (a.get("dcterms_type") or "").split("/")[-1]})
        out.append(rec)
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{len(meps)}", flush=True)
        time.sleep(0.4)
    json.dump(out, open(OUT, "w"), ensure_ascii=False)
    n_acc = sum(len(r["accounts"]) for r in out)
    n_with = sum(1 for r in out if r["accounts"])
    print(f"DONE: {len(out)} MEPs, {n_with} with >=1 account, {n_acc} accounts -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
