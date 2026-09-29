#!/usr/bin/env python3
"""Re-score existing tender matches with the current matcher (29 Sep 2026).

The matcher never revisits a (profile, tender) pair once a match exists, so
matches made under an older rule keep their old verdict for ever. The keyword
rule changed on 29 Sep 2026 from substring to whole-word ("CER" had fired inside
"certified", "SME" inside "assessment"). This re-runs the matcher's own
`_calculate_match` on every existing pair of an OPEN tender:

  * removed ONLY when all hold: the user never touched it (not viewed, saved,
    dismissed, applied, rated or annotated); every keyword hit it had under the
    old substring rule is gone under the new one (it matched only through a
    false hit such as "CER" inside "certified"); and CPV gives no sector
    evidence (no signal, or under CONTENT_RELEVANCE_FLOOR)
  * everything else is kept and counted. Pairs now under the threshold for
    other reasons are kept on purpose: a first threshold-based re-score would
    have deleted Connect Europe's telecom-services notices, because the CPV
    scorer divides an exact match by the profile's code count (0.17 for one of
    six), a defect held for a product decision. Scores are not rewritten.

    python3.12 scripts/rescore_tender_matches.py              # dry run
    python3.12 scripts/rescore_tender_matches.py --apply
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import and_, or_  # noqa: E402
from sqlalchemy.orm import defer  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from models.tender import Tender, TenderMatch, TenderProfile  # noqa: E402
from services.tenders import matcher as matcher_mod  # noqa: E402
from services.tenders.matcher import TenderMatcher  # noqa: E402


def _substring_in(keyword, text):
    kw = (keyword or "").strip().lower()
    return bool(kw) and kw in text


def untouched(m: TenderMatch) -> bool:
    return not (m.is_viewed or m.is_saved or m.is_dismissed or m.is_applied
                or m.user_notes or m.user_rating is not None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        m = TenderMatcher(db)
        threshold = m.score_threshold
        profiles = {p.id: p for p in db.query(TenderProfile).all()}
        stats = collections.Counter()
        per_profile = collections.Counter()
        samples = collections.defaultdict(list)
        for pid, profile in profiles.items():
            rows = (db.query(TenderMatch, Tender)
                    .join(Tender, Tender.id == TenderMatch.tender_id)
                    .options(defer(Tender.xml_content), defer(Tender.raw_json))
                    .filter(TenderMatch.profile_id == pid,
                            Tender.status == "open")
                    .all())
            for match, tender in rows:
                stats["checked"] += 1
                if not untouched(match):
                    stats["kept_touched_by_user"] += 1
                    continue
                txt = f"{tender.title or ''} {tender.description or ''}".lower()
                kws = profile.keywords or []
                old_hits = [k for k in kws if _substring_in(k, txt)]
                new_hits = [k for k in kws if matcher_mod._keyword_in(k, txt)]
                cpv = m._score_cpv_match(tender, profile)
                spurious_only = bool(old_hits) and not new_hits
                no_sector_evidence = cpv is None or cpv < matcher_mod.CONTENT_RELEVANCE_FLOOR
                if spurious_only and no_sector_evidence:
                    stats["removed_spurious_keyword_only"] += 1
                    per_profile[(pid, "spurious_keyword_only")] += 1
                    if len(samples[pid]) < 4:
                        samples[pid].append(f"{old_hits} in: {(tender.title or '')[:60]}")
                    if args.apply:
                        db.delete(match)
                    continue
                if m._calculate_match(tender, profile).total_score < threshold:
                    # Below the threshold for other reasons (mainly the CPV scoring
                    # held for a product decision): kept, and counted.
                    stats["kept_below_threshold_pending_cpv_decision"] += 1
                else:
                    stats["kept_still_matches"] += 1
            if args.apply:
                db.commit()
        print(f"[OK] threshold {threshold} | {dict(stats)}{'' if args.apply else ' (dry run)'}")
        for (pid, cause), n in sorted(per_profile.items(), key=lambda x: -x[1])[:15]:
            p = profiles[pid]
            print(f"  profile {pid} ({getattr(p, 'name', '') or p.user_id}) {cause}: {n}")
        for pid, s in list(samples.items())[:6]:
            for line in s:
                print(f"    [{pid}] {line}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
