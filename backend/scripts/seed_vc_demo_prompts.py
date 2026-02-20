"""
Seed VC Demo Example Prompts

Creates three sets of example chat prompts tailored to each VC fund context:
  - a16z Speedrun: AI/crypto focus, gaming DNA, "can you ship fast?" mentality
  - Y Combinator: GovTech/RegTech focus, Tom Blomfield's AI-for-Government RFS
  - Start it @KBC: Belgian banking/insurance focus, KBC as potential design partner

Each set uses scope='vc_demo_{fund}' so they can be activated per demo.
A 'vc_demo_general' scope contains prompts that work for any fund.

Usage:
    python -m backend.scripts.seed_vc_demo_prompts
    python -m backend.scripts.seed_vc_demo_prompts --delete   # remove all VC demo prompts
"""

import sys
import os

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from sqlalchemy.orm import Session
from core.database import SessionLocal
from models.chat_example_prompt import ChatExamplePrompt
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================================================================
# VC Demo Prompt Sets
# =====================================================================

VC_DEMO_SCOPES = ["vc_demo_speedrun", "vc_demo_yc", "vc_demo_kbc", "vc_demo_general"]

# -- General prompts (work for any fund demo) -------------------------
GENERAL_PROMPTS = [
    {
        "text": "What EU regulations affect financial institutions in 2025-2026?",
        "scope": "vc_demo_general",
        "sort_order": 0,
    },
    {
        "text": "Summarise the AI Act's impact on the financial sector",
        "scope": "vc_demo_general",
        "sort_order": 1,
    },
    {
        "text": "Which EU legislative proposals are currently in trilogue?",
        "scope": "vc_demo_general",
        "sort_order": 2,
    },
    {
        "text": "Draft talking points on DORA compliance for a fund board meeting",
        "scope": "vc_demo_general",
        "sort_order": 3,
    },
]

# -- a16z Speedrun: AI/crypto, gaming DNA, speed -------------------
SPEEDRUN_PROMPTS = [
    {
        "text": "How does MiCA regulate crypto-asset service providers in the EU?",
        "scope": "vc_demo_speedrun",
        "sort_order": 0,
    },
    {
        "text": "Compare EU and US approaches to stablecoin regulation",
        "scope": "vc_demo_speedrun",
        "sort_order": 1,
    },
    {
        "text": "What are DORA's requirements for ICT third-party risk management?",
        "scope": "vc_demo_speedrun",
        "sort_order": 2,
    },
    {
        "text": "Draft a position paper on AI Act Article 6 high-risk classification for fintech",
        "scope": "vc_demo_speedrun",
        "sort_order": 3,
    },
]

# -- Y Combinator: GovTech, AI-for-Government, RegTech -------------
YC_PROMPTS = [
    {
        "text": "What is SFDR 2.0 and how does it change ESG disclosure for asset managers?",
        "scope": "vc_demo_yc",
        "sort_order": 0,
    },
    {
        "text": "Generate a gap analysis: DORA compliance for a mid-size investment fund",
        "scope": "vc_demo_yc",
        "sort_order": 1,
    },
    {
        "text": "Which EP committees are working on financial regulation right now?",
        "scope": "vc_demo_yc",
        "sort_order": 2,
    },
    {
        "text": "Explain the AIFMD II national transposition timeline and what it means for fund managers",
        "scope": "vc_demo_yc",
        "sort_order": 3,
    },
]

# -- Start it @KBC: Belgian banking, insurance, KBC as partner -----
KBC_PROMPTS = [
    {
        "text": "What EU regulations affect Belgian banks and insurers in 2025?",
        "scope": "vc_demo_kbc",
        "sort_order": 0,
    },
    {
        "text": "Summarise DORA's incident reporting requirements for credit institutions",
        "scope": "vc_demo_kbc",
        "sort_order": 1,
    },
    {
        "text": "How does PSD3 change the payments landscape for European banks?",
        "scope": "vc_demo_kbc",
        "sort_order": 2,
    },
    {
        "text": "Draft an amendment to Article 18 of DORA on digital operational resilience testing",
        "scope": "vc_demo_kbc",
        "sort_order": 3,
    },
]

ALL_PROMPT_SETS = GENERAL_PROMPTS + SPEEDRUN_PROMPTS + YC_PROMPTS + KBC_PROMPTS


def seed_vc_demo_prompts(db: Session) -> dict:
    """Insert VC demo example prompts into the database."""
    stats = {"created": 0, "skipped": 0}

    for prompt_data in ALL_PROMPT_SETS:
        # Check if prompt already exists (by text + scope)
        existing = (
            db.query(ChatExamplePrompt)
            .filter(
                ChatExamplePrompt.text == prompt_data["text"],
                ChatExamplePrompt.scope == prompt_data["scope"],
            )
            .first()
        )

        if existing:
            logger.info(f"[SKIP] Already exists: {prompt_data['text'][:60]}...")
            stats["skipped"] += 1
            continue

        prompt = ChatExamplePrompt(
            text=prompt_data["text"],
            locale="en",
            scope=prompt_data["scope"],
            subscription_tiers=None,  # visible to all tiers during demo
            is_active=True,
            sort_order=prompt_data["sort_order"],
        )
        db.add(prompt)
        stats["created"] += 1
        logger.info(f"[OK] Created: [{prompt_data['scope']}] {prompt_data['text'][:60]}...")

    db.commit()
    return stats


def delete_vc_demo_prompts(db: Session) -> int:
    """Remove all VC demo prompts."""
    count = (
        db.query(ChatExamplePrompt)
        .filter(ChatExamplePrompt.scope.in_(VC_DEMO_SCOPES))
        .delete(synchronize_session=False)
    )
    db.commit()
    return count


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed VC demo example prompts")
    parser.add_argument("--delete", action="store_true", help="Delete all VC demo prompts")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.delete:
            count = delete_vc_demo_prompts(db)
            logger.info(f"[OK] Deleted {count} VC demo prompts")
        else:
            stats = seed_vc_demo_prompts(db)
            logger.info(f"[OK] Seeded VC demo prompts: {stats}")
            logger.info(f"")
            logger.info(f"To use in the chat interface, fetch with scope parameter:")
            logger.info(f"  GET /api/chat/examples?scope=vc_demo_speedrun")
            logger.info(f"  GET /api/chat/examples?scope=vc_demo_yc")
            logger.info(f"  GET /api/chat/examples?scope=vc_demo_kbc")
            logger.info(f"  GET /api/chat/examples?scope=vc_demo_general")
    finally:
        db.close()


if __name__ == "__main__":
    main()
