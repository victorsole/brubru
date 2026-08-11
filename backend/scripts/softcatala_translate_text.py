#!/usr/bin/env python3.12
"""Resilient checkpointing Softcatala translator for plain text (blank-line paragraphs).

Translates a UTF-8 text file EN->CA or ES->CA using the Softcatala NMT models
(CTranslate2 + SentencePiece), with INCREMENTAL CHECKPOINTING so an interruption
never loses work. Re-running resumes from the last checkpoint.

Usage:
    python3.12 scripts/softcatala_translate_text.py <in.txt> <out.txt> --src en|es

Protected tokens (case numbers, CELEX, URLs, ECLI, Article refs, brand names) are
kept verbatim via PROTECT.split() (capturing group => odd indices are protected),
so no sentinel is ever injected into text that the model translates.
"""
import argparse, json, os, re, sys, glob, urllib.request, zipfile, shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalan_translate import _apply_glossary  # shared glossary

MODELS = {
    "en": ("eng-cat", "https://www.softcatala.org/pub/softcatala/opennmt/models/2022-11-22/eng-cat-2024-09-24.zip"),
    "es": ("spa-cat", "https://www.softcatala.org/pub/softcatala/opennmt/models/2022-11-22/spa-cat-2022-11-16.zip"),
}
CACHE = os.path.expanduser("~/.cache/brubru")
FLUSH_EVERY = 8

PROTECT = re.compile(r'(https?://\S+|\b\d{5}[A-Z]{1,2}\d{4}\b|C[-‑]\d+/\d+|ECLI:[A-Z:0-9]+|[A-Z]{2}:[A-Z]{1,3}:\d{4}:\d+|EU:C:\d{4}:\d+|\bLOA\b|Articles?\s\d+(?:\(\d+\))?|Brubru|Beresol|Softcatal[aà]|Pexels)')
SENT = re.compile(r'(?<=[\.\?\!;:])\s+')
_BULLETS = {ord('•'): '·', ord('●'): '·', ord('∙'): '·', ord('‧'): '·'}
# Softcatala NMT is sentence-level trained and truncates (early EOS) on very long
# inputs. Sub-split any sentence longer than this at comma/clause boundaries.
_MAXLEN = 200
# NMT quirk fixes applied post-translation (order matters).
_POSTFIX = [
    ("sentit que s'ha d'interpretar en el sentit que", "s'ha d'interpretar en el sentit que"),
    ("s'han d'interpretar en el sentit que s'ha", "s'han d'interpretar en el sentit que"),
]


def ensure_model(src):
    pair, url = MODELS[src]
    mdir = os.path.join(CACHE, f"softcatala-{pair}")
    if src == "en":
        alt = os.path.join(CACHE, "softcatala-en-ca")
        if os.path.exists(os.path.join(alt, "eng-cat", "ctranslate2", "model.bin")):
            return alt, "eng-cat"
    if os.path.exists(os.path.join(mdir, pair, "ctranslate2", "model.bin")):
        return mdir, pair
    os.makedirs(mdir, exist_ok=True)
    zp = os.path.join(mdir, f"{pair}.zip")
    print(f"[dl] {url}")
    urllib.request.urlretrieve(url, zp)
    with zipfile.ZipFile(zp) as z:
        z.extractall(mdir)
    inner = os.path.join(mdir, pair, pair)
    if os.path.isdir(inner):
        for it in os.listdir(inner):
            shutil.move(os.path.join(inner, it), os.path.join(mdir, pair, it))
    os.remove(zp)
    return mdir, pair


def load_translator(mdir, pair):
    import ctranslate2, sentencepiece as spm
    ct2 = os.path.join(mdir, pair, "ctranslate2")
    sp_files = glob.glob(os.path.join(mdir, "**", "*.model"), recursive=True)
    sp = spm.SentencePieceProcessor(); sp.load(sp_files[0])
    return ctranslate2.Translator(ct2), sp


def _chunk_long(sent):
    """Split a very long sentence at comma/clause boundaries so the NMT does not
    early-EOS-truncate it. Returns a list of pieces that rejoin to the original."""
    if len(sent) <= _MAXLEN:
        return [sent]
    # split on commas + common Catalan/Spanish clause markers, keeping delimiters
    parts = re.split(r'(,\s+)', sent)
    chunks, cur = [], ""
    for p in parts:
        if len(cur) + len(p) > _MAXLEN and cur:
            chunks.append(cur); cur = p
        else:
            cur += p
    if cur:
        chunks.append(cur)
    return chunks or [sent]


def _tr_span(span, tr, sp):
    if not span.strip():
        return span
    lead = span[: len(span) - len(span.lstrip())]
    trail = span[len(span.rstrip()):]
    sents = [s for s in SENT.split(span.strip()) if s.strip()]
    # map each sentence to its (possibly multiple) chunks
    chunks, spans = [], []
    for s in sents:
        cs = _chunk_long(s)
        spans.append(len(cs)); chunks.extend(cs)
    toks = [sp.encode(c, out_type=str) for c in chunks]
    try:
        res = tr.translate_batch(toks, max_batch_size=16, beam_size=2, max_decoding_length=512)
        tchunks = [sp.decode(r.hypotheses[0]) for r in res]
    except Exception:
        tchunks = chunks
    # rejoin chunks back into sentences
    tsents, k = [], 0
    for n in spans:
        tsents.append(" ".join(tchunks[k:k + n]).strip()); k += n
    return lead + " ".join(tsents) + trail


def translate_blocks(blocks, tr, sp, done):
    out = list(done)
    for i in range(len(done), len(blocks)):
        b = blocks[i].translate(_BULLETS)
        if not b.strip():
            out.append(""); yield i + 1, out; continue
        parts = PROTECT.split(b)
        rebuilt = [p if (j % 2 == 1) else _tr_span(p, tr, sp) for j, p in enumerate(parts)]
        joined = _apply_glossary("".join(rebuilt))
        joined = joined.replace('⁇', '·').replace(' — ', ', ').replace('—', ', ')
        for a, b in _POSTFIX:
            joined = joined.replace(a, b)
        out.append(joined)
        yield i + 1, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("infile"); ap.add_argument("outfile")
    ap.add_argument("--src", choices=["en", "es"], required=True)
    a = ap.parse_args()
    blocks = re.split(r'\n\s*\n', Path(a.infile).read_text(encoding="utf-8"))
    prog_file = a.outfile + ".progress.json"
    done = []
    if os.path.exists(prog_file):
        done = json.load(open(prog_file)).get("done", [])
        print(f"[resume] {len(done)}/{len(blocks)}")
    mdir, pair = ensure_model(a.src)
    tr, sp = load_translator(mdir, pair)
    print(f"[model] {pair} | blocks: {len(blocks)}")
    last = done
    for n, cur in translate_blocks(blocks, tr, sp, done):
        last = cur
        if n % FLUSH_EVERY == 0 or n == len(blocks):
            json.dump({"done": cur}, open(prog_file, "w"), ensure_ascii=False)
            print(f"[ckpt] {n}/{len(blocks)}")
    Path(a.outfile).write_text("\n\n".join(last), encoding="utf-8")
    print(f"[done] {a.outfile} ({len(last)} blocks)")


if __name__ == "__main__":
    main()
