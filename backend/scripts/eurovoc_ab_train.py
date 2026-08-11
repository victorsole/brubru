"""
Step 2 of the PyEuroVoc retrain: one arm of the length A/B.

Fine-tunes ONE encoder at a FIXED context length on the frozen corpus split, then
evaluates micro/macro-F1 at ID + MT + DO, STRATIFIED by document length bucket.
Run it twice with the same subset/seed and different --max-len (512 vs 8192) to get
the controlled A/B: same model, same data, only the truncation length changes.

This is a proof-of-concept scale on Mac MPS: small train/eval subset, a couple of
epochs, to prove the pipeline and get a directional, length-stratified signal
before deciding on a full cloud run.

Run:
  python3.12 scripts/eurovoc_ab_train.py --max-len 512  --train-n 2000 --eval-n 500 --epochs 2 --batch 8 --out runs/a_512.json
  python3.12 scripts/eurovoc_ab_train.py --max-len 8192 --train-n 2000 --eval-n 500 --epochs 2 --batch 1 --grad-accum 8 --out runs/b_8192.json
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

CDIR = Path(__file__).resolve().parent.parent / "data" / "eurovoc_corpus"
SPL = CDIR / "splits"
DESC = Path(__file__).resolve().parent.parent / "data" / "eu_vocabularies" / "eurovoc_descriptors.json"


def _bucket(t):
    return "le512" if t <= 512 else "512_4096" if t <= 4096 else "4096_8192" if t <= 8192 else "gt8192"


def load(split, text_by_celex, id_ix, n=None, seed=42):
    rows = [json.loads(l) for l in (SPL / f"{split}.jsonl").read_text(encoding="utf-8").splitlines()]
    if n:
        random.Random(seed).shuffle(rows)
        rows = rows[:n]
    out = []
    for r in rows:
        txt = text_by_celex.get(r["celex"], "")
        if not txt:
            continue
        y = np.zeros(len(id_ix), dtype=np.float32)
        for i in r["ids"]:
            j = id_ix.get(i)
            if j is not None:
                y[j] = 1.0
        out.append({"celex": r["celex"], "text": txt, "y": y,
                    "bucket": _bucket(r["est_tokens"]), "gold": set(r["ids"]) & set(id_ix)})
    return out


class Net(nn.Module):
    def __init__(self, model_name, n_labels):
        super().__init__()
        from transformers import AutoModel
        self.enc = AutoModel.from_pretrained(model_name)
        self.head = nn.Linear(self.enc.config.hidden_size, n_labels)

    def forward(self, ids, mask):
        h = self.enc(input_ids=ids, attention_mask=mask).last_hidden_state
        m = mask.unsqueeze(-1).float()
        pooled = (h * m).sum(1) / m.sum(1).clamp(min=1e-6)  # masked mean
        return self.head(pooled)


def f1(pred_sets, gold_sets):
    tp = sum(len(p & g) for p, g in zip(pred_sets, gold_sets))
    fp = sum(len(p - g) for p, g in zip(pred_sets, gold_sets))
    fn = sum(len(g - p) for p, g in zip(pred_sets, gold_sets))
    P = tp / (tp + fp) if tp + fp else 0.0
    R = tp / (tp + fn) if tp + fn else 0.0
    return round(200 * P * R / (P + R), 2) if P + R else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="answerdotai/ModernBERT-base")
    ap.add_argument("--max-len", type=int, default=512)
    ap.add_argument("--train-n", type=int, default=2000)
    ap.add_argument("--eval-n", type=int, default=500)
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--out", default="runs/arm.json")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    torch.manual_seed(a.seed); random.seed(a.seed); np.random.seed(a.seed)

    vocab = json.loads((SPL / "vocab.json").read_text())
    id_labels = vocab["id_labels"]; id_ix = {v: k for k, v in enumerate(id_labels)}
    id2mt = {d["id"]: d.get("mt") for d in json.loads(DESC.read_text())}
    text_by_celex = {r["celex"]: r["text"] for r in
                     (json.loads(l) for l in (CDIR / "corpus.jsonl").read_text(encoding="utf-8").splitlines())}

    tr = load("train", text_by_celex, id_ix, a.train_n, a.seed)
    ev = load("test", text_by_celex, id_ix, a.eval_n, a.seed)
    print(f"[{a.max_len}] train={len(tr)} eval={len(ev)} labels={len(id_labels)} device={a.device}", flush=True)

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(a.model)
    dev = a.device
    net = Net(a.model, len(id_labels)).to(dev)
    opt = torch.optim.AdamW(net.parameters(), lr=a.lr)
    lossf = nn.BCEWithLogitsLoss()

    def batches(data, bs, shuffle):
        idx = list(range(len(data)))
        if shuffle:
            random.Random(a.seed).shuffle(idx)
        for i in range(0, len(idx), bs):
            chunk = [data[j] for j in idx[i:i + bs]]
            enc = tok([c["text"] for c in chunk], truncation=True, max_length=a.max_len,
                      padding=True, return_tensors="pt")
            y = torch.tensor(np.stack([c["y"] for c in chunk]))
            yield enc["input_ids"].to(dev), enc["attention_mask"].to(dev), y.to(dev), chunk

    t0 = time.time()
    net.train()
    for ep in range(a.epochs):
        opt.zero_grad(); step = 0
        for ids, mask, y, _ in batches(tr, a.batch, True):
            loss = lossf(net(ids, mask), y) / a.grad_accum
            loss.backward(); step += 1
            if step % a.grad_accum == 0:
                opt.step(); opt.zero_grad()
        print(f"  epoch {ep+1}/{a.epochs} done | {time.time()-t0:.0f}s", flush=True)

    net.eval()
    pid, gid = [], []
    buckets = collections.defaultdict(lambda: ([], []))
    with torch.no_grad():
        for ids, mask, y, chunk in batches(ev, a.batch, False):
            prob = torch.sigmoid(net(ids, mask)).cpu().numpy()
            for row, c in zip(prob, chunk):
                pred = {id_labels[j] for j in np.where(row >= 0.5)[0]}
                pid.append(pred); gid.append(c["gold"])
                buckets[c["bucket"]][0].append(pred); buckets[c["bucket"]][1].append(c["gold"])

    def to_mt(s): return {id2mt[i] for i in s if id2mt.get(i)}
    def to_do(s): return {id2mt[i][:2] for i in s if id2mt.get(i)}
    res = {"max_len": a.max_len, "train_n": len(tr), "eval_n": len(ev), "epochs": a.epochs,
           "train_secs": round(time.time() - t0),
           "ID_microF1": f1(pid, gid),
           "MT_microF1": f1([to_mt(p) for p in pid], [to_mt(g) for g in gid]),
           "DO_microF1": f1([to_do(p) for p in pid], [to_do(g) for g in gid]),
           "by_bucket_ID_microF1": {b: {"n": len(v[0]), "f1": f1(v[0], v[1])} for b, v in sorted(buckets.items())}}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2), flush=True)


if __name__ == "__main__":
    main()
