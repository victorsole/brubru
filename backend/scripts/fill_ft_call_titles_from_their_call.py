#!/usr/bin/env python3.12
"""Give the F&T calls titled by their code the title of their call (funding standard Phase 3f, register O89, 2 Nov
2026): 57 topics such as CORRUPT or AGRIP-SIMPLE-2026-IM-FRESH-FV, whose title at the portal is the code. The
ingest does the same from now on (ingest_funding_sedia.named_title), so this is once, for the rows the search no
longer returns. Each callTitle is read from the portal's own record of the topic; a topic it does not hold keeps
its title. The title changes, so the row's updated_date moves.

    python3.12 scripts/fill_ft_call_titles_from_their_call.py            # dry run
    python3.12 scripts/fill_ft_call_titles_from_their_call.py --apply --backup b.json
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from sqlalchemy import create_engine, text  # noqa: E402

from ingest_funding_sedia import named_title  # noqa: E402

DETAILS = "https://ec.europa.eu/info/funding-tenders/opportunities/data/topicDetails/{t}.json"
UA = "Brubru/1.0 (+https://brubru.beresol.eu)"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup", help="the old titles, written before any change (required with --apply)")
    args = ap.parse_args(argv)
    if args.apply and not args.backup:
        ap.error("--apply needs --backup")
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        rows = c.execute(text("SELECT topic_id, title FROM ft_calls_for_proposals WHERE title ~ '^[A-Z0-9-]+$'")).fetchall()
    changes, missing = {}, []
    for topic, title in rows:
        try:
            req = urllib.request.Request(DETAILS.format(t=topic.lower()), headers={"User-Agent": UA, "Accept": "application/json"})
            call_title = json.loads(urllib.request.urlopen(req, timeout=60).read())["TopicDetails"].get("callTitle")
        except Exception:  # noqa: BLE001 - a topic the portal does not hold keeps its title
            call_title = None
        new = named_title(title, call_title)
        if new != title:
            changes[topic] = (title, new)
        else:
            missing.append(topic)
        time.sleep(0.2)
    print(f"[INFO] code titles {len(rows)}, to change {len(changes)}, no call title {missing}")
    for topic, (old, new) in list(changes.items())[:60]:
        print(f"  {topic}: {new[:110]}")
    if not args.apply:
        return 0
    pathlib.Path(args.backup).write_text(json.dumps({k: v[0] for k, v in changes.items()}, ensure_ascii=False), encoding="utf-8")
    with engine.begin() as c:
        for topic, (_, new) in changes.items():
            c.execute(text("UPDATE ft_calls_for_proposals SET title = :t WHERE topic_id = :k"), {"t": new, "k": topic})
    print(f"[OK] changed {len(changes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
