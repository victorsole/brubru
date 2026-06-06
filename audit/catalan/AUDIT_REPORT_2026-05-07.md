# Catalan Translations Linguistic Audit — 7 May 2026

**Corpus:** 8,815 translations on disk / DB / FTP (`data/legislacio-ue-catala/`).
**Engine in scope:** Softcatalà NMT (`eng-cat-2024-09-24`), with three Sonnet-fallback acts that leaked AI prompts.
**Audit script:** `backend/scripts/audit_catalan_translations.py` (Tier A static + Tier B LanguageTool/Softcatalà API + manual Tier C).

---

## Executive summary

| Severity | Issue | Acts affected | Auto-fixable |
|---|---|---:|:---:|
| **P0** | AI-leak — Sonnet refusal text rendered as Catalan body | **3** | No (re-translate) |
| **P1** | `REGLAMENT D'APLICACIÓ` should be `REGLAMENT D'EXECUCIÓ` (Brubru glossary) | **1,374** | Yes |
| **P1** | `Corrigendum` untranslated in `<h1>` | **286** | Yes |
| **P2** | Untranslated mid-text English (`shall`, `Member State(s)`, `the European Parliament`, `Implementing` …) | **44** | Partly |
| **P2** | `OPINIÓ` should be `DICTAMEN` in titles | **85** | Yes |
| **P2** | Casing error: `Estats Membres` → `Estats membres` (Catalan house style) | **~465 hits / 25 acts** | Yes |
| **P3** | `DIRECTRIU` should be `DIRECTIVA` | **22** | Yes |
| **P3** | Typography (missing space after `;` `:` `,`, double commas, etc.) | ~952 hits / many acts | Yes |
| **P3** | `Brussels` → `Brussel·les` | **1** | Yes |

**Bottom line:** 0.49 % of acts (43/8815) carry obvious untranslated English. The much larger fix opportunity is corpus-wide glossary normalisation (`d'aplicació` → `d'execució` alone touches 1,374 acts). All P1–P3 fixes can be applied with a single regex-replace pass over `index.html` files; only the 3 P0 acts need re-translation through the Softcatalà NMT.

---

## Tier A — static rule sweep (free, ~3 min over full corpus)

`audit/catalan/static_audit_20260507_114630.jsonl` — per-act issue list.

```
[INFO] Tier A done — 43/8815 acts flagged. Top rules:
       17  untranslated_shall                  (English modal verb in body)
       12  glossary_implementing               ("Implementing" leftover, untranslated)
        8  untranslated_member_state           ("Member State(s)" untranslated)
        3  untranslated_european_parliament    ("the European Parliament" untranslated)
        3  ai_leak_please_provide              (P0 — Sonnet refusal text in body)
        1  glossary_brussel_les                ("Brussels" not "Brussel·les")
        1  untranslated_having_regard          ("HAVING REGARD" untranslated)
```

### P0 — broken translations (3 acts, MUST re-translate)

These were attempted via Sonnet during the credit-exhausted period and the model refused mid-prompt; the refusal text was imported as the translated body.

| CELEX | Leaked phrase |
|---|---|
| `32025D1452` | "please provide the complete text you'd like me to translate from English to Catalan?" |
| `32025D1972` | "I need the complete text of Article 7 to provide an accurate translation. You've only provided the article heading…" (×6 articles) |
| `32025D2157` | "I need the complete text after 'Article 1' to provide the translation." |

**Action:** delete `data/legislacio-ue-catala/{32025D1452,32025D1972,32025D2157}/`, drop the matching `catalan_translations` rows, and re-run `python3.12 scripts/catalan_translate.py --translate <xml> --celex <celex>` (Softcatalà engine, default — no Sonnet).

### P2 — untranslated mid-text English fragments (40 acts)

Exact list of acts and the leaked English token in `static_audit_20260507_114630.jsonl`. Examples:

- `shall` / `must`: `32006R1907` (REACH, 2 hits), `32023R1626`, `32024R0585`, `32025R0437`, `32025R0505`, `32025R1161`, `32025R1204`, `32025R1241`, `32025R1283`, `32025R1284`, `32025R1473` …
- `Member State(s)`: `32010R0045`, `32019R0833`, `32022R0952`, `32024R0775`, `32024R2779`, `32025R1205`, `32025R2090`, `32025R2192`
- `the European Parliament`: `32023R2462`, `32025R90020`, `32025R90577`
- `Implementing` (raw, not yet translated): 12 acts, all 2024-2025 implementing regulations
- `HAVING REGARD`: `C_2019008_p01000101` (an OJ-fragment row that the binding-only filter would have excluded anyway)

These are sentence-level NMT misses — typically the NMT preserved the English word because the surrounding sentence wasn't long enough to provide context. Most are **automatically fixable** with a targeted glossary substitution (see Step 2 below). For the rest, re-running Softcatalà NMT on just the affected paragraph is reliable.

---

## Tier B — Softcatalà / LanguageTool API on the 43 flagged acts

`audit/catalan/lt_audit_20260507_114630.jsonl` — per-act API findings.

Endpoint: `https://api.softcatala.org/corrector/v2/check` (LanguageTool 6.8 backend), 0.6s polite delay, 30 chunks/act max. **47 network errors** (≈ 1 %), findings remain indicative.

### Total: 4,157 findings across 43 acts, top categories

| Category | Hits | Real signal? |
|---|---:|---|
| TYPOS (`MORFOLOGIK_RULE_CA_ES`) | 1,943 | **Mixed** — the spell-checker flagged HTML entities like `catal&agrave;`, `traducci&oacute`, `&eacute` in the page footer because the audit script's `visible_text()` decodes only `&nbsp;` `&amp;` `&quot;` `&apos;`. Drop these as false positives. ~950 are real typos in body text. |
| TYPOGRAPHY (whitespace + punctuation) | 952 | **Real.** `ESPAI_DARRERE_PUNTICOMA` (372) — missing space after `;`. `COMMA_PARENTHESIS_WHITESPACE` (203). `ESPAI_DARRERE_DOSPUNTS` (140). NMT output dropping whitespace around punctuation. |
| **CASING** | **557** | **Real.** `CA_CHECKCASE_ESTATS_MEMBRES` (293) + `CA_CHECKCASE_ESTAT_MEMBRE` (172). Catalan house-style is lower-case "Estats membres" / "Estat membre"; our translations frequently use "Estats Membres" / "Estat Membre". |
| PUNCTUATION | 282 | **Real.** Includes `UNPAIRED_BRACKETS` (162) — partly the `[...]` Publications-Office redactions (false positives), partly real unbalanced parens. |
| DIACRITICS | 36 | **Real** — accent omissions caught by spell-checker. |
| PREFERABLE_EXPRESSIONS | 68 | **Real** — `CELEBRAR_CONTRACTE` (26): use "signar un contracte" not "celebrar un contracte"; `MATEIX_INCORRECTE` (22): redundant "el mateix" usage. |
| INCORRECT_EXPRESSIONS | 33 | **Real** — Brubru-glossary–adjacent issues. |

### Worst acts by LT finding count (top 10)

```
273  32025D1972   (P0 — also AI leak)
265  32019R0833
243  32023R2462
212  32010R0045
168  32025R1082
166  32006R1907   (REACH — long act, finding density is in fact low per page)
160  32025R2090
149  32012R0013
143  C_2018012_p01000101   (will be removed by binding-only audit anyway)
141  32024R2507
```

Caveat: the Tier B sample was deliberately the 43 Tier-A-flagged acts (highest noise floor). A full-corpus Tier B sweep would take ~120 hours at 0.6 s/req and is not warranted.

---

## Tier C — corpus-wide cross-act terminology consistency

Manual scan of `<h1>` titles across all 8,815 acts for known glossary deviations.

| Pattern in title | Should be | Acts |
|---|---|---:|
| **`REGLAMENT D'APLICACIÓ`** | `REGLAMENT D'EXECUCIÓ` | **1,374** |
| **`Corrigendum`** (untranslated in `<h1>`) | `Correcció d'errades` | **286** |
| **`OPINIÓ`** at title start | `DICTAMEN` | **85** |
| **`DIRECTRIU`** at title start | `DIRECTIVA` | **22** |

**Note on `D'APLICACIÓ` vs `D'EXECUCIÓ`:** both are legitimate Catalan translations of "implementing" but the Brubru standard (CLAUDE.md "Catalan EU Legislation Translation Pipeline") and the official EU translation memory both prefer `d'execució`. The 1,374 affected acts are not "wrong" Catalan — they are **inconsistent with the rest of the corpus**.

**Note on `DIRECTRIU`:** this *is* wrong — "directriu" in Catalan means "guideline" / "non-binding instruction", whereas an EU Directive is binding. All 22 acts must be corrected.

**Note on `Corrigendum`:** these are 2023+ corrigendum series; the NMT didn't translate the English word. Translation: "Correcció d'errades del…" (or the more formal "Esmena al…").

---

## Recommended remediation (ordered by effort × impact)

### Step 1 — re-translate the 3 P0 acts (10 min)

```bash
cd /Users/victorsole/Documents/GitHub/brubru/backend
for c in 32025D1452 32025D1972 32025D2157; do
  rm -rf ../data/legislacio-ue-catala/$c
  python3.12 -c "
from core.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
db.execute(text(\"DELETE FROM catalan_translations WHERE celex='$c'\"))
db.commit()
db.close()
"
  # Find the source XML and re-translate via Softcatalà NMT
  XML=$(grep -l "celex='$c'" ../docs/LEG_2025-11/*/fmx4/*.xml 2>/dev/null | head -1)
  python3.12 scripts/catalan_translate.py --translate "$XML" --celex $c
done
python3.12 scripts/sync_catalan_disk_to_db.py --deploy-pending
```

### Step 2 — corpus-wide glossary normalisation (1,767 acts, ~10 min)

Single sweep over all `index.html` files. Build `backend/scripts/fix_catalan_glossary.py` that applies (in this exact order, regex-anchored to `<h1>` for title-only fixes and to body for content fixes):

```python
HTML_FIXES = [
    # Title-only — anchor to h1
    (r"(<h1[^>]*>.*?)REGLAMENT\s+D'APLICACIÓ",   r"\1REGLAMENT D'EXECUCIÓ"),
    (r"(<h1[^>]*>.*?)Reglament\s+d'aplicació",   r"\1Reglament d'execució"),
    (r"(<h1[^>]*>.*?)\bDIRECTRIU\b",             r"\1DIRECTIVA"),
    (r"(<h1[^>]*>.*?)\bDirectriu\b",             r"\1Directiva"),
    (r"(<h1[^>]*>.*?)\bOPINIÓ\b",                r"\1DICTAMEN"),
    (r"(<h1[^>]*>.*?)\bOpinió del\b",            r"\1Dictamen del"),
    (r"(<h1[^>]*>.*?)\bCorrigendum\b",           r"\1Correcció d'errades de"),

    # Body-wide — Brubru glossary
    (r"\bd['’]?implementaci[óo]\b",              r"d'execució"),
    (r"\bha\s+aconseguit\b",                     r"ha adoptat"),

    # Untranslated fragments — common safe substitutions
    (r"\bMember States?\b",                      lambda m: "Estats membres" if m.group(0).endswith("s") else "Estat membre"),
    (r"\bthe European Parliament\b",             r"el Parlament Europeu"),
    (r"\bthis Regulation\b",                     r"aquest Reglament"),
    (r"\bthis Directive\b",                      r"aquesta Directiva"),
    (r"\bin accordance with\b",                  r"d'acord amb"),

    # Casing — Estats membres house style (lower-case 'm')
    (r"\bEstats Membres\b",                      r"Estats membres"),
    (r"\bEstat Membre\b",                        r"Estat membre"),

    # Brussel·les
    (r"\bBrussels\b",                            r"Brussel·les"),
]
```

For "shall" / "must" / "Implementing" the right call is **paragraph-level Softcatalà re-translation**, not a word substitution — context-free replacement risks "shall" → "haurà de" mid-imperative, which is wrong. The list of 40 affected acts is small enough to handle individually.

After applying, regenerate `frontend/public/guides/index.html` is **not** needed (this is a different surface), but **do** re-FTP the changed `index.html` files. The fix script should:

1. Compute SHA256 before/after to skip unchanged files
2. Update `catalan_translations.html_size_bytes` for changed rows
3. NULL out `catalan_translations.deployed_at` so `sync_catalan_disk_to_db.py --deploy-pending` re-uploads them

### Step 3 — typography sweep (whitespace around punctuation, ~952 hits)

Smaller fix scope, can be folded into the same script:

```python
TYPOGRAPHY_FIXES = [
    (r";([A-Za-zÀ-ÿ])", r"; \1"),    # ESPAI_DARRERE_PUNTICOMA
    (r":([A-Za-zÀ-ÿ])", r": \1"),    # ESPAI_DARRERE_DOSPUNTS
    (r",,",             r","),       # DOUBLE_PUNCTUATION
    (r"\s+,",           r","),       # space-before-comma
    (r"\s+;",           r";"),       # space-before-semicolon
]
```

Apply with care to avoid breaking URLs (`https://…`) — anchor away from `://`.

### Step 4 — re-audit and commit a clean baseline

```bash
python3.12 backend/scripts/audit_catalan_translations.py --softcatala --sample 50 --quiet
```

This pulls a fresh **random 50-act** Tier-B sample (not `--only-flagged`), giving a true baseline of corpus-wide LanguageTool noise. Expect typography findings to drop from ~950 to under 100, casing findings to drop to near zero, and TYPOS to drop sharply once the HTML-entity false positives are fixed in `visible_text()`.

---

## Audit script improvements (deferred)

For follow-up work — the audit script itself has fixable issues:

1. **HTML-entity decoding** in `visible_text()` — replace the inline decoder with `html.unescape()`, which decodes all ~250 named entities + numeric refs. Eliminates the `catal&agrave`/`traducci&oacute`/`&eacute` false positives (saves ~1,000 false positives in Tier B).
2. **Strip footer/header chrome** before LT submission — the page footer ("Traducció oficial al català per BRUBRU. Versió HTML.") gets included in every chunk, multiplying findings by chunk count.
3. **Network-error retry** — 47/2,400 chunks (~2 %) failed mid-sweep. Switch from urllib to requests + a backoff_factor.
4. **Add a Tier-D consistency-graph mode** that builds an `(EN-source-phrase → CA-translation)` index across the corpus and reports terms with > 1 Catalan rendering.

---

**Files**

- `backend/scripts/audit_catalan_translations.py` — audit script
- `audit/catalan/static_audit_20260507_114630.jsonl` — Tier A per-act issues
- `audit/catalan/lt_audit_20260507_114630.jsonl` — Tier B per-act LT findings
- `audit/catalan/summary_20260507_114630.md` — auto-generated summary
- `audit/catalan/AUDIT_REPORT_2026-05-07.md` — **this report**
