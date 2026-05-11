#!/usr/bin/env python3.12
"""
Linguistic audit of Brubru's Catalan EU-legislation translations.

Tier A — static rule sweep (CPU-only, fast, no network):
    - Brubru-glossary violations (CLAUDE.md standard)
    - Untranslated English fragments
    - UTF-8-as-Latin1 mojibake
    - Missing diacritics on common Catalan words
    - AI-leak phrases

Tier B — Softcatala corrector sweep (network, rate-limited):
    https://api.softcatala.org/corrector/v2/check  (LanguageTool 6.8 backend)
    Run on a sample of N acts (random by default, or filtered to Tier-A
    offenders via --only-flagged).

Outputs:
    audit/catalan/static_audit_<TS>.jsonl  (Tier A)
    audit/catalan/lt_audit_<TS>.jsonl      (Tier B, if --softcatala)
    audit/catalan/summary_<TS>.md          (aggregate report, both tiers)

Usage:
    # Tier A only — full sweep over all translations
    python3.12 backend/scripts/audit_catalan_translations.py

    # Tier A + Tier B sample (100 random acts via Softcatala API)
    python3.12 backend/scripts/audit_catalan_translations.py --softcatala --sample 100

    # Tier A on a single CELEX (debug)
    python3.12 backend/scripts/audit_catalan_translations.py --celex 32016R0679

    # Tier B targeted at acts that failed Tier A
    python3.12 backend/scripts/audit_catalan_translations.py --softcatala --only-flagged --sample 50

The Tier-B Softcatala sweep extracts visible text from each act's index.html
(stripping tags), splits into ≤1500-char chunks (LanguageTool free-tier limit
is ~20k chars but we stay polite), and posts each chunk with a 0.6s delay.
Rate ≈ 1.5 req/s; ~2 min per typical act.

Created 7 May 2026.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
TRANSLATIONS_DIR = ROOT / "data" / "legislacio-ue-catala"
AUDIT_DIR = ROOT / "audit" / "catalan"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

SOFTCATALA_API = "https://api.softcatala.org/corrector/v2/check"
USER_AGENT = "Mozilla/5.0 brubru-catalan-audit"


# --------------------------------------------------------------------------- #
# Tier A — static rule sweep                                                  #
# --------------------------------------------------------------------------- #

# (rule_id, severity, regex, why, suggestion-or-None)
# severity: 'high' = breaks reader trust; 'mid' = stylistic deviation; 'low' = stylistic preference
STATIC_RULES = [
    # --- Untranslated English fragments (high severity) ----------------------
    ("untranslated_having_regard", "high", re.compile(r"\bHaving regard\b", re.I),
     "English preamble fragment 'Having regard' present", "Vist / Vista"),
    ("untranslated_whereas", "high", re.compile(r"\bWhereas\s*[:,]"),
     "English 'Whereas:' present", "Atenent que"),
    ("untranslated_member_state", "high",
     re.compile(r"\bMember States?\b"),
     "Untranslated 'Member State(s)'", "Estat membre / Estats membres"),
    ("untranslated_this_regulation", "high",
     re.compile(r"\bthis Regulation\b"),
     "Untranslated 'this Regulation'", "aquest Reglament"),
    ("untranslated_this_directive", "high",
     re.compile(r"\bthis Directive\b"),
     "Untranslated 'this Directive'", "aquesta Directiva"),
    ("untranslated_european_parliament", "high",
     re.compile(r"\bthe European Parliament\b"),
     "Untranslated 'the European Parliament'", "el Parlament Europeu"),
    ("untranslated_shall", "high",
     re.compile(r"\b(shall|should|must)\b"),
     "English modal verb (shall/should/must) present", None),
    ("untranslated_have_adopted", "high",
     re.compile(r"\b(have|has)\s+adopted\s+this\b", re.I),
     "Untranslated 'have/has adopted this …'", "ha adoptat"),
    ("untranslated_in_accordance", "high",
     re.compile(r"\bin accordance with\b", re.I),
     "Untranslated 'in accordance with'", "d'acord amb"),
    ("untranslated_acting", "high",
     re.compile(r"\bActing in accordance\b"),
     "Untranslated 'Acting in accordance'", "Actuant d'acord"),

    # --- Brubru glossary (CLAUDE.md) ---------------------------------------- #
    ("glossary_implementacio", "mid",
     re.compile(r"d['’']?\s*implementaci[oó]", re.I),
     "Brubru glossary: use 'd'execució' instead of 'd'implementació'", "d'execució"),
    ("glossary_ha_aconseguit", "mid",
     re.compile(r"\bha\s+aconseguit\b", re.I),
     "Brubru glossary: 'ha adoptat' is preferred over 'ha aconseguit' for 'has adopted'", "ha adoptat"),
    ("glossary_implementing", "mid",
     re.compile(r"\bimplementing\b", re.I),
     "English 'implementing' leftover (translate to 'd'execució')", "d'execució"),
    ("glossary_brussel_les", "low",
     re.compile(r"\bBrussel(?:[\.’' ]les|s)\b"),
     "Catalan should use 'Brussel·les' with a punt volat (·)", "Brussel·les"),

    # --- Mojibake / encoding ------------------------------------------------ #
    ("mojibake_apostrophe", "high", re.compile(r"â€™"),
     "UTF-8 apostrophe rendered as Latin-1 (â€™)", "'"),
    ("mojibake_e_acute", "high", re.compile(r"Ã©"),
     "UTF-8 é rendered as Latin-1 (Ã©)", "é"),
    ("mojibake_e_grave", "high", re.compile(r"Ã¨"),
     "UTF-8 è rendered as Latin-1 (Ã¨)", "è"),
    ("mojibake_a_grave", "high", re.compile(r"Ã "),
     "UTF-8 à rendered as Latin-1 (Ã )", "à"),
    ("mojibake_o_acute", "high", re.compile(r"Ã³"),
     "UTF-8 ó rendered as Latin-1 (Ã³)", "ó"),
    ("mojibake_i_acute", "high", re.compile(r"Ã­"),
     "UTF-8 í rendered as Latin-1 (Ã­)", "í"),
    ("mojibake_c_cedilla", "high", re.compile(r"Ã§"),
     "UTF-8 ç rendered as Latin-1 (Ã§)", "ç"),
    ("mojibake_dash", "mid", re.compile(r"â€"),
     "Stray UTF-8 punctuation rendered as Latin-1 (â€…)", None),

    # --- AI leak phrases ---------------------------------------------------- #
    ("ai_leak_please_provide", "high",
     re.compile(r"Please provide|I need the complete text|As an AI|I cannot translate|I'm sorry", re.I),
     "Looks like an AI-leak phrase — translation aborted mid-prompt", None),
    # NB: '[...]' alone is a Publications-Office redaction marker in source EUR-Lex text
    # and is NOT an AI leak. Only flag when paired with English commentary.
    ("ai_leak_translation_note", "mid",
     re.compile(r"\b(Translator['’]s note|Nota del traductor)\b", re.I),
     "Translator's-note marker present — likely AI commentary leak", None),

    # --- Catalan diacritics commonly stripped by NMT ------------------------ #
    # Word-boundary regexes; case-insensitive with negative-lookbehind for legit lowercase variants.
    ("missing_accent_perque", "low",
     re.compile(r"(?<![A-Za-zÀ-ÿ])Perque(?![A-Za-zÀ-ÿ])"),
     "Missing accent: 'Perque' should be 'Perquè'", "Perquè"),
    ("missing_accent_politica", "low",
     re.compile(r"(?<![A-Za-zÀ-ÿ])politica(?![A-Za-zÀ-ÿ])"),
     "Missing accent: 'politica' should be 'política'", "política"),
    ("missing_accent_regulacio", "low",
     re.compile(r"(?<![A-Za-zÀ-ÿ])regulacio(?![A-Za-zÀ-ÿ])"),
     "Missing accent: 'regulacio' should be 'regulació'", "regulació"),
    ("missing_accent_decisio", "low",
     re.compile(r"(?<![A-Za-zÀ-ÿ])decisio(?![A-Za-zÀ-ÿ])"),
     "Missing accent: 'decisio' should be 'decisió'", "decisió"),
    ("missing_accent_directiva", "low",
     re.compile(r"(?<![A-Za-zÀ-ÿ])directiva\s+\(UE\)\s+\d+/\d+(?![A-Za-zÀ-ÿ])"),
     "'directiva' should be capitalised when naming a specific Directive (Directiva (UE) ...)", None),
    ("missing_accent_aixo", "low",
     re.compile(r"(?<![A-Za-zÀ-ÿ])Aixo(?![A-Za-zÀ-ÿ])"),
     "Missing accent: 'Aixo' should be 'Això'", "Això"),
    # --- Body content emptiness --------------------------------------------- #
    ("empty_body", "high", re.compile(r"<body[^>]*>\s*</body>"),
     "<body> appears to be empty", None),
    ("title_placeholder", "high",
     re.compile(r"<h1[^>]*>\s*(?:--|TITLE|TBD|XXX)\s*</h1>", re.I),
     "Title is a placeholder", None),
]


def visible_text(html: str) -> str:
    """Crude tag-stripper for static rule scanning. Keeps only body text and
    drops <script>/<style>/<head>. Good enough for substring detection; not
    intended for sentence-level analysis."""
    html = re.sub(r"<head\b[^>]*>.*?</head>", "", html, flags=re.S | re.I)
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S | re.I)
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.S | re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"&nbsp;", " ", html)
    html = re.sub(r"&amp;", "&", html)
    html = re.sub(r"&quot;", '"', html)
    html = re.sub(r"&#39;|&apos;", "'", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def audit_one_static(celex: str, html: str) -> list[dict]:
    """Run all static rules over a single act's HTML. Returns issue dicts."""
    text = visible_text(html)
    issues = []
    for rule_id, severity, regex, why, suggestion in STATIC_RULES:
        # Targeted rules (e.g. mojibake) scan raw HTML, not stripped text
        target = html if rule_id.startswith("mojibake_") or rule_id == "empty_body" or rule_id == "title_placeholder" else text
        matches = regex.findall(target)
        if matches:
            issues.append({
                "celex": celex,
                "rule_id": rule_id,
                "severity": severity,
                "count": len(matches),
                "why": why,
                "suggestion": suggestion,
                "samples": [m if isinstance(m, str) else " ".join(m) for m in matches[:3]],
            })
    return issues


def iter_translation_files(only: list[str] | None = None) -> Iterator[tuple[str, Path]]:
    """Yield (celex, index.html path) for every translation directory."""
    dirs = []
    if only:
        dirs = [TRANSLATIONS_DIR / c for c in only]
    else:
        dirs = sorted(
            d for d in TRANSLATIONS_DIR.iterdir()
            if d.is_dir() and not d.name.endswith("-softcatala")
        )
    for d in dirs:
        idx = d / "index.html"
        if idx.is_file():
            yield d.name, idx


# --------------------------------------------------------------------------- #
# Tier B — Softcatala corrector API                                           #
# --------------------------------------------------------------------------- #

def chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """Split text into ≤max_chars chunks on sentence boundaries where possible."""
    chunks: list[str] = []
    sentences = re.split(r"(?<=[\.!?])\s+", text)
    cur = ""
    for s in sentences:
        if len(cur) + len(s) + 1 > max_chars:
            if cur:
                chunks.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        chunks.append(cur)
    return chunks


def softcatala_check(text: str, retries: int = 2) -> dict:
    """POST one chunk to Softcatala / LanguageTool. Returns parsed JSON."""
    body = urlencode({"text": text, "language": "ca"}).encode("utf-8")
    req = Request(
        SOFTCATALA_API,
        data=body,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"Softcatala API failed after {retries + 1} attempts: {last_err}")


# --------------------------------------------------------------------------- #
# Driver                                                                      #
# --------------------------------------------------------------------------- #

def run_static_sweep(targets: list[tuple[str, Path]],
                     out_path: Path,
                     verbose: bool = False) -> tuple[int, int, dict[str, int]]:
    """Run Tier A across all targets. Stream per-act JSON lines. Returns
    (acts_total, acts_with_issues, rule_counter)."""
    rule_counts: Counter[str] = Counter()
    acts_with_issues = 0
    total = len(targets)
    t0 = time.time()
    with out_path.open("w", encoding="utf-8") as out:
        for i, (celex, path) in enumerate(targets, 1):
            try:
                html = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001
                out.write(json.dumps({"celex": celex, "error": str(e)}) + "\n")
                continue
            issues = audit_one_static(celex, html)
            for iss in issues:
                rule_counts[iss["rule_id"]] += 1
            if issues:
                acts_with_issues += 1
                out.write(json.dumps({"celex": celex, "issues": issues}) + "\n")
            if verbose and i % 500 == 0:
                rate = i / max(time.time() - t0, 1e-6)
                print(f"  [{i}/{total}] {rate:.0f} acts/s, {acts_with_issues} flagged so far")
    return total, acts_with_issues, dict(rule_counts)


def run_softcatala_sweep(targets: list[tuple[str, Path]],
                         out_path: Path,
                         delay: float = 0.6,
                         max_chunks_per_act: int = 30) -> tuple[int, int]:
    """Run Tier B over a sample. Streams per-act results as JSON lines."""
    acts_done = 0
    acts_with_findings = 0
    t0 = time.time()
    with out_path.open("w", encoding="utf-8") as out:
        for i, (celex, path) in enumerate(targets, 1):
            try:
                html = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:  # noqa: BLE001
                out.write(json.dumps({"celex": celex, "error": str(e)}) + "\n")
                continue
            text = visible_text(html)
            chunks = chunk_text(text)[:max_chunks_per_act]
            findings: list[dict] = []
            for ch in chunks:
                if not ch.strip():
                    continue
                try:
                    resp = softcatala_check(ch)
                except Exception as e:  # noqa: BLE001
                    findings.append({"chunk_error": str(e), "chunk_head": ch[:80]})
                    time.sleep(delay)
                    continue
                for m in resp.get("matches", []):
                    findings.append({
                        "rule_id": m["rule"]["id"],
                        "category": m["rule"]["category"]["id"],
                        "issue_type": m.get("rule", {}).get("issueType"),
                        "message": m["message"],
                        "context": m["context"]["text"][m["context"]["offset"]:m["context"]["offset"] + m["context"]["length"]],
                        "context_full": m["context"]["text"],
                        "replacements": [r.get("value", "") for r in m.get("replacements", [])[:3]],
                    })
                time.sleep(delay)
            acts_done += 1
            if findings:
                acts_with_findings += 1
                out.write(json.dumps({"celex": celex, "findings": findings}) + "\n")
            elapsed = time.time() - t0
            rate = acts_done / max(elapsed, 1e-6)
            print(f"  [{i}/{len(targets)}] {celex}: {len(findings)} findings  ({rate:.2f} acts/s)")
    return acts_done, acts_with_findings


def write_summary(summary_path: Path,
                  static_total: int,
                  static_flagged: int,
                  rule_counts: dict[str, int],
                  lt_done: int,
                  lt_flagged: int,
                  static_path: Path,
                  lt_path: Path | None) -> None:
    lines = []
    lines.append(f"# Catalan Translations Linguistic Audit — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n")
    lines.append(f"**Tier A — Static Rules**  ")
    lines.append(f"- Acts scanned: **{static_total}**  ")
    lines.append(f"- Acts with at least one issue: **{static_flagged}** ({100 * static_flagged / max(static_total,1):.1f}%)  ")
    lines.append(f"- Rule hit counts (per act, deduped):  \n")
    rules_sorted = sorted(rule_counts.items(), key=lambda kv: -kv[1])
    if rules_sorted:
        lines.append("| Rule | Hits |")
        lines.append("|---|---:|")
        for rid, n in rules_sorted:
            lines.append(f"| `{rid}` | {n} |")
    else:
        lines.append("_(no static rule hits — clean sweep)_")
    lines.append("")
    lines.append(f"Per-act detail: `{static_path.relative_to(ROOT)}`\n")

    if lt_path is not None:
        lines.append(f"**Tier B — Softcatala / LanguageTool**  ")
        lines.append(f"- Acts sampled: **{lt_done}**  ")
        lines.append(f"- Acts with at least one finding: **{lt_flagged}** ({100 * lt_flagged / max(lt_done,1):.1f}%)  ")
        lines.append(f"- Per-act detail: `{lt_path.relative_to(ROOT)}`\n")

    summary_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Linguistic audit of Catalan translations")
    ap.add_argument("--celex", action="append", help="Limit to specific CELEX (repeatable)")
    ap.add_argument("--softcatala", action="store_true", help="Also run Tier B Softcatala API sweep")
    ap.add_argument("--sample", type=int, default=100, help="Tier B sample size")
    ap.add_argument("--only-flagged", action="store_true",
                    help="Tier B: pick sample from acts that failed Tier A (instead of random)")
    ap.add_argument("--delay", type=float, default=0.6, help="Seconds between Softcatala requests")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    static_path = AUDIT_DIR / f"static_audit_{ts}.jsonl"
    lt_path = AUDIT_DIR / f"lt_audit_{ts}.jsonl"
    summary_path = AUDIT_DIR / f"summary_{ts}.md"

    targets = list(iter_translation_files(args.celex))
    print(f"[INFO] Tier A: scanning {len(targets)} translations...")
    total, flagged, rule_counts = run_static_sweep(targets, static_path, verbose=not args.quiet)
    print(f"[INFO] Tier A done — {flagged}/{total} acts flagged. Top rules:")
    for rid, n in sorted(rule_counts.items(), key=lambda kv: -kv[1])[:8]:
        print(f"        {n:>6}  {rid}")

    lt_done = lt_flagged = 0
    actual_lt_path: Path | None = None
    if args.softcatala:
        # Build sample
        if args.only_flagged:
            flagged_celex = []
            with static_path.open() as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if "issues" in rec:
                        flagged_celex.append(rec["celex"])
            sample_pool = [t for t in targets if t[0] in set(flagged_celex)]
            print(f"[INFO] Tier B: {len(sample_pool)} flagged candidates, sampling {min(args.sample, len(sample_pool))}")
        else:
            sample_pool = list(targets)
            print(f"[INFO] Tier B: random sample of {min(args.sample, len(sample_pool))}/{len(sample_pool)}")
        random.seed(42)
        sample = random.sample(sample_pool, min(args.sample, len(sample_pool)))
        lt_done, lt_flagged = run_softcatala_sweep(sample, lt_path, delay=args.delay)
        actual_lt_path = lt_path

    write_summary(summary_path, total, flagged, rule_counts, lt_done, lt_flagged, static_path, actual_lt_path)
    print(f"\n[OK] Summary: {summary_path}")
    print(f"[OK] Static detail: {static_path}")
    if actual_lt_path is not None:
        print(f"[OK] LT detail: {actual_lt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
