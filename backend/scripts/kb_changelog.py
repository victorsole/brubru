#!/usr/bin/env python3.12
"""
Append an entry to the Brubru knowledge-base changelog.

This is the single tool that keeps MEUB > Brubru Databases > Knowledge Guides
("What's new" feed) in sync with the chat knowledge base. Per the hard rule
(set 8 June 2026): every time a chat KB guide is added or materially updated,
log it here so the change is visible in the product, not just in the chatbot.

Entries are stored newest-first in knowledge_base/kb_changelog.json and served
read-only by GET /api/databases/kb-changelog.

Usage:
    python3.12 scripts/kb_changelog.py \
        --action updated \
        --guide eu_customs_reform \
        --title "EU Customs Reform" \
        --summary "Added the EUR 3 handling fee on low-value parcels (Reg 2026/1200)." \
        --refs 32026R1200

    # actions: added | updated | canon | deep_dive
    # --date defaults to today (UTC); pass --date YYYY-MM-DD to override.
    # --refs is repeatable-friendly: pass a comma- or space-separated list.

Idempotency: a duplicate (date, guide, action, summary) is skipped so a re-run
of the morning routine does not double-log.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_CHANGELOG = Path(__file__).resolve().parents[1] / "knowledge_base" / "kb_changelog.json"
_VALID_ACTIONS = {"added", "updated", "canon", "deep_dive"}


def _load() -> dict:
    if not _CHANGELOG.exists():
        return {"_comment": "KB changelog", "entries": []}
    return json.loads(_CHANGELOG.read_text(encoding="utf-8"))


def _save(doc: dict) -> None:
    _CHANGELOG.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse_refs(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for chunk in raw:
        for tok in chunk.replace(",", " ").split():
            tok = tok.strip()
            if tok and tok not in out:
                out.append(tok)
    return out


def add_entry(action: str, guide: str, title: str, summary: str,
              refs: list[str] | None = None, date: str | None = None) -> bool:
    """Append one entry. Returns True if added, False if it was a duplicate."""
    action = action.strip().lower()
    if action not in _VALID_ACTIONS:
        raise SystemExit(f"[ERROR] action must be one of {sorted(_VALID_ACTIONS)}, got {action!r}")
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = {
        "date": date,
        "action": action,
        "guide": guide.strip().removesuffix(".md"),
        "title": title.strip(),
        "summary": summary.strip(),
        "refs": _parse_refs(refs),
    }
    doc = _load()
    entries = doc.setdefault("entries", [])
    for e in entries:
        if (e.get("date"), e.get("guide"), e.get("action"), e.get("summary")) == (
            entry["date"], entry["guide"], entry["action"], entry["summary"]):
            print(f"[INFO] duplicate entry skipped: {entry['guide']} ({entry['date']})")
            return False
    entries.insert(0, entry)  # newest first
    _save(doc)
    print(f"[OK] logged: [{entry['date']}] {entry['action']} {entry['guide']} -- {entry['title']}")
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="Append an entry to the Brubru KB changelog.")
    p.add_argument("--action", required=True, help="added | updated | canon | deep_dive")
    p.add_argument("--guide", required=True, help="guide filename stem, e.g. eu_customs_reform")
    p.add_argument("--title", required=True, help="human-readable title")
    p.add_argument("--summary", required=True, help="one-line summary of what changed")
    p.add_argument("--refs", nargs="*", default=None, help="CELEX/OEIL refs (space or comma separated)")
    p.add_argument("--date", default=None, help="YYYY-MM-DD (defaults to today UTC)")
    args = p.parse_args()
    add_entry(args.action, args.guide, args.title, args.summary, args.refs, args.date)
    return 0


if __name__ == "__main__":
    sys.exit(main())
