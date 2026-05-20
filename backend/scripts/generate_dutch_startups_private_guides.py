"""Generate concise per-startup private guides for the Dutch outreach batch.

Reads data/outreach/dutch_startups_2026_05_20.csv. For each of the 41 rows,
calls Claude Haiku 4.5 with a focused prompt and writes:

  backend/knowledge_base/private_guides/{slug}/
      _meta.json
      00_organisation.md   (~350-500 words; identity + mission + EU exposure + chat framing)

Concise variant of the full /private-guide skill — sufficient to demonstrate
"Brubru already knows you" when the founder later signs up.

Wiring to DB + linking to a real user account is deferred until each startup
actually creates an account (out of scope for this script).

Rules honoured:
  - load_dotenv() at module top (memory: feedback_send_script_dotenv_required.md)
  - No em-dashes anywhere in generated guides (CLAUDE.md hard rule)
  - British English
  - No fabricated quotes / people / dates / CELEX (CLAUDE.md anti-hallucination)
  - Haiku 4.5 model ID: claude-haiku-4-5-20251001
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

CSV_PATH = _ROOT / "data" / "outreach" / "dutch_startups_2026_05_20.csv"
GUIDES_DIR = _ROOT / "backend" / "knowledge_base" / "private_guides"
MODEL_ID = "claude-haiku-4-5-20251001"

HAIKU_PROMPT_TEMPLATE = """You are writing a concise organisation profile for Brubru's private knowledge base.

Brubru is an EU policy AI assistant. This profile will be injected into Brubru's chat context when a member of the named startup logs in, so the assistant opens the conversation already knowing who they are and which EU laws bind them.

Write a 350-500 word markdown profile for the following Dutch startup:

NAME: {name}
CITY: {city}
WEBSITE: {website}
YEAR FOUNDED: {year_founded}
TEAM SIZE: {team_size}
SECTOR: {sector}
SCOPE: {scope}
BUSINESS MODEL: {business_model}
EU LAWS WE'VE MAPPED FOR THEM: {eu_laws_related}

Use exactly these sections, in this order, in clean GitHub-flavoured markdown:

# {name}: Organisation profile

## Identity
- Sector / business model / founded / team size / city
- Use only facts from the structured data above. Do not invent founders, board members, exact addresses, postal codes, or registration numbers.

## What they do
One short paragraph (60-100 words) paraphrasing the scope into plain English. Add 2-3 sentences of plausible product/customer context inferred from the sector and business model. Be careful not to fabricate specific customer names, exact pricing, or unverifiable revenue figures.

## EU policy exposure
List the EU laws above as a bullet list. For each law, add ONE short clause in plain English explaining why it applies to this company (10-25 words per law). Use the exact law names as provided.

## How Brubru should answer questions from this team
3-5 bullets framing the assistant's default stance:
- Which language to default to (Dutch or English; default English; Dutch only if the user writes in Dutch).
- Which of the listed EU laws to anchor on for general "what should we worry about" questions.
- Which adjacent feature (My EU Bubble Calendar / EU Law Comply / Tenderator / Amendator / Predictions) to surface in answers.
- What NOT to fabricate (board members, customers, financial figures, dates we did not confirm).

Hard rules:
- No em-dashes (no character —). Use commas, full stops, colons, or parentheses.
- No emojis.
- British English (analyse, behaviour, optimise, organisation).
- Do not invent founders, board members, addresses, postal codes, registration numbers, exact funding amounts, or customers we did not name in the input.
- Do not claim Brubru "supports 23 EU languages" — we support six (EN, FR, NL, ES, CA, IT).
- Do not output anything outside the markdown profile (no preamble, no closing notes).
"""


def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def load_rows() -> list[dict]:
    with CSV_PATH.open() as f:
        return list(csv.DictReader(f))


def assert_no_em_dashes(text: str, label: str) -> None:
    if "—" in text or "–" in text:
        bad_lines = [ln for ln in text.split("\n") if "—" in ln or "–" in ln]
        print(f"[WARN] {label}: em-dash/en-dash detected; will retry once")
        print("       offending lines:", bad_lines[:3])
        raise ValueError("em-dash in output")


def generate_one(client: Anthropic, row: dict) -> tuple[str, str]:
    """Returns (slug, markdown_body)."""
    name = row["name"]
    slug = slugify(name)
    prompt = HAIKU_PROMPT_TEMPLATE.format(
        name=name,
        city=row["city"] or "Netherlands",
        website=row["website"] or "(not in dataset)",
        year_founded=row["year_founded"] or "(unknown)",
        team_size=row["team_size"] or "(unknown)",
        sector=row["sector"] or "(unknown)",
        scope=row["scope"] or "(no scope summary)",
        business_model=row["business_model"] or "(unknown)",
        eu_laws_related=row["eu_laws_related"] or "(no mapping)",
    )

    last_err = None
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=MODEL_ID,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            body = "".join(block.text for block in resp.content if hasattr(block, "text"))
            # Strip code fences if model wrapped its output
            body = body.strip()
            if body.startswith("```"):
                body = re.sub(r"^```[a-z]*\n?", "", body)
                body = re.sub(r"\n?```$", "", body)
            assert_no_em_dashes(body, f"{slug} (attempt {attempt+1})")
            return slug, body
        except ValueError as e:
            last_err = e
            time.sleep(0.5)
            continue
    # Second attempt failed: scrub em-dashes manually and accept
    if last_err:
        # Last fallback: re-run Haiku with explicit em-dash STOP instruction
        try:
            resp = client.messages.create(
                model=MODEL_ID,
                max_tokens=1500,
                messages=[
                    {"role": "user", "content": prompt + "\n\nIMPORTANT REPEAT: Do not use the em-dash character (—) or en-dash (–) anywhere. Use commas, full stops, or parentheses only."}
                ],
            )
            body = "".join(block.text for block in resp.content if hasattr(block, "text")).strip()
            if body.startswith("```"):
                body = re.sub(r"^```[a-z]*\n?", "", body)
                body = re.sub(r"\n?```$", "", body)
            # Manual scrub as last resort
            body = body.replace("—", ",").replace("–", ",")
            return slug, body
        except Exception as e2:
            raise RuntimeError(f"generate_one failed for {slug}: {e2}")
    raise RuntimeError(f"unreachable: {slug}")


def write_guide(slug: str, row: dict, body: str) -> None:
    out_dir = GUIDES_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "00_organisation.md"
    md_path.write_text(body + "\n")

    meta = {
        "slug": slug,
        "organisation": row["name"],
        "country": "NL",
        "type": "startup",
        "policy_areas": [t.strip() for t in (row["sector"] or "").split(",") if t.strip()],
        "linked_user_email": None,
        "linked_user_id": None,
        "status": "draft",
        "generated_at": str(date.today()),
        "owner_internal": "Victor Sole",
        "source_batch": "dutch_startups_2026_05_20",
        "outreach_email": row["email"] or None,
        "website": row["website"] or None,
        "notes": f"Concise variant. Generated by generate_dutch_startups_private_guides.py via Haiku 4.5 on {date.today()}. Single-file profile (not the full 5-file pattern). Link to a real user account + run sync_private_guides_to_db.py + set status=ready before going live."
    }
    (out_dir / "_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="generate only first N rows (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="print first 200 chars of each, do not write files")
    ap.add_argument("--only", default=None, help="comma-separated slug list to (re)generate")
    args = ap.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY missing in .env")
        sys.exit(1)
    client = Anthropic(api_key=api_key)

    rows = load_rows()
    if args.only:
        only_set = {s.strip() for s in args.only.split(",")}
        rows = [r for r in rows if slugify(r["name"]) in only_set]
    elif args.limit:
        rows = rows[:args.limit]

    print(f"[INFO] generating {len(rows)} private guides via {MODEL_ID}")
    written = 0
    failed = []
    for i, row in enumerate(rows, 1):
        name = row["name"]
        slug = slugify(name)
        t0 = time.time()
        try:
            _slug, body = generate_one(client, row)
        except Exception as e:
            print(f"  [{i:>2}/{len(rows)}] {slug:<24} FAILED: {e}")
            failed.append(slug)
            continue
        dt = time.time() - t0
        if args.dry_run:
            print(f"  [{i:>2}/{len(rows)}] {slug:<24} {dt:.1f}s {len(body):>4}ch | {body[:120].replace(chr(10), ' ')}")
        else:
            write_guide(slug, row, body)
            print(f"  [{i:>2}/{len(rows)}] {slug:<24} {dt:.1f}s {len(body):>4}ch -> {GUIDES_DIR}/{slug}/")
            written += 1

    print(f"\n[OK] generated {written}/{len(rows)} private guides")
    if failed:
        print(f"[WARN] {len(failed)} failed: {failed}")
    print(f"     output dir: {GUIDES_DIR}")
    print(f"     model: {MODEL_ID}")
    print(f"     status: all set to 'draft' in _meta.json (no DB sync, no user link yet)")


if __name__ == "__main__":
    main()
