#!/usr/bin/env python3.12
"""
Semantic-ish memory retrieval for Brubru.

Given a query, ranks memory/*.md files by relevance using TF-IDF cosine similarity
over YAML-frontmatter description + body. Prints a compact table: file, score,
token estimate, one-line snippet. Cache rebuilt when any source file is newer
than the pickle.

Use cases:
  - At start of a complex task, surface the 3 most relevant memories instead of
    the full MEMORY.md index.
  - Before writing code, check what past feedback applies.
  - Let an agent query memory without reading 73 files.

Honours <private>...</private> tags: content inside is excluded from both the
index and the printed snippet.

Defaults to ~/.claude/projects/-Users-victorsole-Documents-GitHub-brubru/memory/.
Override with --dir.
"""

from __future__ import annotations

import argparse
import os
import pickle
import re
import sys
from pathlib import Path
from typing import List, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DEFAULT_DIR = Path.home() / ".claude" / "projects" / "-Users-victorsole-Documents-GitHub-brubru" / "memory"
PRIVATE_RE = re.compile(r"<private>.*?</private>", re.DOTALL | re.IGNORECASE)
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def strip_private(text: str) -> str:
    return PRIVATE_RE.sub("", text)


def extract_description(text: str) -> str:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    return ""


def first_body_line(text: str) -> str:
    body = FRONTMATTER_RE.sub("", text).strip()
    for line in body.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:120]
    return ""


def load_files(mem_dir: Path) -> List[Tuple[str, str, str, str]]:
    """Return list of (name, description, snippet, full_text_for_index)."""
    out = []
    for p in sorted(mem_dir.glob("*.md")):
        if p.name == "MEMORY.md":
            continue  # index file, not content
        raw = p.read_text(encoding="utf-8", errors="ignore")
        clean = strip_private(raw)
        desc = extract_description(clean)
        snippet = first_body_line(clean) or desc
        # Weight description by repeating it — helps short descriptions beat long bodies
        index_text = (desc + " ") * 5 + clean
        out.append((p.name, desc, snippet, index_text))
    return out


def build_or_load_index(mem_dir: Path, cache_path: Path):
    files = load_files(mem_dir)
    latest_mtime = max((mem_dir / name).stat().st_mtime for name, *_ in files)
    if cache_path.exists() and cache_path.stat().st_mtime >= latest_mtime:
        with cache_path.open("rb") as f:
            return pickle.load(f)
    corpus = [text for _, _, _, text in files]
    vec = TfidfVectorizer(
        lowercase=True,
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.9,
        stop_words="english",
    )
    matrix = vec.fit_transform(corpus)
    index = {"files": files, "vectorizer": vec, "matrix": matrix}
    with cache_path.open("wb") as f:
        pickle.dump(index, f)
    return index


def search(index, query: str, top: int):
    q_vec = index["vectorizer"].transform([query])
    sims = cosine_similarity(q_vec, index["matrix"])[0]
    ranked = sorted(enumerate(sims), key=lambda x: -x[1])
    results = []
    for idx, score in ranked[:top]:
        if score <= 0:
            continue
        name, desc, snippet, _ = index["files"][idx]
        results.append((name, score, desc, snippet))
    return results


def estimate_tokens(path: Path) -> int:
    size = path.stat().st_size
    return size // 4  # ~4 chars/token


def main() -> int:
    ap = argparse.ArgumentParser(description="Semantic-ish memory retrieval")
    ap.add_argument("query", nargs="+", help="Query string")
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR, help="Memory directory")
    ap.add_argument("--top", type=int, default=5, help="Number of results")
    ap.add_argument("--cache", type=Path, default=None, help="Cache path")
    ap.add_argument("--paths", action="store_true", help="Print full paths only (for scripting)")
    args = ap.parse_args()

    query = " ".join(args.query)
    mem_dir = args.dir.resolve()
    if not mem_dir.is_dir():
        print(f"[ERROR] Memory dir not found: {mem_dir}", file=sys.stderr)
        return 1
    cache_path = args.cache or mem_dir / ".tfidf_index.pkl"

    index = build_or_load_index(mem_dir, cache_path)
    results = search(index, query, args.top)
    if not results:
        print("No matches.", file=sys.stderr)
        return 0

    if args.paths:
        for name, _, _, _ in results:
            print(mem_dir / name)
        return 0

    total_tokens = 0
    print(f"Query: {query!r}")
    print(f"Memory dir: {mem_dir}")
    print(f"Indexed: {len(index['files'])} files")
    print()
    print(f"{'score':>6}  {'tokens':>6}  file")
    print(f"{'-----':>6}  {'------':>6}  {'-' * 60}")
    for name, score, desc, snippet in results:
        tokens = estimate_tokens(mem_dir / name)
        total_tokens += tokens
        print(f"{score:>6.3f}  {tokens:>6}  {name}")
        if desc:
            print(f"{'':>14}  desc: {desc[:100]}")
        elif snippet:
            print(f"{'':>14}  {snippet[:100]}")
    print()
    print(f"Total: ~{total_tokens} tokens if all loaded (cap MEMORY.md = ~800)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
