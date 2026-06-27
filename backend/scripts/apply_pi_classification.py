"""Apply the semantic PI classification of the 633 unclassified carriages.

Each index maps to one canonical PI label (or XX = genuinely horizontal/institutional or
an unidentifiable CELEX-only corrigendum -> left unclassified, honest). Labels are validated
against the closed 34-label set before writing. Idempotent: only fills rows still empty.

Run:  python3.12 scripts/apply_pi_classification.py            # dry-run
      python3.12 scripts/apply_pi_classification.py --apply
"""
from __future__ import annotations
import argparse, json, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
logging.disable(logging.INFO)
from sqlalchemy import text
from core.database import SessionLocal, engine
engine.echo = False

SCR = "/private/tmp/claude-501/-Users-victorsole-Documents-GitHub-brubru/467dde5d-b102-4717-9258-3805a4ea37f8/scratchpad/pi_classify/unclassified.json"

C = {
 "AG":"Agriculture","BI":"Business and Industry","CA":"Climate Action",
 "CN":"Communication Networks, Content and Technology","CO":"Competition",
 "CP":"Consumer Protection","CU":"Culture","CT":"Customs","DS":"Defence and Security",
 "DC":"Development and Cooperation","DE":"Digital Policy and Digital Economy",
 "EF":"Economic and Financial Affairs","ED":"Education, Training and Youth",
 "EM":"Employment and Social Affairs","EN":"Energy","EV":"Environment","FS":"Food Safety",
 "FP":"Foreign and Security Policy","HE":"Health","HR":"Human Rights and Democracy",
 "HA":"Humanitarian Aid and Civil Protection","JU":"Justice and Fundamental Rights",
 "MA":"Maritime Affairs and Fisheries","MH":"Migration and Home Affairs",
 "NE":"Neighbourhood and Enlargement","RP":"Regional Policy","RI":"Research and Innovation",
 "SM":"Single Market","SP":"Space Policy","ST":"Statistics","TX":"Taxation",
 "TE":"Trade and Economic Security","TR":"Transport","WR":"Women's Rights and Gender Equality",
}

M = {
0:"RP",1:"HE",2:"EF",3:"EF",4:"EF",5:"EN",6:"XX",7:"MH",8:"FP",9:"EF",10:"XX",11:"HR",12:"XX",
13:"MH",14:"EF",15:"FP",16:"FP",17:"XX",18:"RP",19:"FP",20:"XX",21:"FP",22:"RP",23:"EF",24:"HR",
25:"FP",26:"MH",27:"FP",28:"XX",29:"XX",30:"FP",31:"DE",32:"EV",33:"FP",34:"EF",35:"XX",36:"JU",
37:"FP",38:"EF",39:"EF",40:"FP",41:"EF",42:"EF",43:"MH",44:"EF",45:"FP",46:"EF",47:"SM",48:"DE",
49:"XX",50:"MH",51:"EF",52:"EF",53:"EF",54:"JU",55:"HR",56:"FP",57:"EM",58:"SM",59:"EF",60:"MH",
61:"MH",62:"FP",63:"XX",64:"EF",65:"EF",66:"HR",67:"HE",68:"FS",69:"EF",70:"FP",71:"DE",72:"CP",
73:"BI",74:"TR",75:"FP",76:"FP",77:"EF",78:"MA",79:"EF",80:"EF",81:"EF",82:"MH",83:"EF",84:"EF",
85:"EF",86:"HA",87:"FP",88:"EF",89:"XX",90:"ST",91:"XX",92:"SM",93:"EF",94:"EF",95:"EF",96:"CP",
97:"EF",98:"AG",99:"SM",100:"MH",101:"RP",102:"TR",103:"EM",104:"BI",105:"TR",106:"XX",107:"XX",
108:"FP",109:"TE",110:"EF",111:"EF",112:"BI",113:"SM",114:"HE",115:"TE",116:"XX",117:"XX",118:"JU",
119:"EN",120:"EF",121:"XX",122:"EV",123:"MH",124:"XX",125:"TX",126:"HA",127:"EM",128:"EF",129:"EF",
130:"EF",131:"RP",132:"HA",133:"JU",134:"EF",135:"MH",136:"EF",137:"EF",138:"FP",139:"SM",140:"XX",
141:"XX",142:"MH",143:"SM",144:"EF",145:"DC",146:"FP",147:"JU",148:"EF",149:"DE",150:"EM",151:"EF",
152:"JU",153:"FP",154:"EF",155:"EF",156:"EF",157:"FP",158:"XX",159:"FP",160:"MH",161:"XX",162:"EN",
163:"BI",164:"EN",165:"MH",166:"FP",167:"AG",168:"JU",169:"SM",170:"JU",171:"EF",172:"EF",173:"EF",
174:"EF",175:"HR",176:"JU",177:"EM",178:"EF",179:"FP",180:"RP",181:"RP",182:"XX",183:"RP",184:"HE",
185:"TE",186:"TR",187:"MA",188:"XX",189:"FP",190:"EF",191:"DE",192:"HR",193:"EV",194:"MA",195:"EF",
196:"EF",197:"CP",198:"HE",199:"EM",200:"XX",201:"HE",202:"EF",203:"CU",204:"CN",205:"TR",206:"SM",
207:"TX",208:"EF",209:"EF",210:"EF",211:"EF",212:"EF",213:"EF",214:"XX",215:"HE",216:"ED",217:"EF",
218:"SM",219:"XX",220:"EF",221:"FP",222:"FP",223:"EF",224:"XX",225:"FP",226:"EF",227:"JU",228:"SM",
229:"CP",230:"HE",231:"EF",232:"SM",233:"XX",234:"JU",235:"EF",236:"TR",237:"AG",238:"DS",239:"JU",
240:"EF",241:"FP",242:"FP",243:"MH",244:"EF",245:"EF",246:"MA",247:"EF",248:"EF",249:"MH",250:"EF",
251:"HR",252:"EF",253:"CA",254:"EF",255:"BI",256:"EF",257:"EF",258:"EF",259:"FP",260:"EF",261:"FP",
262:"EN",263:"EF",264:"EF",265:"EF",266:"BI",267:"BI",268:"HR",269:"TR",270:"FP",271:"FP",272:"EF",
273:"FP",274:"FP",275:"EF",276:"HR",277:"EF",278:"JU",279:"FP",280:"EF",281:"BI",282:"EF",283:"HE",
284:"EF",285:"EF",286:"JU",287:"TR",288:"EN",289:"JU",290:"ST",291:"BI",292:"JU",293:"FP",294:"DS",
295:"DE",296:"DE",297:"JU",298:"EF",299:"EF",300:"SM",301:"XX",302:"EM",303:"HR",304:"MH",305:"CA",
306:"TE",307:"ED",308:"EF",309:"EF",310:"HR",311:"EF",312:"EF",313:"MH",314:"EF",315:"TE",316:"FS",
317:"MH",318:"CP",319:"EF",320:"EF",321:"EF",322:"EF",323:"XX",324:"EF",325:"JU",326:"XX",327:"XX",
328:"HR",329:"EF",330:"JU",331:"FP",332:"EF",333:"HR",334:"EF",335:"EF",336:"EF",337:"XX",338:"SM",
339:"EF",340:"FP",341:"EF",342:"AG",343:"TR",344:"XX",345:"EF",346:"JU",347:"HR",348:"EF",349:"CN",
350:"EF",351:"SM",352:"HR",353:"SM",354:"AG",355:"EF",356:"JU",357:"EF",358:"EF",359:"AG",360:"FP",
361:"XX",362:"TE",363:"XX",364:"FP",365:"JU",366:"EF",367:"DE",368:"EF",369:"FP",370:"JU",371:"EF",
372:"DE",373:"BI",374:"CA",375:"XX",376:"FP",377:"AG",378:"EF",379:"JU",380:"FP",381:"XX",382:"FP",
383:"EF",384:"EF",385:"EF",386:"DE",387:"JU",388:"CU",389:"AG",390:"TE",391:"FP",392:"EF",393:"SM",
394:"EM",395:"JU",396:"MA",397:"MH",398:"FP",399:"CA",400:"HR",401:"MH",402:"FP",403:"EF",404:"FP",
405:"FP",406:"EN",407:"EM",408:"EF",409:"MH",410:"MH",411:"EM",412:"HR",413:"EF",414:"BI",415:"EV",
416:"JU",417:"EF",418:"CA",419:"EF",420:"CA",421:"FP",422:"FP",423:"RP",424:"EN",425:"SM",426:"TR",
427:"JU",428:"JU",429:"JU",430:"FP",431:"EM",432:"EF",433:"XX",434:"EN",435:"FP",436:"EV",437:"MH",
438:"EN",439:"SM",440:"BI",441:"HE",442:"TE",443:"TR",444:"FP",445:"EF",446:"FP",447:"EF",448:"EF",
449:"AG",450:"XX",451:"FP",452:"MH",453:"FP",454:"EM",455:"CT",456:"TX",457:"EF",458:"CA",459:"FP",
460:"EF",461:"FP",462:"CP",463:"EF",464:"TR",465:"FP",466:"EF",467:"EN",468:"HR",469:"FP",470:"FP",
471:"EF",472:"JU",473:"EF",474:"FP",475:"HR",476:"EF",477:"EF",478:"EF",479:"BI",480:"RP",481:"MH",
482:"EF",483:"MH",484:"EF",485:"JU",486:"XX",487:"EF",488:"HR",489:"SM",490:"RP",491:"JU",492:"FP",
493:"EF",494:"MH",495:"AG",496:"RP",497:"XX",498:"JU",499:"EF",500:"FP",501:"EF",502:"AG",503:"CA",
504:"HR",505:"SM",506:"TE",507:"EF",508:"FP",509:"XX",510:"EM",511:"EV",512:"MH",513:"SM",514:"EV",
515:"SM",516:"EF",517:"EV",518:"EF",519:"FP",520:"XX",521:"EF",522:"EF",523:"BI",524:"EF",525:"FP",
526:"RP",527:"EF",528:"FP",529:"HE",530:"XX",531:"JU",532:"EF",533:"FS",534:"EF",535:"EF",536:"EF",
537:"EF",538:"EM",539:"HR",540:"XX",541:"EF",542:"XX",543:"FP",544:"FP",545:"EM",546:"EF",547:"FP",
548:"TX",549:"JU",550:"DE",551:"TR",552:"AG",553:"XX",554:"MH",555:"AG",556:"EF",557:"EF",558:"DE",
559:"EM",560:"HE",561:"EF",562:"SM",563:"EF",564:"EF",565:"EF",566:"EF",567:"EF",568:"JU",569:"MH",
570:"XX",571:"TR",572:"HR",573:"XX",574:"EF",575:"EF",576:"FP",577:"EF",578:"FP",579:"EF",580:"MA",
581:"EM",582:"RP",583:"XX",584:"BI",585:"SM",586:"FP",587:"EF",588:"EF",589:"EF",590:"JU",591:"XX",
592:"EF",593:"WR",594:"EF",595:"FP",596:"EF",597:"ED",598:"CP",599:"FP",600:"MH",601:"SM",602:"TX",
603:"RP",604:"RP",605:"EF",606:"CP",607:"FP",608:"XX",609:"AG",610:"EF",611:"EF",612:"CN",613:"TE",
614:"FP",615:"CA",616:"HE",617:"JU",618:"EF",619:"MH",620:"XX",621:"XX",622:"EF",623:"DS",624:"EF",
625:"EV",626:"SM",627:"TE",628:"DE",629:"FP",630:"EF",631:"EF",632:"JU",
}


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    data = json.load(open(SCR))
    assert len(data) == 633, f"expected 633, got {len(data)}"
    # validate every code
    bad = {k: v for k, v in M.items() if v != "XX" and v not in C}
    assert not bad, f"bad codes: {bad}"
    db = SessionLocal()
    filled = xx = 0
    for i, item in enumerate(data):
        code = M.get(i, "XX")
        if code == "XX":
            xx += 1; continue
        label = C[code]
        filled += 1
        if args.apply:
            db.execute(text("UPDATE legislative_carriages SET policy_areas=:p WHERE id=:i "
                            "AND (policy_areas IS NULL OR array_length(policy_areas,1) IS NULL)"),
                       {"p": [label], "i": item["id"]})
    if args.apply:
        db.commit()
    print(f"items: {len(data)} | {'filled' if args.apply else 'WOULD fill'}: {filled} | left XX (honest): {xx}")
    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
