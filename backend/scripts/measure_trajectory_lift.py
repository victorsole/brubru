"""Phase 3, step 3.4 — measure the predictive LIFT of the new trajectory features.

Honest experiment given the data reality: the carriage universe has ZERO withdrawn/blocked
terminal examples, so a final-outcome classifier has no negative class to learn. The
well-populated, both-classes-present target is procedural ADVANCEMENT:
    advanced = current_status in {ADOPTED, COMPLETED, CLOSE_TO_ADOPTION}   (695)
    early    = current_status in {ANNOUNCED, TABLED}                       (1542)

Two feature arms, 5-fold stratified CV, GradientBoosting, ROC-AUC + PR-AUC:
  BASE   = static metadata only, with every status/age-leaking column EXCLUDED
           (no current_status, days_in_current_status, num_status_changes, days_since_first_seen).
  +TRAJ  = BASE + the Phase-3 trajectory/count features (events velocity/accel/cadence,
           amendments/documents/committee-work/lobby counts).

The delta in CV AUC is the measured lift. Caveats are printed with the result: procedural
activity co-occurs with advancement, so part of the lift is concurrent signal, not pure
forward prediction; the cleaner final-outcome lift needs negative-class data + forward count
accumulation (the daily cron will build that over time).

Run:  python3.12 scripts/measure_trajectory_lift.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logging.disable(logging.INFO)

import numpy as np  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
engine.echo = False
from models.legislative_train import LegislativeCarriage  # noqa: E402
from services.predictions.feature_extractor import FeatureExtractor  # noqa: E402

ADVANCED = {"adopted", "completed", "close_to_adoption"}
EARLY = {"announced", "tabled"}

# status/age leakage — excluded from BOTH arms so lift is attributable to activity, not the label
LEAK = {"days_in_current_status", "num_status_changes", "avg_days_per_status",
        "days_since_first_seen"}
TRAJ = {"snapshot_history_len", "total_procedural_events", "events_last_90d",
        "events_last_180d", "event_acceleration", "avg_days_between_events",
        "days_since_last_event", "num_amendments", "num_commission_documents",
        "num_committee_work", "num_lobby_meetings"}


def _status(c):
    s = c.current_status
    return (getattr(s, "value", s) or "").lower()


def main() -> int:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    db = SessionLocal()
    fx = FeatureExtractor(db=db)
    rows, labels = [], []
    carriages = db.query(LegislativeCarriage).all()
    for c in carriages:
        st = _status(c)
        if st in ADVANCED:
            y = 1
        elif st in EARLY:
            y = 0
        else:
            continue
        f = fx.extract_features(c)
        rows.append(f.get_numeric_features())
        labels.append(y)

    y = np.array(labels)
    keys = sorted({k for r in rows for k in r})
    base_keys = [k for k in keys if k not in LEAK and k not in TRAJ]
    traj_keys = [k for k in keys if k in TRAJ]

    def matrix(cols):
        return np.array([[float(r.get(k, 0.0)) for k in cols] for r in rows])

    # "volume" trajectory features are near-proxies for advancement (more milestones =
    # further along). The stricter arm drops them to isolate whether the DYNAMICS
    # (velocity / acceleration / cadence / recency / counts) add signal beyond raw volume.
    VOLUME = {"total_procedural_events", "snapshot_history_len"}
    dyn_keys = [k for k in traj_keys if k not in VOLUME]

    X_base = matrix(base_keys)
    X_full = matrix(base_keys + traj_keys)
    X_dyn = matrix(base_keys + dyn_keys)

    print(f"samples: {len(y)}  (advanced={int(y.sum())}, early={int((1-y).sum())})")
    print(f"BASE features: {len(base_keys)}   +TRAJ adds: {len(traj_keys)}   +DYN(no-volume) adds: {len(dyn_keys)}")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    def score(X, metric):
        clf = GradientBoostingClassifier(random_state=42)
        return cross_val_score(clf, X, y, cv=cv, scoring=metric)

    for metric in ("roc_auc", "average_precision"):
        b = score(X_base, metric)
        f = score(X_full, metric)
        d = score(X_dyn, metric)
        print(f"\n{metric}:")
        print(f"  BASE            : {b.mean():.4f} +/- {b.std():.4f}")
        print(f"  +TRAJ (all)     : {f.mean():.4f} +/- {f.std():.4f}   lift {f.mean()-b.mean():+.4f}")
        print(f"  +DYN (no-volume): {d.mean():.4f} +/- {d.std():.4f}   lift {d.mean()-b.mean():+.4f}")

    # which trajectory features carry the signal
    clf = GradientBoostingClassifier(random_state=42).fit(X_full, y)
    imp = sorted(zip(base_keys + traj_keys, clf.feature_importances_), key=lambda t: -t[1])
    print("\ntop 12 features by importance (full model):")
    for name, w in imp[:12]:
        tag = " [TRAJ]" if name in TRAJ else ""
        print(f"  {w:.3f}  {name}{tag}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
