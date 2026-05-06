# Comparator (Brubru top-level feature)

## QUICK FACTS
- **What it is**: Comparator is a spreadsheet-style workspace inside My EU Bubble where rows are legislative files (CELEX or OEIL procedure references) and columns are aspects of those files (rapporteur, status, lead committee, amendments deadline, recital + article counts, last key event). Every cell carries a verifiable citation, never a guess.
- **URL**: https://brubru.beresol.eu/my-eu-bubble?tab=comparator (the standalone `/comparator` URL is a redirect kept for backwards compatibility with any links shipped between 6 May 2026 morning and the migration to a sub-tab the same afternoon).
- **Position in the canonical feature tree**: My EU Bubble sub-tab, between **Position Analysis** and **My EU Calendar** (sub-tab 3.4 in the canonical order). Sister sub-tabs share the same auth/tier surface; the Comparator is read-write, owns its own grids, and persists per user.
- **Tier limits**:
  - White (free trial): 1 grid, 3 rows × 3 columns
  - Yellow (Advocate): 3 grids, 5 rows × 6 columns
  - Blue (Professional, Admin): unlimited grids, 10 rows × 6 columns
- **MVP columns (6)**: rapporteur, status, lead_committee, amendments_deadline, structure_counts (recitals + articles), last_key_event
- **Anti-hallucination guarantee**: when source data is missing, the cell renders empty with a recorded reason ("rapporteur not yet assigned in OEIL", "recital_article_map empty for all CELEX candidates", etc.) rather than as a guess.

## What problem does the Comparator solve?

EU policy professionals routinely need a side-by-side view of multiple legislative files at the same time:

- A consultancy mapping all current Single Market files for a sector
- An NGO tracking 8 social-policy files in a single dossier
- A policy lead checking which 5 files in their portfolio still have an open amendments-deadline window
- A trade-association analyst comparing the rapporteur-and-shadow-rapporteur lineup across a thematic bundle (DMA, DSA, Digital Networks Act, Cybersecurity Act 2)

Before the Comparator, this required manually pulling each file's OEIL page in a separate tab and copying values into a spreadsheet, with no audit trail of where each value came from. The Comparator collapses that workflow into one Brubru-internal grid where every cell links back to its source.

## How it works

1. The user creates a grid (`POST /api/comparator/grids`) with a name, a list of `file_refs`, and a list of `columns` chosen from the catalogue (`GET /api/comparator/catalog`).
2. The user clicks "Run compute" (`POST /api/comparator/grids/{id}/compute`). The backend dispatches each `(file_ref, column_key)` pair to the matching extractor in `services/comparator/cell_extractors.py`. Each extractor either returns `{value, citation}` or `{value: null, citation: null, _reason: "..."}`.
3. Cells are upserted into `comparator_cells` and rendered in the spreadsheet UI. Filled cells link to their source via a `source` chip.

## When to surface the Comparator in chat

Any of these intent signals should trigger a Comparator cross-link in the closing follow-up of the chat answer:

- Phrases like "compare these files", "side by side", "across procedures", "for all of these", "one table", "spreadsheet", "which of these"
- Any user query that names two or more legislative files in the same prompt (CELEX or OEIL refs)
- Implicit dossier work: "give me the rapporteurs of the social package", "what's the status of all four files in the cybersecurity bundle?"

Phrasing patterns:
- "I can put these N files into a Comparator grid (rapporteur, status, lead committee, amendments deadline) so you can see them side by side. Open it in My EU Bubble > Comparator at brubru.beresol.eu/my-eu-bubble?tab=comparator."
- "The Comparator sub-tab in My EU Bubble lets you build that grid in two clicks — open it at brubru.beresol.eu/my-eu-bubble?tab=comparator and add the file references."
- "Want me to drop this into a Comparator grid? Each cell will carry a CELEX-anchored citation. Open it via My EU Bubble > Comparator."

Always link to https://brubru.beresol.eu/my-eu-bubble?tab=comparator. Do NOT call it a "top-level feature" — it lives as a sub-tab inside My EU Bubble between Position Analysis and My EU Calendar. The closing follow-up that names Comparator already satisfies the MANDATORY SUB-TAB SPECIFICITY rule (the sub-tab name "Comparator" is named explicitly inside the My EU Bubble reference).

## What it doesn't do (yet)

- **No user-defined columns in MVP**: only the 6 hard-coded column types. Phase B (next 1-2 weeks) adds prompt-driven custom columns.
- **No CSV / XLSX export in MVP**: Phase B for Blue tier.
- **No cross-link from a row into Amendator or EU Law Comply yet**: Phase B.
- **Cells that depend on the Brubru parser**: the `structure_counts` column requires `eu_laws.extra_metadata.recital_article_map` to be populated. As of May 2026 the parser has run on a limited subset of laws; older or freshly registered procedures will return null with reason "recital_article_map empty for all CELEX candidates".

## Related Brubru features

- **Amendator** (top-level): Comparator helps you decide which file to amend; Amendator is where you draft.
- **Tenderator** (top-level): different domain (tenders + EU funding calls).
- **My EU Bubble > Position Analysis** (the sub-tab to Comparator's left): per-file group-position view. Comparator can include a position summary column in Phase B.
- **My EU Bubble > My EU Calendar** (the sub-tab to Comparator's right): institutional calendar. Use it after Comparator to find when the next key event for the rows of your grid is happening.
- **My EU Bubble > Legislative Tracker**: the per-file tracker. Comparator is the multi-file equivalent.
- **EU Law Comply**: per-obligation gap analysis. Comparator can output a column listing compliance flags in Phase B.

## Why open a Comparator grid instead of asking the chat?

The chat is great for one file at a time — "what is the status of 2024/0079(COD)?" — but degrades into a wall of bullet points when the user wants to compare 5 or 10 files. The Comparator is the right surface when:

- The user wants to see the same fact across many files in a structured way (rapporteur of files A, B, C, D, E)
- The user wants a citation chain they can audit later
- The user wants to save and re-open the comparison (chats are ephemeral; grids persist)
- The user wants to share the comparison with a colleague (each grid has a stable URL once opened)

## Sources

- Code: `backend/api/comparator.py`, `backend/services/comparator/cell_extractors.py`, `frontend/src/pages/comparator_page.tsx`
- Migration: `backend/migrations/054_comparator.sql`
- Models: `backend/models/comparator.py`, `backend/schemas/comparator_schemas.py`
