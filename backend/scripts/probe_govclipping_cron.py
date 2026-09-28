"""Call the API exactly as GovClipping's cron does, and print what they would see.

Their endpoint list, their headers, and both the windows they use: the nightly
"scheduled" window (yesterday to now) and the "backfill" window (15 Jul 2024 to now).
Dogfooding this way is what found the incremental-sync defect on 28 Sep 2026: every
call returned 200, so nothing looked wrong, and the TOTALS gave it away. A scheduled
window that returns the same count as a two-year backfill window is the signature of a
change signal that moves on every re-read.

Read the output as a partner would:
  scheduled << backfill   healthy: a day of changes is a small slice of the corpus
  scheduled == backfill   the endpoint reports the whole corpus as changed every night
  scheduled == 0 for days the feed may be stalled, or genuinely quiet: check the source

Run:
    python3.12 scripts/probe_govclipping_cron.py
    python3.12 scripts/probe_govclipping_cron.py --baseline data/logs/govclipping_probe.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = "https://brubru-production.up.railway.app/api/v2"
BACKFILL_FROM = "2024-07-15T19:00:00Z"


def api_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("BRUBRU_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("[FATAL] BRUBRU_API_KEY missing from the repo-root .env")


def endpoints(now: datetime):
    """(label, path, scheduled_params, backfill_params) exactly as their cron sends them."""
    day = (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    week = (now - timedelta(days=8)).strftime("%Y-%m-%dT%H:%M:%SZ")
    to = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    d_from = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    d_to = now.strftime("%Y-%m-%d")
    page = {"page": 1, "limit": 100}

    def win(lo, hi=None):
        p = dict(page, updated_from=lo)
        if hi:
            p["updated_to"] = hi
        return p

    out = []
    for kind in ("press_release", "news"):
        out.append((f"news/all {kind}", "news/all",
                    dict(page, kind=kind, include_body="true", **{"from": d_from, "to": d_to}),
                    dict(page, kind=kind, include_body="true",
                         **{"from": "2024-07-15", "to": d_to})))
    # Both bounds.
    for label, path in [
        ("calendar/events", "calendar/events"),
        ("parliament/webstreams", "parliament/webstreams"),
        ("legislative/eur-lex/laws", "legislative/eur-lex/laws"),
        ("legislative/oeil/procedures", "legislative/oeil/procedures"),
        ("parliament/resolutions", "parliament/resolutions"),
        ("parliament/texts-adopted", "parliament/texts-adopted"),
        ("parliament/texts-submitted", "parliament/texts-submitted"),
        ("commission/consultations", "commission/consultations"),
        ("commission/commission-register-documents", "commission/commission-register-documents"),
        ("council/council-documents", "council/council-documents"),
    ]:
        out.append((label, path, win(day, to), win(BACKFILL_FROM, to)))
    # Lower bound only.
    for label in ["legislative/delegated-acts", "legislative/implementing-acts",
                  "parliament/parliamentary-questions", "parliament/amendments",
                  "commission/tris-notifications", "commission/meetings", "funding/tenders"]:
        out.append((label, label, win(day), win(BACKFILL_FROM)))
    # Weekly cadence on their side.
    out.append(("parliament/eprs", "parliament/eprs", win(week, to), win(BACKFILL_FROM, to)))
    for label in ["commission/rsb-opinions", "parliament/ep-documents"]:
        out.append((label, label, win(week), win(BACKFILL_FROM)))
    # Full scans: scheduled and backfill are the same call.
    for label in ["parliament/votes", "funding/ft-calls-for-proposals",
                  "funding/ft-calls-for-tenders", "commission/infringements",
                  "who-is-who/officials", "parliament/meps"]:
        out.append((label, label, dict(page), dict(page)))
    out.append(("commission/commissioners", "commission/commissioners", {"limit": 100}, {"limit": 100}))
    out.append(("legislative/eurovoc/authority/procedures", "legislative/eurovoc/authority/procedures",
                dict(page, lang="en"), dict(page, lang="en")))
    out.append(("commission/access2markets/countries", "commission/access2markets/countries",
                dict(page, eu_ms_only="true"), dict(page, eu_ms_only="true")))
    out.append(("news/bodies", "news/bodies", {}, {}))
    return out


def call(client, path, params):
    headers = {"X-Request-Id": str(uuid.uuid4())}
    t0 = time.time()
    try:
        r = client.get(f"{BASE}/{path}", params=params, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return {"status": None, "error": f"{type(exc).__name__}: {exc}", "secs": time.time() - t0}
    out = {"status": r.status_code, "secs": round(time.time() - t0, 1)}
    try:
        d = r.json()
        out["total"] = d.get("total")
        data = d.get("data")
        out["got"] = len(data) if isinstance(data, list) else None
    except Exception:
        out["error"] = r.text[:160]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", help="an earlier run's JSON, to show what moved")
    ap.add_argument("--out", default="data/logs/govclipping_probe_latest.json")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    headers = {
        "Authorization": f"Bearer {api_key()}",
        "Accept": "application/json",
        "User-Agent": "GovClipping-cron_new/2.0",
        # Ours, so this traffic is not counted as a real partner's usage.
        "X-Brubru-Probe": "govclipping-dogfood",
    }
    base = {}
    if args.baseline:
        base = json.loads(pathlib.Path(args.baseline).read_text())
        if isinstance(base, list):
            base = {f"{r.get('window')} {r.get('label')}": r for r in base}

    results = {}
    print(f"{'endpoint':44} {'scheduled':>12} {'backfill':>12}  verdict")
    print("-" * 92)
    bad = 0
    with httpx.Client(headers=headers, timeout=120.0, follow_redirects=True) as c:
        for label, path, sched_p, back_p in endpoints(now):
            s = call(c, path, sched_p)
            b = call(c, path, back_p)
            results[f"scheduled {label}"] = dict(s, label=label, window="scheduled")
            results[f"backfill {label}"] = dict(b, label=label, window="backfill")
            st, bt = s.get("total"), b.get("total")
            verdict = "ok"
            if s.get("status") != 200 or b.get("status") != 200:
                verdict = f"HTTP {s.get('status')}/{b.get('status')}"
                bad += 1
            elif st is not None and bt is not None and bt > 0 and st == bt and sched_p != back_p:
                verdict = "*** whole corpus reported as changed"
                bad += 1
            elif st == 0 and sched_p != back_p:
                verdict = "quiet (check the source if it stays 0)"
            prev = base.get(f"scheduled {label}", {}).get("total")
            moved = "" if prev is None or prev == st else f"   was {prev}"
            print(f"{label:44} {str(st):>12} {str(bt):>12}  {verdict}{moved}")
    pathlib.Path(args.out).write_text(json.dumps(results, indent=1))
    print(f"\n{len(results)} calls; {bad} needing attention. Written to {args.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
