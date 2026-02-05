#!/usr/bin/env python3
"""
Check Timeline Predictions - Phase 1.4

Shows stagnation alerts and timeline predictions for legislative procedures.

Usage:
    python scripts/check_timeline_predictions.py                    # Show stagnation alerts
    python scripts/check_timeline_predictions.py --stats            # Show historical stats
    python scripts/check_timeline_predictions.py --predict REF      # Predict timeline for procedure
    python scripts/check_timeline_predictions.py -v                 # Verbose output

Examples:
    # Check for stagnating procedures
    python scripts/check_timeline_predictions.py

    # Get timeline prediction for a specific procedure
    python scripts/check_timeline_predictions.py --predict "2024/0138(COD)"

    # Show historical timeline statistics
    python scripts/check_timeline_predictions.py --stats --type COD
"""

import asyncio
import argparse
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.predictions.timeline_predictor import (
    TimelinePredictor,
    StagnationLevel
)


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )


def level_emoji(level: StagnationLevel) -> str:
    """Get indicator for stagnation level."""
    if level == StagnationLevel.CRITICAL:
        return "[!!!]"
    elif level == StagnationLevel.ALERT:
        return "[!!]"
    elif level == StagnationLevel.WARNING:
        return "[!]"
    return ""


async def show_stagnation_alerts(predictor: TimelinePredictor, min_level: str, limit: int):
    """Display stagnation alerts."""
    print("=" * 70)
    print("STAGNATION ALERTS - Procedures Stuck Too Long")
    print("=" * 70)
    print()

    level_map = {
        "warning": StagnationLevel.WARNING,
        "alert": StagnationLevel.ALERT,
        "critical": StagnationLevel.CRITICAL
    }

    alerts = await predictor.get_stagnation_alerts(
        min_level=level_map.get(min_level, StagnationLevel.WARNING),
        limit=limit
    )

    if not alerts:
        print("No stagnation alerts found.")
        print("(This may mean the database is empty or all procedures are progressing normally)")
        return

    print(f"Found {len(alerts)} stagnating procedures:\n")

    for alert in alerts:
        indicator = level_emoji(alert.level)
        print(f"{indicator} {alert.procedure_ref}")
        print(f"    Title: {alert.title[:60]}...")
        print(f"    Status: {alert.current_status}")
        print(f"    Days in status: {alert.days_in_status} ({alert.days_in_status // 30} months)")
        print(f"    Level: {alert.level.value.upper()}")
        print()


async def show_historical_stats(predictor: TimelinePredictor, proc_type: str):
    """Display historical timeline statistics."""
    print("=" * 70)
    print(f"HISTORICAL TIMELINE STATISTICS ({proc_type or 'All Types'})")
    print("=" * 70)
    print()

    summary = await predictor.get_timeline_summary(proc_type)

    if "error" in summary:
        print(f"Error: {summary['error']}")
        print("(This may mean the database lacks status history data)")
        return

    print(f"Procedure type: {summary['procedure_type']}")
    print(f"Total transitions tracked: {summary['total_transitions']}")
    print()

    if summary["transitions"]:
        print(f"{'Transition':<30} {'Avg Days':>10} {'Median':>10} {'Range':>15} {'Samples':>10}")
        print("-" * 75)

        for t in summary["transitions"][:15]:  # Top 15
            transition = f"{t['from']} -> {t['to']}"
            print(f"{transition:<30} {t['avg_days']:>10.1f} {t['median_days']:>10.1f} "
                  f"{t['range']:>15} {t['sample_size']:>10}")
    else:
        print("No transition statistics available.")


async def show_prediction(predictor: TimelinePredictor, procedure_ref: str):
    """Display timeline prediction for a procedure."""
    print("=" * 70)
    print(f"TIMELINE PREDICTION: {procedure_ref}")
    print("=" * 70)
    print()

    prediction = await predictor.predict_timeline(procedure_ref)

    if not prediction:
        print(f"Procedure not found: {procedure_ref}")
        return

    print(f"Current status: {prediction.current_status}")
    print(f"Days in status: {prediction.days_in_status}")
    print()

    if prediction.predicted_days_remaining is not None:
        print(f"Predicted days remaining: {prediction.predicted_days_remaining}")
        print(f"Confidence: {prediction.confidence:.1%}")
        print(f"Based on: {prediction.based_on}")
    else:
        print("Unable to make prediction (insufficient data)")

    if prediction.similar_procedures:
        print("\nSimilar completed procedures:")
        for p in prediction.similar_procedures:
            print(f"  - {p['procedure_ref']}: {p['title'][:50]}...")
            print(f"    Similarity: {p['similarity']:.1%}, Status: {p['final_status']}")

    if prediction.historical_stats:
        stats = prediction.historical_stats
        print(f"\nHistorical stats for {stats.from_status} stage:")
        print(f"  Average duration: {stats.avg_days:.1f} days")
        print(f"  Range: {stats.min_days}-{stats.max_days} days")
        print(f"  Sample size: {stats.sample_size}")


async def main():
    parser = argparse.ArgumentParser(
        description="Check timeline predictions for legislative procedures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show historical timeline statistics"
    )

    parser.add_argument(
        "--type",
        type=str,
        default=None,
        help="Filter by procedure type (COD, CNS, etc.)"
    )

    parser.add_argument(
        "--predict",
        type=str,
        default=None,
        metavar="PROCEDURE_REF",
        help="Predict timeline for a specific procedure"
    )

    parser.add_argument(
        "--level",
        type=str,
        choices=["warning", "alert", "critical"],
        default="warning",
        help="Minimum stagnation level for alerts (default: warning)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results (default: 20)"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)

    predictor = TimelinePredictor()

    try:
        if args.predict:
            await show_prediction(predictor, args.predict)
        elif args.stats:
            await show_historical_stats(predictor, args.type)
        else:
            await show_stagnation_alerts(predictor, args.level, args.limit)

    finally:
        predictor.close()


if __name__ == "__main__":
    asyncio.run(main())
