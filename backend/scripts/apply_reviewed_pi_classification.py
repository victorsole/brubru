"""Apply reviewed PI labels to the carriages that are active this week but unclassified.

Every label is READ off the title and validated against the canonical closed set already in
use. Where the keyword classifier fired wrongly, the reviewed label overrides it; the
override and its reason are printed so the diff is auditable. Idempotent: only fills rows
whose policy_areas is still empty.
"""
import argparse, logging, sys
from pathlib import Path
# Derive the root from this file, never a hardcoded absolute path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
logging.disable(logging.WARNING)
from sqlalchemy import text
from core.database import SessionLocal, engine
engine.echo = False

# procedure -> (labels, note). "keyword classifier" = accepted as returned.
REVIEWED = {
 '2023/0437(COD)':  (['Transport','Consumer Protection'],
                     "classifier gave Transport only; 261/2004 passenger rights is also consumer protection"),
 '2025/0162(NLE)':  (['Foreign and Security Policy','Single Market'],
                     "OVERRIDE: classifier added Defence, Human Rights and Neighbourhood+Enlargement to an "
                     "EU-Switzerland bilateral package. Switzerland is not an enlargement candidate and the "
                     "package is single-market participation"),
 '2025/0162R(NLE)': (['Foreign and Security Policy','Single Market'], "same file, interim report"),
 '2025/0237(COD)':  (['Agriculture'], "keyword classifier: school fruit, vegetables and milk scheme"),
 '2025/0361(COD)':  (['Economic and Financial Affairs'], "keyword classifier: SFDR disclosures"),
 '2025/0362(COD)':  (['Economic and Financial Affairs','Employment and Social Affairs'],
                     "OVERRIDE: classifier added Competition, Statistics and Taxation to an occupational "
                     "pensions file (IORP II / IDD)"),
 '2025/0363(COD)':  (['Employment and Social Affairs','Economic and Financial Affairs'],
                     "classifier gave Employment only; PEPP is a regulated financial product"),
 '2025/0381(COD)':  (['Economic and Financial Affairs'], "keyword classifier: settlement finality"),
 '2025/2117(INI)':  (['Foreign and Security Policy'], "keyword classifier: EU-China political relations"),
 '2026/2025(INI)':  (['Defence and Security'], "keyword classifier: defence actors scale-up"),
 '2026/2816(RSP)':  (['Climate Action','Environment'],
                     "OVERRIDE: classifier said Customs. The file is an objection on hydrofluorocarbon "
                     "reference values under the F-gas Regulation 2024/573; 'importer'/'placed on the market' "
                     "triggered the customs keywords"),
 '2026/2817(RSP)':  (['Climate Action'], "keyword classifier: ETS free-allocation benchmarks"),
}

# --- second batch, 7 September 2026: the five Migration and Asylum Pact carriages
# created by backfill_carriages_from_emeeting.py in the same session. The keyword
# classifier's output was reviewed and accepted for four of five.
REVIEWED.update({
 '2016/0132(COD)': (['Justice and Fundamental Rights','Migration and Home Affairs'],
                    "keyword classifier, accepted: Eurodac Regulation, LIBE-led biometric database"),
 '2016/0222(COD)': (['Justice and Fundamental Rights','Migration and Home Affairs'],
                    "keyword classifier, accepted: Reception Conditions Directive"),
 '2020/0277(COD)': (['Justice and Fundamental Rights','Migration and Home Affairs'],
                    "keyword classifier, accepted: Crisis and force majeure Regulation"),
 '2020/0278(COD)': (['Justice and Fundamental Rights','Migration and Home Affairs'],
                    "keyword classifier, accepted: Screening Regulation"),
 '2020/0279(COD)': (['Justice and Fundamental Rights','Migration and Home Affairs'],
                    "classifier returned Migration only; Justice added for PACKAGE CONSISTENCY. "
                    "Its four Migration and Asylum Pact siblings all carry Justice and Fundamental "
                    "Rights, and a user filtering on Justice would otherwise get four of the five "
                    "files of one package, which is worse than all or none"),
})

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--apply',action='store_true'); a=ap.parse_args()
    db=SessionLocal()
    canon={r[0] for r in db.execute(text("SELECT DISTINCT unnest(policy_areas) FROM legislative_carriages"))}
    bad={l for labs,_ in REVIEWED.values() for l in labs if l not in canon}
    if bad:
        print("[ABORT] labels outside the canonical set:", bad); sys.exit(1)
    print(f"[OK] all {sum(len(v[0]) for v in REVIEWED.values())} labels are in the canonical {len(canon)}-label set\n")
    filled=skipped=0
    for ref,(labs,note) in REVIEWED.items():
        rows=db.execute(text("""SELECT id, policy_areas FROM legislative_carriages
             WHERE oeil_procedure_ref=:r"""),{'r':ref}).fetchall()
        for rid,cur in rows:
            if cur:   # never overwrite an existing classification
                print(f"  SKIP  {ref:<18} already has {cur}"); skipped+=1; continue
            print(f"  {'APPLY' if a.apply else 'DRY  '} {ref:<18} -> {labs}")
            print(f"          why: {note}")
            if a.apply:
                db.execute(text("UPDATE legislative_carriages SET policy_areas=:p WHERE id=:i"),
                           {'p':labs,'i':rid})
            filled+=1
    if a.apply: db.commit()
    print(f"\n{'APPLIED' if a.apply else 'DRY-RUN'}: {filled} row(s) would be filled, {skipped} skipped as already classified")
    db.close()

main()
