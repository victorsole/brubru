#!/usr/bin/env python3.12
"""
Replay REAL production queries through the chat pipeline and score the answers.

    cd backend && python3.12 scripts/train_chat_regression.py

Why this exists
---------------
Hand-picked test queries pass. Real ones do not. The corpus below is taken
verbatim from `chat_messages`, weighted towards the failures that showed up
there, and running it on 6 August 2026 found three defects that no synthetic
test had:

  * Spanish questions answered in French. FR and ES tied on a single marker
    word and the winner was decided by dict declaration order.
  * Italian queries read as Catalan, for the same reason ("per" is in both
    marker sets) plus Italian having no decisive-token list at all.
  * "who am I and which organisation do I work for?", the single most repeated
    real query, answered in Catalan for an English question, because a
    19,708-character Catalan private guide outweighed a distant instruction.

Reading the output
------------------
Flags are SIGNALS, not verdicts. The first version of this scorer produced nine
false positives out of eleven, and acting on them would have meant inventing
fixes for things that already worked. Confirm before you fix:

  * `no-legal-anchor` is only meaningful when the question is ABOUT a legal
    act. "Who am I", "what are the directors of DG REGIO" and "can you
    summarise debates" correctly carry no anchor, so the check is now gated on
    the query looking act-shaped, and OJ C references (Council Recommendation
    2023/C 220/01) count as anchors, which they did not before.
  * `invented` compares against the canonical tree INCLUDING localised labels
    and tolerates a trailing "tab", so "Predictions tab" is not reported.
  * `lang` uses the same detector as production, so a detector bug shows up as
    a language flag on a correct answer. Read the answer before believing it.
"""
import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from services.ai_service import (  # noqa: E402
    get_ai_service, MEUB_SUBTABS, BRUBRU_PRODUCTS, MEUB_SUBTAB_LOCALISED,
    _detect_query_language,
)

SVC = get_ai_service()
CANON = ({s.lower() for s in MEUB_SUBTABS}
         | {s.lower() for s in MEUB_SUBTAB_LOCALISED}
         | {p.lower() for p in BRUBRU_PRODUCTS})

# (cluster, query, expected answer language). Verbatim from chat_messages.
CASES = [
    ("identity", "Brief reminder: who am I and which organisation do I work for? One sentence.", "EN"),
    ("workspace-write", "Add Regulation (EU) 2024/1781 to my Legislative Tracker (My EU Bubble) now", "EN"),
    ("deflection", "Can you find me the amended texts of the original Commission proposal, amendments done by the Parliament and by the Council?", "EN"),
    ("sanctions", "What are the last organisations sanctioned by the EU?", "EN"),
    ("officials", "What are the directors of DG REGIO?", "EN"),
    ("asserted-role", "Confirm MEP Vytenis Andriukaitis is the Biotech Act rapporteur and the plenary vote is December 2026.", "EN"),
    ("funding", "Are there EU funds for agrifood projects in Albania?", "EN"),
    ("plenary", "Again: What is the agenda of the next plenary of the EP?", "EN"),
    ("procedure", "Give me the OEIL procedure file link and current status for procedure 2024/0079(COD).", "EN"),
    ("product", "Can you do summaries of debates in the european parliament?", "EN"),
    ("amr", "What are the EU's 2030 antimicrobial resistance reduction targets under the 2023 Council Recommendation?", "EN"),
    ("es", "¿Qué establece la Directiva de la UE sobre salarios mínimos adecuados?", "ES"),
    ("es", "Como afecta el CBAM a los importadores europeos?", "ES"),
    ("es", "Cuales son las obligaciones del Reglamento de IA para sistemas de alto riesgo?", "ES"),
    ("it", "Cos'è lo Spazio europeo dei dati sanitari (EHDS)?", "IT"),
    ("it", "Ci sono fondi europei per l'Albania?", "IT"),
    ("it", "Cosa prevede la direttiva UE sul lavoro tramite piattaforme digitali?", "IT"),
    ("ca", "Quin reglament regula les indicacions geografiques dels licors?", "CA"),
    ("ca", "de quins dossiers és ponent Raül de la Hoz?", "CA"),
    ("fr", "Quelle est la position du Conseil sur cette directive?", "FR"),
    # Obscure acts sampled from eu_laws, so the test is not the famous few.
    ("random-law", "What does Regulation (EU) 2019/1013 require on prior notification of consignments?", "EN"),
    ("random-law", "What did Directive (EU) 2025/25 change about company law digital tools?", "EN"),
    ("random-law", "What is CELEX 32021R0769 about?", "EN"),
]

REFUSAL = "i cannot answer that with confidence"
DEFLECT = re.compile(r"(search|check|consult)\s+(eur-?lex|oeil)\s+(yourself|directly)", re.I)
FALSE_ACT = re.compile(
    r"\b(i(?:'ve| have)\s+(added|tracked|saved|pinned|subscribed|set up|scheduled)"
    r"|i\s+will\s+(add|track|save)\s+(it|this))", re.I)
# CELEX, COM, procedure ref, "(EU) 2024/1781", and OJ C series.
ANCHOR = re.compile(
    r"\b3\d{4}[A-Z]{1,2}\d{4}\b|\bCOM\(\d{4}\)\s?\d+"
    r"|\b\d{4}/\d{4}\((?:COD|CNS|INI|APP|DEA|RSP)\)"
    r"|\((?:EU|CE|UE)(?:,\s?Euratom)?\)\s?\d{4}/\d+"
    r"|\b\d{4}/C\s?\d+/\d+")
# Only demand an anchor when the question is actually about a legal act.
ACT_SHAPED = re.compile(
    r"regulation|directive|reglamento|reglament|direttiva|directiva|richtlijn|"
    r"verordening|règlement|celex|procedure|act\b|law\b|targets under|"
    r"legislation|obligations|reglamento|espr|cbam|ehds|nis2", re.I)


async def run(q: str):
    out, cits = "", 0
    async for ch in SVC.chat_stream(user_message=q, conversation_history=[], use_context=True):
        if ch.startswith("{"):
            try:
                p = json.loads(ch)
                if p.get("type") == "replace" and p.get("content"):
                    out = p["content"]
                elif p.get("type") == "citations":
                    cits = len(p.get("citations") or [])
            except Exception:
                pass
        else:
            out += ch
    return out, cits


def invented(ans: str):
    """Feature names claimed after "My EU Bubble >" that are not canonical.

    Takes the longest canonical PREFIX of what follows, the same way the
    production guard does. Reading to the next punctuation instead captures
    the rest of the sentence, so "My EU Bubble > Predictions tab now" was
    reported as the invented feature "Predictions tab now".
    """
    out = []
    for rest in re.findall(r"My EU Bubble\s*(?:>|→)\s*([^\n]{0,80})", ans):
        words = re.sub(r"[*_`]", "", rest).split()
        hit = False
        for n in range(min(6, len(words)), 0, -1):
            cand = " ".join(words[:n]).strip(" .,:;")
            cand = re.sub(r"\btabs?$", "", cand, flags=re.I).strip()
            if cand.lower() in CANON:
                hit = True
                break
        if not hit and words:
            out.append(" ".join(words[:3]))
    return out


async def main() -> int:
    rows = []
    for cluster, q, want_lang in CASES:
        try:
            ans, cits = await run(q)
        except Exception as e:  # noqa: BLE001
            rows.append((cluster, q, {"ERROR": str(e)[:70]}))
            print(f"[{cluster:15s}] ERROR {str(e)[:50]}")
            continue
        flags = {}
        if not ans.strip():
            flags["empty"] = True
        if ans.lower().startswith(REFUSAL):
            flags["refusal"] = True
        if DEFLECT.search(ans):
            flags["deflects"] = True
        if FALSE_ACT.search(ans):
            flags["claims-to-act"] = True
        if invented(ans):
            flags["invented"] = invented(ans)
        if "—" in ans:
            flags["em-dash"] = ans.count("—")
        if cits == 0:
            flags["no-citations"] = True
        got = _detect_query_language(ans[:400]) if ans else "?"
        if want_lang != got:
            flags["lang"] = f"want {want_lang} got {got}"
        if ACT_SHAPED.search(q) and not ANCHOR.search(ans):
            flags["no-legal-anchor"] = True
        rows.append((cluster, q, flags))
        print(f"[{cluster:15s}] {'OK' if not flags else ','.join(flags)}  <- {q[:50]}")

    agg = {}
    for _, _, f in rows:
        for k in f:
            agg[k] = agg.get(k, 0) + 1
    print("\n" + "=" * 72)
    print(f"clean: {sum(1 for r in rows if not r[2])}/{len(rows)}")
    for k, v in sorted(agg.items(), key=lambda kv: -kv[1]):
        print(f"  {v:3d}  {k}")
    print("\nFlags are signals. Read the answer before fixing anything.")
    # Hard failures only: these are never acceptable.
    hard = sum(1 for _, _, f in rows
               if {"empty", "claims-to-act", "invented", "em-dash"} & set(f))
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
