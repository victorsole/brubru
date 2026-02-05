#!/usr/bin/env python3
"""
Export Training Data - Phase 2.1

Exports labeled training data for ML models from completed procedures.

Output files:
- training_timeline.csv: Features + days_to_next_transition (for timeline prediction)
- training_outcome.csv: Features + final_outcome (for outcome prediction)

Usage:
    python scripts/export_training_data.py
    python scripts/export_training_data.py --output-dir data/ml
    python scripts/export_training_data.py --procedure-type COD --limit 1000
"""

import os
import sys
import csv
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def export_timeline_training_data(
    output_path: str,
    procedure_type: str = None,
    limit: int = None
) -> int:
    """
    Export training data for timeline prediction.

    Each row = one status transition with:
    - All features at the time of transition
    - Label: days spent in that status (actual)

    Returns:
        Number of rows exported
    """
    from models.legislative_train import LegislativeCarriage, CarriageStatusHistory, CarriageStatusEnum
    from services.predictions.feature_extractor import FeatureExtractor

    db = SessionLocal()
    extractor = FeatureExtractor(db)

    try:
        # Query completed procedures with status history
        query = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.current_status.in_([
                CarriageStatusEnum.ADOPTED,
                CarriageStatusEnum.WITHDRAWN,
                CarriageStatusEnum.BLOCKED
            ])
        )

        if procedure_type:
            query = query.filter(
                LegislativeCarriage.oeil_procedure_ref.contains(f"({procedure_type})")
            )

        if limit:
            query = query.limit(limit)

        carriages = query.all()
        logger.info(f"Found {len(carriages)} completed procedures")

        # Prepare CSV
        rows_written = 0

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = None

            for carriage in carriages:
                # Get status history
                history = carriage.status_history or []
                if not history:
                    continue

                # Extract base features
                features = extractor.extract_features(carriage)
                base_dict = features.to_dict()

                # For each status transition, create a training row
                for i, entry in enumerate(history):
                    if not isinstance(entry, dict):
                        continue

                    duration = entry.get('duration_days')
                    if duration is None or duration <= 0:
                        continue

                    status = entry.get('status', 'unknown')

                    # Create row with features + label
                    row = {
                        **base_dict,
                        'training_status': status,
                        'transition_index': i,
                        'total_transitions': len(history),
                        'days_in_status': duration,  # LABEL
                    }

                    # Initialize writer with headers on first row
                    if writer is None:
                        fieldnames = list(row.keys())
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()

                    writer.writerow(row)
                    rows_written += 1

        logger.info(f"Exported {rows_written} training rows to {output_path}")
        return rows_written

    finally:
        extractor.close()
        db.close()


def export_outcome_training_data(
    output_path: str,
    procedure_type: str = None,
    limit: int = None
) -> int:
    """
    Export training data for outcome prediction.

    Each row = one procedure with:
    - All features
    - Label: final outcome (adopted, withdrawn, blocked, amended_significantly)

    Returns:
        Number of rows exported
    """
    from models.legislative_train import LegislativeCarriage, CarriageStatusEnum
    from services.predictions.feature_extractor import FeatureExtractor

    db = SessionLocal()
    extractor = FeatureExtractor(db)

    try:
        # Query completed procedures
        query = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.current_status.in_([
                CarriageStatusEnum.ADOPTED,
                CarriageStatusEnum.WITHDRAWN,
                CarriageStatusEnum.BLOCKED
            ])
        )

        if procedure_type:
            query = query.filter(
                LegislativeCarriage.oeil_procedure_ref.contains(f"({procedure_type})")
            )

        if limit:
            query = query.limit(limit)

        carriages = query.all()
        logger.info(f"Found {len(carriages)} completed procedures")

        # Prepare CSV
        rows_written = 0

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = None

            for carriage in carriages:
                # Extract features
                features = extractor.extract_features(carriage)
                row = features.to_dict()

                # Add outcome label
                status = carriage.current_status
                if hasattr(status, 'value'):
                    status = status.value

                # Map status to outcome class
                outcome = 'adopted'  # default
                if status in ('withdrawn',):
                    outcome = 'withdrawn'
                elif status in ('blocked',):
                    outcome = 'blocked'
                # Note: 'amended_significantly' would require additional data
                # about amendment counts vs original text

                row['outcome'] = outcome  # LABEL

                # Add total procedure duration
                history = carriage.status_history or []
                total_days = sum(
                    entry.get('duration_days', 0)
                    for entry in history
                    if isinstance(entry, dict)
                )
                row['total_procedure_days'] = total_days

                # Initialize writer with headers on first row
                if writer is None:
                    fieldnames = list(row.keys())
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                writer.writerow(row)
                rows_written += 1

        logger.info(f"Exported {rows_written} training rows to {output_path}")
        return rows_written

    finally:
        extractor.close()
        db.close()


def export_feature_statistics(
    output_path: str,
    procedure_type: str = None,
    limit: int = None
):
    """
    Export feature statistics for analysis.
    """
    from models.legislative_train import LegislativeCarriage, CarriageStatusEnum
    from services.predictions.feature_extractor import FeatureExtractor
    import json

    db = SessionLocal()
    extractor = FeatureExtractor(db)

    try:
        # Extract all features
        status_filter = ['adopted', 'withdrawn', 'blocked']
        features_list = extractor.extract_all_features(
            status_filter=status_filter,
            procedure_type_filter=procedure_type,
            limit=limit
        )

        if not features_list:
            logger.warning("No features extracted")
            return

        # Calculate statistics
        stats = extractor.get_feature_statistics(features_list)
        stats['export_timestamp'] = datetime.now().isoformat()
        stats['procedure_type_filter'] = procedure_type
        stats['limit'] = limit

        # Write to JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, default=str)

        logger.info(f"Exported feature statistics to {output_path}")

    finally:
        extractor.close()
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description='Export training data for ML models'
    )
    parser.add_argument(
        '--output-dir',
        default='data/ml',
        help='Output directory for training files'
    )
    parser.add_argument(
        '--procedure-type',
        help='Filter by procedure type (e.g., COD, CNS)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of procedures to export'
    )
    parser.add_argument(
        '--timeline-only',
        action='store_true',
        help='Only export timeline training data'
    )
    parser.add_argument(
        '--outcome-only',
        action='store_true',
        help='Only export outcome training data'
    )
    parser.add_argument(
        '--stats-only',
        action='store_true',
        help='Only export feature statistics'
    )

    args = parser.parse_args()

    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filenames with timestamp
    timestamp = datetime.now().strftime('%Y%m%d')
    suffix = f"_{args.procedure_type}" if args.procedure_type else ""

    timeline_path = output_dir / f"training_timeline{suffix}_{timestamp}.csv"
    outcome_path = output_dir / f"training_outcome{suffix}_{timestamp}.csv"
    stats_path = output_dir / f"feature_stats{suffix}_{timestamp}.json"

    logger.info(f"Output directory: {output_dir}")

    total_rows = 0

    # Export timeline data
    if not args.outcome_only and not args.stats_only:
        logger.info("Exporting timeline training data...")
        rows = export_timeline_training_data(
            str(timeline_path),
            procedure_type=args.procedure_type,
            limit=args.limit
        )
        total_rows += rows

    # Export outcome data
    if not args.timeline_only and not args.stats_only:
        logger.info("Exporting outcome training data...")
        rows = export_outcome_training_data(
            str(outcome_path),
            procedure_type=args.procedure_type,
            limit=args.limit
        )
        total_rows += rows

    # Export statistics
    if not args.timeline_only and not args.outcome_only:
        logger.info("Exporting feature statistics...")
        export_feature_statistics(
            str(stats_path),
            procedure_type=args.procedure_type,
            limit=args.limit
        )

    logger.info(f"[OK] Export complete. Total training rows: {total_rows}")


if __name__ == '__main__':
    main()
