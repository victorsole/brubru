"""
Dogfood Brubru Chat with FerrMed-flavoured queries.

Hits production /api/chat/message and prints answer head + retrieval signals
so we can quickly tell whether each query lands on the right guide.

Usage:
    python3.12 scripts/dogfood_ferrmed_chat.py
    python3.12 scripts/dogfood_ferrmed_chat.py --local      # hit localhost:8000
    python3.12 scripts/dogfood_ferrmed_chat.py --verbose    # print full answers
"""

import argparse
import json
import sys
import time
import uuid
import urllib.request
import urllib.error

PROD_URL = "https://brubru-production.up.railway.app/api/chat/message"
LOCAL_URL = "http://localhost:8000/api/chat/message"

QUERIES = [
    "What's the status of the high-speed rail INI 2026/2003 — Connecting Europe Through High-Speed Rail?",
    "Tell me about the rail infrastructure capacity reform — Improving use of rail infrastructure capacity 2023/0271(COD). Where is it in the procedure?",
    "What is the Combined Transport directive revision? What's the current state of the file?",
    "What is the Military Mobility Action Plan 3.0 and what does it mean for rail freight infrastructure?",
    "What are the ERTMS deployment deadlines under Decision 2023/1095?",
    "What is the CEF Transport budget envelope for 2021-2027 and what's the rail share?",
    "What does the TEN-T Regulation 2024/1679 say about the Mediterranean Corridor — what's the deadline and what are the key missing links?",
    "What is the HGV CO2 emission class for trailers proposal 2023/0134(COD)?",
    "What is CountEmissionsEU (2023/0266 COD) and why does it matter for the rail freight modal share?",
    "How can Brubru help FERRMED ASBL track legislative files relevant to rail freight, intermodal, and military mobility — given FERRMED has 5.5 FTE lobbyists and 3 EP-accredited passholders?",
]


def fire(url: str, message: str, timeout: float = 180.0) -> dict:
    body = json.dumps(
        {
            "message": message,
            "chat_id": str(uuid.uuid4()),
            "use_context": True,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Brubru-Dogfood/1.0"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            data["_latency_s"] = round(time.time() - t0, 1)
            data["_http_status"] = resp.status
            return data
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.reason}", "_latency_s": round(time.time() - t0, 1)}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}", "_latency_s": round(time.time() - t0, 1)}


def evaluate(answer: str, expected_signals: list) -> tuple[int, list]:
    """Return (hit_count, missing) for keyword/regex signals in answer."""
    lower = (answer or "").lower()
    hits = []
    miss = []
    for sig in expected_signals:
        if sig.lower() in lower:
            hits.append(sig)
        else:
            miss.append(sig)
    return len(hits), miss


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", action="store_true", help="Hit localhost:8000 instead of production.")
    parser.add_argument("--verbose", action="store_true", help="Print full answers.")
    args = parser.parse_args()

    url = LOCAL_URL if args.local else PROD_URL
    print(f"=== Dogfooding Brubru Chat for FerrMed ===")
    print(f"Endpoint: {url}")
    print(f"Queries:  {len(QUERIES)}")
    print()

    # Expected signal keywords per query (the words a *good* answer should contain).
    expected = [
        ["high-speed rail", "INI", "TRAN"],
        ["capacity", "rail infrastructure", "2023/0271"],
        ["combined transport", "directive"],
        ["military mobility", "dual-use", "CEF"],
        ["ERTMS", "2030", "decision"],
        ["CEF", "transport", "1.69"],
        ["TEN-T", "Mediterranean", "2030"],
        ["heavy-duty", "CO2", "trailer"],
        ["CountEmissions", "transport", "measure"],
        ["FERRMED", "rail freight", "intermodal"],
    ]

    rows = []
    for i, q in enumerate(QUERIES, 1):
        print(f"[{i:2}/{len(QUERIES)}] {q[:100]}{'...' if len(q) > 100 else ''}")
        sys.stdout.flush()
        result = fire(url, q)
        if "_error" in result:
            print(f"   ERROR: {result['_error']}  ({result['_latency_s']}s)")
            rows.append({"q": q, "ok": False, "reason": result["_error"]})
            continue

        answer = result.get("response") or result.get("message") or ""
        latency = result["_latency_s"]
        hit, missing = evaluate(answer, expected[i - 1])
        verdict = "PASS" if hit >= 2 else ("PARTIAL" if hit == 1 else "FAIL")
        head = answer[:200].replace("\n", " ")
        print(f"   [{verdict}]  signals={hit}/{len(expected[i-1])}  missing={missing}  latency={latency}s")
        if args.verbose:
            print(f"   ── ANSWER ──\n{answer}\n   ────────────")
        else:
            print(f"   {head}{'…' if len(answer) > 200 else ''}")
        print()
        rows.append({"q": q, "verdict": verdict, "hits": hit, "missing": missing, "latency": latency})

    # Summary
    passes = sum(1 for r in rows if r.get("verdict") == "PASS")
    partials = sum(1 for r in rows if r.get("verdict") == "PARTIAL")
    fails = sum(1 for r in rows if r.get("verdict") == "FAIL")
    errors = sum(1 for r in rows if not r.get("verdict"))
    print("=" * 70)
    print(f"SUMMARY  PASS={passes}  PARTIAL={partials}  FAIL={fails}  ERROR={errors}  (of {len(QUERIES)})")
    print("=" * 70)


if __name__ == "__main__":
    main()
