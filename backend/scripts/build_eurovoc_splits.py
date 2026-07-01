"""
Step 1c of the PyEuroVoc retraining corpus: freeze a leakage-free, multi-label
stratified train/val/test split, ready for the length-stratified A/B.

Inputs : data/eurovoc_corpus/corpus.jsonl  (usable acts: text + gold ids/mts/domains)
Outputs: data/eurovoc_corpus/splits/{train,val,test}.jsonl  (index + labels; NO text)
         data/eurovoc_corpus/splits/vocab.json      (ID>=10, MT, DO label lists)
         data/eurovoc_corpus/splits/manifest.json    (sizes, seed, coverage audit)

Design (from the corpus audit):
  - Label vocab = ID descriptors with >=10 examples (1,525), plus the full MT (127)
    and DO (21) rollups. The paper evaluated ID/MT/DO; we keep all three.
  - One CELEX = one act, so a by-CELEX split is automatically leakage-free.
  - Multi-label iterative stratification (Sechidis 2011, the paper's method) on the
    ID target matrix, so every label's frequency is preserved across splits.
  - Each act carries its length bucket (<=512 / 512-4096 / 4096-8192 / >8192) so the
    A/B can be reported per bucket (the long-context signal lives in 512-4096).
  - The split files hold celex + labels only; text is loaded from corpus.jsonl at
    train time (single source of the 33M words, no duplication).

Deterministic (seed 42). No GPU, no network.

Run:  python3.12 scripts/build_eurovoc_splits.py
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import numpy as np
from iterstrat.ml_stratifiers import MultilabelStratifiedShuffleSplit

CORPUS_DIR = Path(__file__).resolve().parent.parent / "data" / "eurovoc_corpus"
CORPUS = CORPUS_DIR / "corpus.jsonl"
OUT = CORPUS_DIR / "splits"
SEED = 42
ID_MIN = 10  # a descriptor needs >=10 examples to enter the ID vocabulary


def _bucket(t: int) -> str:
    if t <= 512:
        return "le512"
    if t <= 4096:
        return "512_4096"
    if t <= 8192:
        return "4096_8192"
    return "gt8192"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    recs = [json.loads(l) for l in CORPUS.read_text(encoding="utf-8").splitlines()
            if not json.loads(l)["fragment_suspect"]]

    idf = collections.Counter(i for r in recs for i in r["ids"])
    id_vocab = sorted([i for i, v in idf.items() if v >= ID_MIN])
    mt_vocab = sorted({m for r in recs for m in r["mts"]})
    do_vocab = sorted({d for r in recs for d in r["domains"]})
    id_ix = {v: k for k, v in enumerate(id_vocab)}

    # keep acts that still have >=1 in-vocab ID label (else no training signal)
    recs = [r for r in recs if any(i in id_ix for i in r["ids"])]
    print(f"[splits] {len(recs)} acts | ID vocab={len(id_vocab)} (>= {ID_MIN}) MT={len(mt_vocab)} DO={len(do_vocab)}")

    # ID target matrix for stratification
    Y = np.zeros((len(recs), len(id_vocab)), dtype=np.int8)
    for r_i, r in enumerate(recs):
        for i in r["ids"]:
            j = id_ix.get(i)
            if j is not None:
                Y[r_i, j] = 1
    X = np.arange(len(recs)).reshape(-1, 1)

    # 90/10 -> trainval/test, then 8/9 : 1/9 -> train/val  (=> 80/10/10)
    s1 = MultilabelStratifiedShuffleSplit(n_splits=1, test_size=0.10, random_state=SEED)
    trv, te = next(s1.split(X, Y))
    s2 = MultilabelStratifiedShuffleSplit(n_splits=1, test_size=1.0 / 9.0, random_state=SEED)
    tr_rel, va_rel = next(s2.split(X[trv], Y[trv]))
    tr, va = trv[tr_rel], trv[va_rel]
    assert len(set(tr) & set(va)) == 0 and len(set(tr) & set(te)) == 0 and len(set(va) & set(te)) == 0

    def write(name, idx):
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for k in idx:
                r = recs[int(k)]
                ids = [i for i in r["ids"] if i in id_ix]
                f.write(json.dumps({"celex": r["celex"], "ids": ids, "mts": r["mts"],
                                    "domains": r["domains"], "est_tokens": r["est_tokens"],
                                    "len_bucket": _bucket(r["est_tokens"]), "n_labels": len(ids)},
                                   ensure_ascii=False) + "\n")
        return len(idx)

    sizes = {"train": write("train", tr), "val": write("val", va), "test": write("test", te)}
    (OUT / "vocab.json").write_text(json.dumps(
        {"id_min_examples": ID_MIN, "id_labels": id_vocab, "mt_labels": mt_vocab,
         "do_labels": do_vocab}, ensure_ascii=False), encoding="utf-8")

    # audit: label coverage + length-bucket balance across splits
    def buckets(idx):
        c = collections.Counter(_bucket(recs[int(k)]["est_tokens"]) for k in idx)
        n = sum(c.values())
        return {b: f"{100*c[b]//n}%" for b in ("le512", "512_4096", "4096_8192", "gt8192")}
    tr_ids = {i for k in tr for i in recs[int(k)]["ids"] if i in id_ix}
    te_ids = {i for k in te for i in recs[int(k)]["ids"] if i in id_ix}
    manifest = {"seed": SEED, "id_min": ID_MIN, "sizes": sizes,
                "id_vocab": len(id_vocab), "mt_vocab": len(mt_vocab), "do_vocab": len(do_vocab),
                "id_labels_in_train": len(tr_ids), "id_labels_in_test": len(te_ids),
                "buckets": {k: buckets(v) for k, v in (("train", tr), ("val", va), ("test", te))}}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  sizes: {sizes}")
    print(f"  ID labels covered in train: {len(tr_ids)}/{len(id_vocab)} | in test: {len(te_ids)}/{len(id_vocab)}")
    print(f"  length-bucket balance: {manifest['buckets']}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
