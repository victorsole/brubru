"""
De-risk the Predictions demo: call the on-the-fly outcome predictor directly
(no HTTP/auth) for EFPIA priority files and print what it returns, so the live
demo on 28 May 2026 does not flop.

Usage:
    cd backend && python3.12 scripts/verify_efpia_prediction.py
"""

from __future__ import annotations

import asyncio
import logging
import sys

sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru/backend")
sys.path.insert(0, "/Users/victorsole/Documents/GitHub/brubru")

from dotenv import load_dotenv
load_dotenv("/Users/victorsole/Documents/GitHub/brubru/.env")

logging.basicConfig(level=logging.WARNING, format="%(message)s")

REFS = ["2023/0131(COD)", "2023/0132(COD)", "2017/0018(COD)", "2023/0129(COD)"]


async def run():
    from services.predictions import get_outcome_predictor
    predictor = get_outcome_predictor()
    for ref in REFS:
        print("=" * 70)
        print(f"PROCEDURE {ref}")
        try:
            p = await predictor.predict_outcome(ref)
            print(f"  current_status : {p.current_status}")
            print(f"  predicted      : {p.predicted_outcome}  (confidence {p.confidence})")
            for prob in p.probabilities:
                print(f"    - {prob.outcome:<12} {prob.probability}")
            print(f"  model_version  : {p.model_version}")
            tf = p.top_factors
            if tf:
                print(f"  top_factors    : {tf if isinstance(tf, str) else ', '.join(str(x) for x in tf)}")
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(run())
