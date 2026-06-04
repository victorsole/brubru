"""
Ingest senior EU Commission officials from the static Who-is-Who directory PDF.

The live Who-is-Who org tree is JS-rendered and not scrapable, but the Publications
Office publishes the same directory as a static PDF (api_op.md: EUWhoiswho_COM_EN.pdf).
This parses it into per-DG senior officials (Director-General, Deputy DG, Directors,
Heads of Unit) and writes knowledge_base/whoiswho_officials.json, which MEUB
Stakeholder Mapping reads to put named people behind each Commission DG node.

Run:  python3.12 -m scripts.ingest_whoiswho_officials   (downloads the current PDF)
      python3.12 -m scripts.ingest_whoiswho_officials --pdf /tmp/wiw_com.pdf
No Anthropic. One-off / refresh job; safe to re-run.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

PDF_URL = "https://op.europa.eu/webpub/wiw/pdf/EUWhoiswho_COM_EN.pdf"
OUT = Path(__file__).resolve().parents[1] / "knowledge_base" / "whoiswho_officials.json"
_UA = {"User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"}

# Senior-role vocabulary -> rank (lower = more senior). Only these are kept.
_ROLES = [
    (re.compile(r"^Secretary-General$", re.I), 0),
    (re.compile(r"^Director-General$", re.I), 0),
    (re.compile(r"^Deputy Secretary-General", re.I), 1),
    (re.compile(r"^Deputy Director-General", re.I), 1),
    (re.compile(r"^(Principal Adviser|Chair\b|Hors Classe Adviser)", re.I), 2),
    (re.compile(r"^Director\b", re.I), 3),
    (re.compile(r"^Head of (Unit|the )", re.I), 4),
]
_NAME = re.compile(r"^(?:Mr|Ms|Mme|M)\.?\s+([A-Z][\w'’.\- ]+?)\s*$")
_KEEP_PER_DG = 5


def _role_rank(line: str):
    for rx, rank in _ROLES:
        if rx.match(line.strip()):
            return rank
    return None


def _titlecase_caps(raw: str) -> str:
    # Title-case all-caps tokens (surnames, shouty functions); keep mixed-case as-is.
    return " ".join(w.title() if w.isupper() else w for w in raw.split()).strip()


def _clean_name(raw: str) -> str:
    return _titlecase_caps(raw)


def _clean_func(raw: str) -> str:
    return _titlecase_caps(raw.rstrip(" —-:").strip())


def parse_pdf(data: bytes) -> dict:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    lines = [l.rstrip() for l in text.splitlines()]

    # Section boundaries: "DG <CODE> — <name>" (code = the graph's DG code).
    hdr = re.compile(r"^DG ([A-Z]{2,8})\b\s*[—-]")
    sections = []  # (code, start_line)
    for i, ln in enumerate(lines):
        m = hdr.match(ln.strip())
        if m:
            sections.append((m.group(1), i))
    sections.append((None, len(lines)))

    officials: dict[str, list] = {}
    for s in range(len(sections) - 1):
        code, start = sections[s]
        end = sections[s + 1][1]
        block = lines[start:end]
        people = []
        for i, ln in enumerate(block):
            nm = _NAME.match(ln.strip())
            if not nm or "@" in ln:
                continue
            name = nm.group(1).strip()
            if len(name) < 4 or name.upper() == name and " " not in name:
                continue
            func, rank = None, None
            for j in range(i + 1, min(i + 4, len(block))):
                cand = block[j].strip()
                if not cand or "@" in cand or cand.startswith("Tel"):
                    continue
                rr = _role_rank(cand)
                if rr is not None:
                    func, rank = cand, rr
                    break
            if func is not None:
                people.append((rank, len(people), _clean_name(name), func))
        if people:
            people.sort(key=lambda p: (p[0], p[1]))
            seen, top, c0, c1 = set(), [], 0, 0
            for rank, _, name, func in people:
                if name in seen:
                    continue
                if rank == 0 and c0 >= 1:   # at most one Director-General / Secretary-General
                    continue
                if rank == 1 and c1 >= 2:   # at most two deputies
                    continue
                seen.add(name)
                if rank == 0:
                    c0 += 1
                elif rank == 1:
                    c1 += 1
                top.append({"name": name, "function": _clean_func(func)})
                if len(top) >= _KEEP_PER_DG:
                    break
            officials[code] = top
    return officials


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", help="local PDF path (skip download)")
    args = ap.parse_args()

    if args.pdf:
        data = Path(args.pdf).read_bytes()
        print(f"[whoiswho] read {len(data)} bytes from {args.pdf}")
    else:
        print(f"[whoiswho] downloading {PDF_URL}")
        data = urllib.request.urlopen(urllib.request.Request(PDF_URL, headers=_UA), timeout=60).read()
        print(f"[whoiswho] downloaded {len(data)} bytes")

    officials = parse_pdf(data)
    payload = {"source": "EUWhoiswho_COM_EN.pdf", "dg_count": len(officials),
               "official_count": sum(len(v) for v in officials.values()), "officials": officials}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[whoiswho] wrote {OUT} -> {payload['dg_count']} DGs, {payload['official_count']} officials")
    for code in list(officials)[:5]:
        print(f"  {code}: " + "; ".join(f"{o['name']} ({o['function']})" for o in officials[code]))


if __name__ == "__main__":
    sys.exit(main())
