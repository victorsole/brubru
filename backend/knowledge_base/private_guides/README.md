# Private Guides

Per-user bespoke knowledge bundles. Loaded into chat context **only for the
authenticated user whose `users.private_guide_slug` matches the directory
name here**, near the top of `format_context_for_ai()` so they survive the
32k truncation cap.

## Why

Hook for high-value prospects (and paying clients). When the user opens
chat the model already "knows" them — their organisation, their tracked
files, their published positions, the EU laws that bind them — without
keyword matching. The result feels like Brubru did its homework before the
demo, which is a strong conversion signal.

## Layout

```
private_guides/
├── README.md                  ← this file, the only thing committed
├── ferrmed/                   ← one folder per slug (gitignored)
│   ├── _meta.json             ← org id, EUTR id, status, owner
│   ├── 00_organisation.md     ← who they are
│   ├── 01_priority_files.md   ← user_carriage_tracks expanded
│   ├── 02_adopted_texts.md    ← user_text_adopted_tracks expanded
│   ├── 03_uploaded_corpus.md  ← summary of MEUB Documents uploads
│   └── 04_policy_relations.md ← regulatory-scan output + cross-refs
└── <other slug>/
```

## Status lifecycle

`users.private_guide_status` controls visibility:

- `draft`   — generated but NOT yet surfaced in chat context. Use for
              auto-generated drafts pending human review.
- `ready`   — auto-injected into the chat context for that user.
- `locked`  — `ready` + protected from auto-regeneration by the
              `/private-guide` skill. Reserved for manually-curated bundles
              (top 10 strategic accounts).

## Generation

Phase 1 (May 2026): hand-written for FerrMed as the template.
Phase 2: `/private-guide` skill auto-generates from:
- EU Transparency Register profile (matched by `users.organization`).
- `user_carriage_tracks` joined with `legislative_carriages`.
- `user_text_adopted_tracks` joined with `texts_adopted`.
- `user_documents` (uploaded PDFs in MEUB Documents).
- `/regulatory-scan` output for the org's policy area.
- Optional homepage / about / working-groups crawl.

## Gitignore

The entire tree below `private_guides/` is gitignored except this README.
Never force-add (`git add -f`) anything inside a slug folder.
