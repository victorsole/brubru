"""
MEUB sync source registry.

ONE place that declares every auto-synced MEUB feed: which CLI runs it, on
which cadence tier, and how to label it. The cron tier endpoints loop over
this by tier; the freshness API labels chips from it. Adding a source later
is a single line here, not new plumbing.

Tiers (cadence is set on the Railway cron schedule, not here):
  - "fast" (~3h): intraday newswires, the Official Journal, votes
  - "warm" (~6h): calendar, transcripts (metadata), lobby meetings, questions

Already-scheduled feeds (OEIL/Tracked Files, Texts Adopted, Commission docs,
Committee Work, Consultations) keep running via their existing cron endpoints
and are intentionally NOT duplicated here.
"""

from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass(frozen=True)
class SourceSpec:
    key: str                       # stable id, used as sync_runs.source_key + chip key
    label: str                     # human label for the freshness chip
    tier: str                      # 'fast' | 'warm'
    script: str                    # relpath under backend/ (run as a subprocess)
    args: Tuple[str, ...] = field(default_factory=tuple)
    timeout: int = 900             # seconds
    # Hours after which a missed refresh is considered "stale" (drives the
    # staleness email for fast feeds and the amber chip in the UI).
    stale_after_hours: int = 7


# fmt: off
MEUB_SOURCES: List[SourceSpec] = [
    # ---- FAST (~3h): things the EU publishes intraday ---------------------
    SourceSpec("news_dg",      "News - Commission & EU bodies", "fast", "scripts/sync_dg_news.py",       timeout=900),
    SourceSpec("news_ep",      "News - Parliament",             "fast", "scripts/sync_ep_news.py",        timeout=900),
    SourceSpec("news_bespoke", "News - other bodies",           "fast", "scripts/sync_bespoke_news.py",   timeout=900),
    SourceSpec("news_ft",      "News - Funding & Tenders",      "fast", "scripts/sync_ft_news.py",         timeout=600),
    # Council documents (D1, 27 Aug 2026). `/api/v1/council-documents` served a
    # CALENDAR because its documents branch had zero rows since it shipped. A
    # corpus that is filled once and never refreshed becomes the same defect
    # again, quietly, so it is on the warm tier. `--window-days 7` keeps each
    # window well under the register's 1,000-document cap; bodies are fetched so
    # `q` can find documents whose bureaucratic subject line omits the topic.
    SourceSpec("council_documents", "Documents - Council", "warm",
               "scripts/ingest_council_documents.py",
               ("--apply", "--since-days", "14", "--window-days", "7", "--fetch-bodies"),
               timeout=1800, stale_after_hours=48),

    # ---- EP texts pipeline (registered 27 Aug 2026) ----------------------
    # The tier runner executes THIS LIST IN ORDER, sequentially and fail-soft,
    # so the order below IS the dependency chain: fetch texts -> fetch their
    # bodies -> parse OEIL roles -> date the resolutions -> grow the resolutions
    # corpus -> fill the joined columns -> check for gaps.
    #
    # Every one of these was a manual command on 27 Aug. `sync_texts_adopted`
    # had NEVER been scheduled at all, which is why the corpus sat frozen at 251
    # rows opening on 20 January 2026 and the EP's November 2025 resolution on
    # protecting minors online was invisible to every search.
    #
    # All are idempotent: existing rows are skipped or COALESCE-guarded, so a run
    # that overlaps the previous one is harmless.
    SourceSpec("texts_adopted", "Texts adopted - Parliament", "warm",
               "scripts/sync_texts_adopted.py", ("--recent-days", "30"),
               timeout=1800, stale_after_hours=48),
    SourceSpec("texts_adopted_bodies", "Texts adopted - full text", "warm",
               "scripts/backfill_texts_adopted_bodies.py", ("--apply", "--limit", "150"),
               timeout=1800, stale_after_hours=48),
    SourceSpec("oeil_roles", "Carriages - committee roles", "warm",
               "scripts/backfill_oeil_committee_roles.py", ("--apply",),
               timeout=900, stale_after_hours=48),
    SourceSpec("resolution_dates", "Resolutions - adoption dates", "warm",
               "scripts/backfill_resolution_dates.py", ("--apply",),
               timeout=600, stale_after_hours=48),
    SourceSpec("resolutions_corpus", "Resolutions - corpus", "warm",
               "scripts/backfill_ep_resolutions_corpus.py", ("--apply",),
               timeout=600, stale_after_hours=48),
    SourceSpec("ep_enrich", "EP texts - joined columns", "warm",
               "scripts/enrich_ep_texts_and_resolutions.py", ("--apply",),
               timeout=600, stale_after_hours=48),
    # LAST on purpose: it asks what is still missing AFTER everything above ran,
    # and exits non-zero on a real gap so the run is recorded as failed rather
    # than passing quietly. A backfill that reports success over its own range
    # proves nothing about whether the range was right.
    SourceSpec("ep_council_gaps", "EP + Council completeness", "warm",
               "scripts/ep_council_completeness.py", (),
               timeout=300, stale_after_hours=48),
    SourceSpec("oj",           "My OJ (Official Journal)",      "fast", "scripts/sync_oj.py",             ("--apply", "--explain"), timeout=900),
    # Must stay directly after "oj": the tier runs sources in list order, so the
    # ingest lands the day's entries and this translates them in the same pass.
    # Softcatala NMT (local CTranslate2, free) writes oj_entry_translations, which
    # api/oj.py reads straight from the DB, so unlike the acquis corpus there is
    # no deploy step to mirror. Per-entry cost swings with explanation length
    # (~1.5s typical, ~12s worst seen), so --limit 60 keeps one run inside the
    # timeout while still clearing a normal OJ day (10-72 entries) in one go;
    # the ~3h tier gives 8 passes/day, so any backlog drains within a day.
    SourceSpec("oj_catalan",   "My OJ - Catalan translations",  "fast", "scripts/backfill_oj_translations.py", ("--limit", "60"), timeout=1200),
    # --max-sittings caps the work per run. Without it this script walks EVERY
    # sitting day, each behind a JS challenge at 9s settle + up to 20s
    # networkidle, so it is unbounded work inside a bounded window: it failed
    # 49 of 49 runs over 14 days, 43 of them on the 1200s timeout, and never
    # once succeeded. Sittings are processed NEWEST FIRST, so a cap still
    # captures the votes that matter and the tail catches up across runs.
    # 20 was a GUESS and it was wrong: both runs on 24-25 Aug still hit
    # timeout_1200s. The arithmetic nobody did first: each sitting tries up to
    # THREE candidate dates (the sitting, +1, -1) and each fetch costs 9s settle
    # plus up to 20s networkidle, so worst case is 20 x 3 x 29s = ~1,740s against
    # a 1,200s budget. 6 sittings is 6 x 3 x 29 = ~520s, comfortably under half.
    # Newest-first, so the tail still catches up across runs.
    SourceSpec("votes_ep",     "Votes - Parliament",            "fast", "scripts/sync_ep_votes.py",       ("--apply", "--max-sittings", "6", "--deadline-seconds", "900"), timeout=1200),
    SourceSpec("votes_council","Votes - Council",               "fast", "scripts/sync_council_votes.py",  ("--max", "20"), timeout=900),

    # ---- WARM (~6h): slower-moving institutional feeds --------------------
    SourceSpec("calendar",          "My EU Calendar",            "warm", "scripts/sync_eu_calendar.py",          timeout=1200, stale_after_hours=14),
    SourceSpec("calendar_dg_events","Calendar - DG events",      "warm", "scripts/sync_dg_events.py",            timeout=900,  stale_after_hours=14),
    SourceSpec("calendar_ft_events","Calendar - Funding & Tenders","warm","scripts/sync_ft_events.py",           timeout=600,  stale_after_hours=14),
    SourceSpec("transcripts",       "Transcripts (committee)",   "warm", "scripts/sync_committee_transcripts.py", ("--max", "10", "--days", "7"), timeout=1200, stale_after_hours=14),
    SourceSpec("lobby_meetings",    "Lobby Meetings",            "warm", "scripts/sync_mep_lobby_meetings.py",    ("--procedures", "20", "--profiles", "10"), timeout=1200, stale_after_hours=14),
    SourceSpec("parl_questions",    "Parliamentary Questions",   "warm", "scripts/ingest_parl_questions.py",      timeout=900,  stale_after_hours=14),
    SourceSpec("agency_consultations","Consultations - EU agencies","warm","scripts/sync_agency_consultations.py", timeout=600,  stale_after_hours=14),
    # Names files that arrived without a readable one. Unlike the feeds above
    # this ingests nothing: it fills legislative_carriages.short_title for rows
    # still NULL, so a new act stops being shown as "Council Implementing
    # Decision (EU) 2026/1923 of 30 July 2026 amending...". Idempotent, so once
    # the backlog is cleared each run is a no-op that only picks up new
    # arrivals. --limit and --sleep keep one run inside the timeout and under
    # the model provider's rate limit, which answers a 429 by sleeping ~60s
    # rather than falling through.
    SourceSpec("carriage_short_titles","File names (AI)",         "warm", "scripts/backfill_carriage_short_titles.py", ("--limit", "40", "--sleep", "4"), timeout=900, stale_after_hours=48),
]
# fmt: on


def sources_for_tier(tier: str) -> List[SourceSpec]:
    return [s for s in MEUB_SOURCES if s.tier == tier]


def all_source_keys() -> List[str]:
    return [s.key for s in MEUB_SOURCES]


def get_source(key: str) -> SourceSpec | None:
    return next((s for s in MEUB_SOURCES if s.key == key), None)
