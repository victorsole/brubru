"""
End-to-end JWT verifier for onboarded private-guide users.

Mints a JWT server-side (same SECRET_KEY + HS256 + {sub, email} shape as
api/auth.py::create_access_token), hits production /api/chat/message with
the bearer header and NO user_id in the body, and looks for an
organisation-specific token in the response.

  Pass  = answer cites a token from the user's private guide -> guide reached chat context
  Fail  = answer is generic / does not mention the expected org token

Bypasses the password gate (works for OAuth-only users like David) and the
form-encoded login flow that needs scrypt access.

Usage:
    cd backend && python3.12 scripts/verify_jwt_chat_path.py             # dry-run (mint + decode locally)
    cd backend && python3.12 scripts/verify_jwt_chat_path.py --probe     # hit production /api/chat/message

NOTE: --probe sends 10 real chat calls to production. ~$0.50 in model cost.
"""

from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import argparse
import json
import logging
import sys
import time
from datetime import datetime, timedelta

import jwt
import requests

sys.path.insert(0, f"{_REPO_ROOT}/backend")
sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv
load_dotenv(f"{_REPO_ROOT}/.env")

from sqlalchemy import text
from core.database import SessionLocal, engine
from core.config import settings

engine.echo = False
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
for noisy in ("sqlalchemy.engine", "sqlalchemy.engine.Engine", "sqlalchemy.pool", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


API_BASE = "https://brubru-production.up.railway.app"
ALGORITHM = "HS256"
SECRET_KEY = settings.SECRET_KEY


# Expected org-tokens per user. Case-insensitive substring match against the chat reply.
# At least ONE of the listed tokens must appear in the answer for the row to PASS.
EXPECTED = {
    "jmp@bassons.eu":                 ["ACM", "Catalonia", "Bassons", "Piqu"],
    "fernandez@taseuro.com":          ["TAS", "Europrojects"],
    "bernis@taseuro.com":             ["TAS", "Europrojects", "Bernis"],
    "secretariat@ferrmed.com":        ["FerrMed"],
    "bureau@ferrmed.com":             ["FerrMed"],
    "guidomariavalletta@gmail.com":   ["Valletta", "Guido"],
    "j.gonzalez@bepassociation.eu":   ["BEPA", "Clerens", "Gonz"],
    "margapayola@gmail.com":          ["Payola", "Marga"],
    "sustainability@beuc.eu":         ["BEUC"],
    "david.devantcerezo@efpia.eu":    ["EFPIA", "Devant"],
}

UNIVERSAL_PROBE = (
    "Brief reminder: who am I and which organisation do I work for? "
    "One sentence."
)


def mint_token(user_id: str, email: str, hours: int = 1) -> str:
    """Produce a JWT the backend will accept identically to a login-issued one."""
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=hours),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def probe_chat(token: str, message: str, timeout: int = 60) -> dict:
    """POST to /api/chat/message with bearer token and NO user_id in body."""
    url = f"{API_BASE}/api/chat/message"
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"message": message},
        timeout=timeout,
    )
    out = {"status": resp.status_code, "raw": resp.text[:2000]}
    try:
        out["json"] = resp.json()
    except Exception:
        out["json"] = None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true",
                    help="Hit production /api/chat/message for each user (default: dry-run only)")
    args = ap.parse_args()

    logger.info("=" * 78)
    logger.info(f"JWT verifier - {'PROBE (10 prod chat calls)' if args.probe else 'DRY-RUN (mint+decode only)'}")
    logger.info("=" * 78)

    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT id::text AS uid, email, private_guide_slug AS slug, subscription_tier AS tier
            FROM users
            WHERE private_guide_slug IS NOT NULL
            ORDER BY email
        """)).mappings().all()
    finally:
        db.close()

    logger.info(f"  [users] {len(rows)} profiles with private_guide_slug")
    logger.info("")

    results = []
    for r in rows:
        email = r["email"]
        uid = r["uid"]
        slug = r["slug"]
        tier = r["tier"]

        token = mint_token(uid, email)
        # Confirm the token decodes locally with the same key/algorithm the backend uses.
        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            decode_ok = decoded.get("sub") == uid
        except Exception as e:
            decode_ok = False
            logger.info(f"  [decode] {email}: FAILED ({e})")

        row = {
            "email": email,
            "uid_short": uid[:8],
            "slug": slug,
            "tier": tier,
            "decode_ok": decode_ok,
            "probe_status": None,
            "probe_pass": None,
            "answer_excerpt": None,
        }

        if args.probe:
            logger.info(f"  [probe] {email:<40} ...")
            try:
                out = probe_chat(token, UNIVERSAL_PROBE)
                row["probe_status"] = out["status"]
                answer = None
                if out["json"]:
                    answer = (out["json"].get("message")
                              or out["json"].get("response")
                              or out["json"].get("answer"))
                if not answer:
                    answer = out["raw"][:400]
                row["answer_excerpt"] = (answer or "")[:300]

                if out["status"] == 200 and answer:
                    expected_tokens = EXPECTED.get(email, [])
                    hit = any(t.lower() in answer.lower() for t in expected_tokens)
                    row["probe_pass"] = hit
                else:
                    row["probe_pass"] = False
            except requests.exceptions.RequestException as e:
                row["probe_status"] = "EXC"
                row["probe_pass"] = False
                row["answer_excerpt"] = str(e)[:300]

            time.sleep(1.5)  # gentle pacing - production

        results.append(row)

    logger.info("")
    logger.info("-" * 78)
    logger.info("SUMMARY")
    logger.info("-" * 78)
    header = f"  {'email':<40} {'tier':<6} {'slug':<24} {'mint':<5} {'http':<6} {'pass':<5}"
    logger.info(header)
    for r in results:
        mint = "ok" if r["decode_ok"] else "BAD"
        http = str(r["probe_status"]) if args.probe else "-"
        passed = ("PASS" if r["probe_pass"] else "FAIL") if args.probe else "-"
        logger.info(f"  {r['email']:<40} {r['tier']:<6} {r['slug']:<24} {mint:<5} {http:<6} {passed:<5}")

    if args.probe:
        logger.info("")
        logger.info("-" * 78)
        logger.info("RESPONSE EXCERPTS (first 300 chars)")
        logger.info("-" * 78)
        for r in results:
            logger.info(f"\n  [{r['email']}] -> {('PASS' if r['probe_pass'] else 'FAIL')}")
            logger.info(f"    expected one of: {EXPECTED.get(r['email'], [])}")
            logger.info(f"    answer: {r['answer_excerpt']}")

    n_pass = sum(1 for r in results if r["probe_pass"])
    n_fail = sum(1 for r in results if r["probe_pass"] is False)
    logger.info("")
    if args.probe:
        logger.info(f"  [TOTAL] {n_pass} PASS / {n_fail} FAIL out of {len(results)}")
    else:
        logger.info(f"  [TOTAL] {len(results)} JWTs minted + decoded locally. Re-run with --probe to hit production.")


if __name__ == "__main__":
    main()
