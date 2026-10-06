"""Build the 'Preparing for a wider Union' carousel (Commission Communication, 6 October 2026).

Eight 1080x1350 slides, same aesthetic as build_dsa_vlop_list_deck.py. Every claim is
traced to the Communication (read in full), its press release and Q&A, or the Staff
Working Document (figures re-checked against the text on 6 Oct 2026):

  slide 2  Communication intro + Part II: no Treaty amendment; "does not prejudge timing"
  slide 3  Communication Part II.1 (passerelle areas, QMV for clusters, accession stays unanimous)
  slide 4  Communication Part IV (15 years, reverse QMV, suspension of voting rights, sectoral safeguards)
  slide 5  Communication Part III (gradual integration; SEPA; Roam Like at Home)
  slide 6  Communication Part II.4 (Global Europe, Partnership Plans, Montenegro; Ukraine agriculture)
  slide 7  Staff Working Document, EU36/EU27 table (2021 data)
  slide 8  Communication Part V and press release (next steps)

No institutional codes on the slides (public-marketing rule). Hard rule #12: the build
fails on any overflow, on a body/footer overlap, or on a footer gap above 180 px.

  python3.12 backend/scripts/build_wider_union_deck.py
"""
from __future__ import annotations

import base64
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
ROOT = pathlib.Path(_REPO_ROOT)
OUT = ROOT / "docs/marketing/designs/wider_union_deck.html"

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#d9dde3;font-family:'Adobe Caslon Pro',Georgia,'Times New Roman',serif;color:#000}
.slide{width:1080px;height:1350px;background:#fff;position:relative;overflow:hidden;display:flex;flex-direction:column;margin:0 auto 24px}
.hero{background:linear-gradient(135deg,rgba(6,17,47,.96) 0%,rgba(28,61,122,.88) 50%,rgba(91,58,140,.96) 100%);color:#fff;padding:90px 72px 120px;display:flex;flex-direction:column;justify-content:flex-end;flex:1}
.over{font-family:'JetBrains Mono',Menlo,monospace;font-size:32px;letter-spacing:.06em;text-transform:uppercase;opacity:.88;margin-bottom:28px}
.hero h1{font-size:128px;line-height:1.0;font-weight:700}
.hero p{font-size:50px;line-height:1.2;margin-top:34px;opacity:.95}
.body{padding:48px 72px 0;flex:1;display:flex;flex-direction:column;min-height:0}
.lab{font-family:'JetBrains Mono',Menlo,monospace;font-size:30px;letter-spacing:.06em;text-transform:uppercase;color:#7C4DFF;margin-bottom:16px}
h2{font-size:84px;line-height:1.02;font-weight:700;margin-bottom:30px}
.it{border-left:12px solid #0693e3;background:#f9fafb;margin-bottom:var(--gap,18px);padding:var(--pad,22px) 34px;font-size:var(--fs,44px);line-height:1.16}
.it:nth-child(even){border-color:#9b51e0}.it:nth-child(3n){border-color:#059669}
.it b{display:block;font-size:calc(var(--fs,44px) + 6px);line-height:1.08;margin-bottom:6px}
.note{font-size:var(--nfs,44px);line-height:1.2;font-style:italic;background:#f9fafb;border-left:12px solid #9b51e0;padding:26px 34px;margin-top:6px}
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px}
.st{border-left:12px solid #0693e3;background:#f9fafb;padding:var(--pad,30px) 30px}
.st:nth-child(2){border-color:#9b51e0}.st:nth-child(3){border-color:#059669}.st:nth-child(4){border-color:#d97706}
.st .n{font-size:92px;line-height:1;font-weight:700}
.st .l{font-size:40px;line-height:1.15;margin-top:8px}
.foot{height:120px;border-top:6px solid;border-image:linear-gradient(135deg,#0693e3,#9b51e0) 1;display:flex;align-items:center;justify-content:space-between;padding:0 72px;background:#fff;margin-top:24px;flex:none}
.cta{display:flex;align-items:center;gap:18px;font-size:40px;font-weight:700}
.cta img{height:56px}
.by{display:flex;align-items:center;gap:16px;font-size:32px}
.by img{height:46px}
"""

# (label, title, items[(head, text)], note, style vars)
SLIDES = [
    ("What it is not", "Not a date, not a Treaty change", [
        ("No Treaty amendment", "The Union can prepare within the existing Treaties and accession treaties."),
        ("No accession dates", "The package does not prejudge the timing or order of any accession."),
        ("Still merit-based", "Accession needs a unanimous Council decision and ratification by every Member State."),
    ], "It is a policy blueprint: it invites Parliament and Council to act.", "--pad:24px;--gap:18px;--fs:44px;--nfs:44px"),
    ("Governance", "Faster decisions, same Treaties", [
        ("Passerelle clauses", "To move to qualified majority on sanctions, tax fraud, energy tax measures, human rights and civilian missions, social protection."),
        ("Accession talks", "Qualified majority to open negotiating clusters and take intermediate decisions."),
        ("Enhanced cooperation", "A group of at least nine Member States can go ahead when talks are blocked."),
    ], "Accession itself stays unanimous.", "--pad:24px;--gap:20px;--fs:42px;--nfs:46px"),
    ("Safeguards", "A 15-year safeguard after accession", [
        ("A new institutional clause", "For serious breaches of the Union's values and of sincere cooperation: 15 years after accession."),
        ("Reverse majority", "Measures take effect unless the Council rejects them by qualified majority."),
        ("Up to voting rights", "In the most serious cases: suspension of Council voting rights."),
        ("Older safeguards, longer", "Economy, internal market, justice and home affairs: the 3-year window to be significantly extended."),
    ], "It complements the existing rule-of-law procedure; it does not replace it.", "--pad:12px;--gap:10px;--fs:38px;--nfs:40px"),
    ("Gradual integration", "Earlier participation, reversible", [
        ("Conditional and reversible", "Merit-based access to selected policies: energy, transport, digital, defence."),
        ("Annual dialogues", "Each partner reviews progress and gaps with the Commission once a year."),
        ("Already happening", "Five partners have started to take part in SEPA schemes; Ukraine and Moldova joined Roam Like at Home on 1 January 2026."),
    ], "It cannot confer a Commissioner or decision-making rights.", "--pad:22px;--gap:18px;--fs:40px;--nfs:44px"),
    ("Budget", "Who pays, and when", [
        ("Before accession", "Candidates are funded under the proposed Global Europe instrument, tied to reforms."),
        ("At accession", "The plan becomes part of the Partnership Plans, with added cohesion, farm, home affairs and Interreg money."),
        ("Montenegro first", "Its financial package of 30 June 2026 is the template."),
        ("Ukraine and farming", "Targeted arrangements to limit support and market access for sensitive products."),
    ], "", "--pad:26px;--gap:20px;--fs:42px;--nfs:42px"),
]

STATS = [
    ("+21.8%", "area"),
    ("+15.1%", "population"),
    ("+4.8%", "total GDP"),
    ("-8.9%", "GDP per head (2004 round: -8.0%)"),
]


def b64(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def main() -> int:
    icon = b64(ROOT / "frontend/public/assets/brubru_icon_colours.png")
    ber = b64(ROOT / "frontend/public/assets/beresol-logo.png")
    foot = (f'<div class="foot"><div class="cta"><img src="data:image/png;base64,{icon}" alt="">brubru.beresol.eu</div>'
            f'<div class="by">by <img src="data:image/png;base64,{ber}" alt="Beresol"></div></div>')

    out = [f'<section class="slide"><div class="hero"><div class="over">European Commission, 6 October 2026</div>'
           f'<h1>Preparing for a wider Union</h1><p>The blueprint for the next enlargement, in seven slides.</p></div>{foot}</section>']
    for lab, title, items, note, style in SLIDES:
        rows = "".join(f'<div class="it"><b>{h}</b>{t}</div>' for h, t in items)
        nt = f'<div class="note">{note}</div>' if note else ""
        out.append(f'<section class="slide" style="{style}"><div class="body"><div class="lab">{lab}</div><h2>{title}</h2>{rows}{nt}</div>{foot}</section>')
    cards = "".join(f'<div class="st"><div class="n">{n}</div><div class="l">{l}</div></div>' for n, l in STATS)
    out.append(f'<section class="slide" style="--pad:44px;--nfs:44px"><div class="body"><div class="lab">What the numbers say</div>'
               f'<h2>A bigger Union with lower GDP per head</h2><div class="stats">{cards}</div>'
               f'<div class="note" style="margin-top:24px">Commission working document: today&rsquo;s EU27 against the EU plus the enlargement countries it covers, 2021 data.</div></div>{foot}</section>')
    out.append(f'<section class="slide" style="--pad:26px;--gap:20px;--fs:44px;--nfs:46px"><div class="body"><div class="lab">What happens next</div>'
               f'<h2>Three dates to watch</h2>'
               f'<div class="it"><b>15 and 16 October</b>The European Council discusses enlargement and reforms.</div>'
               f'<div class="it"><b>Enlargement package</b>Indicative roadmaps for Montenegro, Albania, Moldova and Ukraine, if reforms keep pace. The College&rsquo;s agenda pencils in 28 October.</div>'
               f'<div class="it"><b>Montenegro first</b>The safeguards and financial arrangements are to be tried on its accession terms.</div>'
               f'<div class="note">Ask Brubru Chat what the Communication says, with the sources.</div></div>{foot}</section>')

    html = (f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><title>Preparing for a wider Union</title>'
            f'<style>{CSS}</style></head><body>{"".join(out)}</body></html>')
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}")

    from PIL import Image
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1200, "height": 1400})
        pg.goto(f"file://{OUT}")
        pg.wait_for_timeout(600)
        over = pg.evaluate("Array.from(document.querySelectorAll('section.slide')).map((s,i)=>({i:i+1,over:s.scrollHeight-s.clientHeight})).filter(x=>x.over>2)")
        gaps = pg.evaluate("""Array.from(document.querySelectorAll('section.slide')).map((s,i)=>{
            const body=s.querySelector('.body'); if(!body) return {i:i+1,gap:null};
            const f=s.querySelector('.foot').getBoundingClientRect(); let low=0;
            body.querySelectorAll('*').forEach(e=>{const r=e.getBoundingClientRect(); if(r.height>0) low=Math.max(low,r.bottom)});
            return {i:i+1,gap:Math.round(f.top-low)}})""")
        print("footer gaps (px):", [(g['i'], g['gap']) for g in gaps])
        bad = [g for g in gaps if g['gap'] is not None and (g['gap'] < 0 or g['gap'] > 180)]
        print("overflowing:", over, "| gap out of 0-180:", bad)
        pngs = []
        for i, el in enumerate(pg.query_selector_all("section.slide"), 1):
            f = OUT.with_name(f"wider_union_slide_{i}.png")
            el.screenshot(path=str(f))
            pngs.append(f)
        b.close()
    if over or bad:
        print("[ERROR] fix the layout before shipping")
        return 1
    imgs = [Image.open(f).convert("RGB") for f in pngs]
    imgs[0].save(str(OUT.with_suffix(".pdf")), save_all=True, append_images=imgs[1:], resolution=150.0)
    sheet = Image.new("RGB", (400 * len(imgs) + 10, 490), "#d9dde3")
    for k, im in enumerate(imgs):
        sheet.paste(im.resize((390, 488)), (10 + k * 400, 1))
    sheet.save(OUT.with_name("wider_union_contact_390.png"))
    print(f"[OK] {OUT.with_suffix('.pdf')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
