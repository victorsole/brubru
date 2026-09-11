"""Build the Public Procurement Act deck.

Fourteen 1080x1350 slides in the canonical Brubru aesthetic, structurally copied
from scripts/build_cra_article14_deck.py: Adobe Caslon Pro, the blue to purple
gradient as a 3px accent rule, light canvas, Pexels heroes with photographer
credits, every image embedded as a base64 data URI so the file converts to PDF
cleanly.

The images are read from frontend/public/public-procurement-act/, where the
deep-dive already stores them, rather than re-fetched: the deck and the page
should look like the same piece of work, and one download is enough.

Every figure traces to COM(2026) 590 final and SWD(2026) 591 final, read on
11 September 2026. Slide 11 quotes the impact assessment's own summary of Loxbo
and Pircher (2025) at its page 40.

  python3.12 scripts/build_ppa_deck.py
"""
from __future__ import annotations

import base64
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
ROOT = pathlib.Path(_REPO_ROOT)
OUT = ROOT / "docs/marketing/designs/public_procurement_act_deck.html"
IMG = ROOT / "frontend/public/public-procurement-act"

HERO_CREDIT = "Aimee"
CLOSE_CREDIT = "Samuel W&ouml;lfl"

CSS = """
:root{
  --ink:#141414; --soft:#4a4a4a; --faint:#7a7a7a;
  --blue:#0693e3; --purple:#9b51e0; --amber:#d97706; --line:#e6e6ea;
  --serif:'Adobe Caslon Pro',Georgia,'Times New Roman',serif;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:#33343a;font-family:var(--serif);color:var(--ink)}
.slide{position:relative;width:1080px;height:1350px;margin:24px auto;background:#fff;
  overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.35)}
.rule{height:3px;width:96px;background:linear-gradient(90deg,var(--blue),var(--purple));border:0}
.overline{font-family:'JetBrains Mono',ui-monospace,monospace;letter-spacing:.22em;
  text-transform:uppercase;font-size:13px;color:var(--purple);font-weight:600}
.pad{padding:76px 64px}
.credit{position:absolute;bottom:14px;right:20px;font-size:11px;color:rgba(255,255,255,.72);
  font-family:ui-sans-serif,system-ui;letter-spacing:.02em}
.pagenum{position:absolute;bottom:26px;left:64px;font-size:12px;color:var(--faint);
  font-family:'JetBrains Mono',monospace;letter-spacing:.1em}
h1{font-size:60px;line-height:1.08;font-weight:600;letter-spacing:-.01em}
h2{font-size:42px;line-height:1.12;font-weight:600;letter-spacing:-.01em}
.lead{font-size:22px;line-height:1.5;color:var(--soft);max-width:40ch}
.body{color:var(--soft);font-size:19px;line-height:1.5}
.card{background:#fff;border:1px solid var(--line);padding:30px 32px}
.tag{font-family:'JetBrains Mono',monospace;font-size:13px;letter-spacing:.14em;
  color:var(--faint);text-transform:uppercase}
.src{color:var(--faint);font-size:15px;margin-top:30px}
/* The natural line box of this stack measures 1.135em (Caslon is absent on the
   build machine, so Georgia renders and Georgia is tall). Any line-height below
   that leaves the digits sitting outside their own box; 1.14 contains them. */
.big{font-size:96px;line-height:1.14;font-weight:600;letter-spacing:-.02em}
.mid{font-size:60px;line-height:1.14;font-weight:600;letter-spacing:-.02em}
table.m{width:100%;border-collapse:collapse;font-size:19px;color:var(--soft)}
table.m th{font-family:'JetBrains Mono',monospace;font-size:12px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--faint);text-align:right;padding:0 0 12px;font-weight:600}
table.m th:first-child{text-align:left}
table.m td{padding:11px 0;border-top:1px solid var(--line);text-align:right;
  font-variant-numeric:tabular-nums}
table.m td:first-child{text-align:left;padding-right:18px}
table.m tr.tot td{border-top:2px solid var(--ink);color:var(--ink);font-weight:600}

/* Print. Without this the 24px screen margin between slides pushes pagination
   out of step and a 14-slide deck prints as 15 pages, with each page carrying
   the tail of the slide before it. */
@page{size:1080px 1350px;margin:0}
@media print{
  body{background:#fff}
  .slide{margin:0;box-shadow:none;break-after:page;page-break-after:always}
  .slide:last-child{break-after:auto;page-break-after:auto}
}
"""


def uri(path: pathlib.Path) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(path.read_bytes()).decode()


def png_uri(path: pathlib.Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def main() -> int:
    hero = uri(IMG / "hero.jpg")
    close = uri(IMG / "cta.jpg")
    beresol_path = ROOT / "frontend/public/assets/beresol-logo_transparent.png"
    if not beresol_path.exists():
        beresol_path = ROOT / "frontend/public/assets/beresol-logo.png"
        print(f"[WARN] transparent Beresol mark missing, using {beresol_path.name}; "
              f"it is RGB with no alpha and paints a white box on a cream footer")
    beresol = png_uri(beresol_path)

    s = []

    # 1 cover
    s.append(f"""<section class="slide" style="display:flex;align-items:flex-end;
  background:linear-gradient(180deg,rgba(10,12,26,.46),rgba(12,16,42,.92)),url('{hero}');
  background-size:cover;background-position:center;color:#fff">
  <div class="pad" style="width:100%">
    <div class="overline" style="color:#c9b8ff">COM(2026) 590 final &middot; 9 September 2026</div>
    <hr class="rule" style="margin:20px 0 28px;width:120px">
    <h1 style="max-width:15ch;text-shadow:0 2px 24px rgba(0,0,0,.4)">The Public Procurement Act</h1>
    <p class="lead" style="color:rgba(255,255,255,.92);margin-top:24px;max-width:34ch">
      Three directives become one directly applicable regulation of 149 articles,
      governing about fifteen per cent of Europe&rsquo;s economy.</p>
  </div>
  <div class="credit">Photo: {HERO_CREDIT} / Pexels</div>
</section>""")

    # 2 scale
    s.append("""<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--blue)">The scale</div>
    <hr class="rule" style="margin:18px 0 44px">
    <div class="big" style="color:var(--blue)">EUR 2.5tn</div>
    <p class="body" style="margin-top:14px;max-width:38ch">spent every year on public procurement across the Union, about 15% of EU GDP.</p>
    <div class="mid" style="color:var(--purple);margin-top:56px">149 articles</div>
    <p class="body" style="margin-top:14px;max-width:38ch">in seven Parts, fifteen Titles and twenty-three Chapters, replacing the three directives of 2014.</p>
    <p class="src">COM(2026) 590 final</p>
  </div>
  <div class="pagenum">02</div>
</section>""")

    # 3 regulation not directive
    s.append("""<section class="slide" style="background:#faf9fc">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">What actually changes</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:17ch">One word carries more weight than the page count</h2>
    <p class="body" style="margin-top:34px;max-width:46ch">A directive is transposed. Twenty-seven national transpositions of the 2014 rules are why a Spanish contractor bidding in Poland meets a different procedural world from the one it knows at home.</p>
    <p class="body" style="margin-top:22px;max-width:46ch">A regulation is not transposed. Article 149 makes it binding in its entirety and directly applicable, so the rules reach the bidder without a national intermediary rewriting them on the way.</p>
    <p class="src">Articles 146 and 149</p>
  </div>
  <div class="pagenum">03</div>
</section>""")

    # 4 thresholds unchanged
    s.append("""<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--blue)">What does not change</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:16ch">The thresholds stay exactly where they are</h2>
    <div style="display:grid;gap:16px;margin-top:40px;font-size:20px;color:var(--soft)">
      <div><strong style="color:var(--ink)">EUR 5 404 000</strong> &middot; works and concessions</div>
      <div><strong style="color:var(--ink)">EUR 140 000</strong> &middot; central government supplies and services</div>
      <div><strong style="color:var(--ink)">EUR 216 000</strong> &middot; sub-central</div>
      <div><strong style="color:var(--ink)">EUR 432 000</strong> &middot; utilities</div>
      <div><strong style="color:var(--ink)">EUR 750 000</strong> &middot; social, health and educational services</div>
    </div>
    <p class="body" style="margin-top:38px;max-width:44ch">They are set by the WTO Government Procurement Agreement, not by this reform. Article 3 has the Commission re-checking them against it every two years.</p>
    <p class="src">Articles 2 and 3</p>
  </div>
  <div class="pagenum">04</div>
</section>""")

    # 5 four procedures
    s.append("""<section class="slide" style="background:#faf9fc">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">How you buy</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:15ch">Four procedures, two of them open to anything</h2>
    <div style="display:grid;gap:22px;margin-top:42px">
      <div class="card"><div class="tag">Articles 34 to 35</div><p class="body" style="margin-top:8px"><strong style="color:var(--ink)">Open.</strong> Publish, anyone may express interest and tender.</p></div>
      <div class="card"><div class="tag">Articles 36 to 40</div><p class="body" style="margin-top:8px"><strong style="color:var(--ink)">Dynamic.</strong> Stays open: a supplier that missed the start can join at any point during its validity.</p></div>
      <div class="card"><div class="tag">Articles 41 to 45</div><p class="body" style="margin-top:8px"><strong style="color:var(--ink)">Innovation.</strong> For a societal challenge with no known solution. Up to two years of testing and validation.</p></div>
      <div class="card"><div class="tag">Articles 46 to 48</div><p class="body" style="margin-top:8px"><strong style="color:var(--ink)">Direct award.</strong> No competition, no prior publication, only in the listed cases or extreme urgency.</p></div>
    </div>
  </div>
  <div class="pagenum">05</div>
</section>""")

    # 6 the 30 percent rule
    s.append("""<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--amber)">The headline rule</div>
    <hr class="rule" style="margin:18px 0 40px">
    <div style="display:flex;align-items:baseline;gap:28px">
      <div class="big" style="color:var(--amber)">30%</div>
      <p class="body" style="max-width:22ch">minimum weight of quality criteria in every award</p>
    </div>
    <div style="display:flex;align-items:baseline;gap:28px;margin-top:44px">
      <div class="big" style="color:var(--purple)">50%</div>
      <p class="body" style="max-width:22ch">where the subject-matter of the contract is labour-intensive</p>
    </div>
    <p class="body" style="margin-top:52px;max-width:46ch">Award goes to the best quality for money, evaluated by the best price-quality ratio. Price alone stops being an option.</p>
    <p class="src">Article 98(1) and 98(4)</p>
  </div>
  <div class="pagenum">06</div>
</section>""")

    # 7 the detail summaries drop
    s.append("""<section class="slide" style="background:#faf9fc">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">The detail most summaries drop</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:18ch">Life-cycle costs count inside the 30%, not on top of it</h2>
    <p class="body" style="margin-top:34px;max-width:46ch">Where life-cycle costing is applied under Article 99, its weight is counted within that percentage. The same goes for environmental criteria set by Union legislation.</p>
    <p class="body" style="margin-top:22px;max-width:46ch">A buyer who reaches 30% by counting life-cycle costs has satisfied the article without weighing a single further quality factor.</p>
    <p class="body" style="margin-top:22px;max-width:46ch">Article 98(5) then allows a departure altogether, where quality is secured through specifications or performance conditions instead. Comply, or explain in the public summary.</p>
    <p class="src">Articles 98(4), 98(5) and 99</p>
  </div>
  <div class="pagenum">07</div>
</section>""")

    # 8 the money
    s.append("""<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--blue)">The money, as the file states it</div>
    <hr class="rule" style="margin:18px 0 34px">
    <h2 style="max-width:18ch">EUR 649 million net, not a round 650</h2>
    <table class="m" style="margin-top:36px">
      <tr><th>Measure</th><th>Buyers</th><th>Operators</th><th>Total</th></tr>
      <tr><td>Simplification, new</td><td>78</td><td>&mdash;</td><td>78</td></tr>
      <tr><td>Quality rule, new</td><td>55</td><td>457</td><td>512</td></tr>
      <tr><td>EU Ecolabel, new</td><td>&mdash;</td><td>12</td><td>12</td></tr>
      <tr><td>European preference, new</td><td>7.4</td><td>7.4</td><td>15</td></tr>
      <tr><td>Simplification, removed</td><td>&minus;166</td><td>&mdash;</td><td>&minus;166</td></tr>
      <tr><td>Digital marketplace, removed</td><td>&minus;220</td><td>&minus;881</td><td>&minus;1 101</td></tr>
      <tr class="tot"><td>Net</td><td>&minus;79</td><td>&minus;570</td><td>&minus;649</td></tr>
    </table>
    <p class="src">SWD(2026) 591 final. Annualised present value over seven years at a 3% discount rate, EUR million a year.</p>
  </div>
  <div class="pagenum">08</div>
</section>""")

    # 9 87 percent
    s.append("""<section class="slide" style="background:#faf9fc">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--blue)">Finding one</div>
    <hr class="rule" style="margin:18px 0 40px">
    <div class="big" style="color:var(--blue)">87%</div>
    <p class="body" style="margin-top:16px;max-width:44ch">of every saving in the file comes from one measure: the digital marketplace, worth EUR 1 101 million of the EUR 1 267 million of removed burden.</p>
    <p class="body" style="margin-top:28px;max-width:44ch">Procedural simplification, the part the headlines describe, contributes EUR 166 million.</p>
    <p class="body" style="margin-top:28px;max-width:44ch"><strong style="color:var(--ink)">The simplification story is a digitisation story.</strong> If the eProcurement platform, the eligibility service and the data spaces underdeliver, so does the entire business case.</p>
    <p class="src">SWD(2026) 591 final, measure MPL.1</p>
  </div>
  <div class="pagenum">09</div>
</section>""")

    # 10 who pays
    s.append("""<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--amber)">Finding two</div>
    <hr class="rule" style="margin:18px 0 40px">
    <div class="big" style="color:var(--amber)">EUR 457m</div>
    <p class="body" style="margin-top:16px;max-width:44ch">a year of new burden falls on economic operators from the quality rule alone, out of EUR 512 million it adds in total.</p>
    <p class="body" style="margin-top:28px;max-width:44ch">It is the single largest new cost in the whole reform, and it lands on the firms that bid rather than on the administrations that chose the policy.</p>
    <p class="body" style="margin-top:28px;max-width:44ch">The press release leads with this policy. The cost of it is in the annex.</p>
    <p class="src">SWD(2026) 591 final, measure ESI.2</p>
  </div>
  <div class="pagenum">10</div>
</section>""")

    # 11 the finding
    s.append("""<section class="slide" style="background:#faf9fc">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--purple)">Finding three</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:18ch">The Commission&rsquo;s own file cuts against its central instrument</h2>
    <div style="border-left:3px solid var(--purple);padding:6px 0 6px 26px;margin-top:34px">
      <p class="body" style="font-size:21px;max-width:42ch">Countries with weaker public administrations experienced an increase in single bidding of approximately <strong style="color:var(--ink)">10 to 11 percentage points</strong>, associated with their increased use of the most economically advantageous tender criteria. Countries with strong public administrations saw a reduction of <strong style="color:var(--ink)">4 to 7 points</strong>.</p>
    </div>
    <p class="body" style="margin-top:30px;max-width:46ch">Single bidding is the standard proxy for irregularity risk, and rising single bidding is the problem the reform cites to justify itself.</p>
    <p class="body" style="margin-top:20px;max-width:46ch">This makes Article 139, on professionalisation and capacity building, far more load-bearing than its position near the end suggests.</p>
    <p class="src">SWD(2026) 591 final, page 40, summarising Loxbo and Pircher (2025)</p>
  </div>
  <div class="pagenum">11</div>
</section>""")

    # 12 european preference
    s.append("""<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--purple)">The politically decisive chapter</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:16ch">European preference, Articles 70 to 77</h2>
    <div style="display:grid;gap:20px;margin-top:38px">
      <div class="card"><div class="tag">Article 72</div><p class="body" style="margin-top:8px">The Commission may remove a third country&rsquo;s covered status by delegated act, on market access, security of supply, or economic security grounds.</p></div>
      <div class="card"><div class="tag">Article 73</div><p class="body" style="margin-top:8px">A buyer may then restrict participation, require Union origin, award extra points, or reject any tender below 50% Union content.</p></div>
      <div class="card" style="border-color:var(--purple)"><div class="tag" style="color:var(--purple)">Article 75, the one to watch</div><p class="body" style="margin-top:8px">The Commission may make those requirements <strong style="color:var(--ink)">mandatory</strong> for all buyers against non-covered operators, by delegated act rather than a new proposal.</p></div>
    </div>
  </div>
  <div class="pagenum">12</div>
</section>""")

    # 13 the fourteen acts
    s.append("""<section class="slide" style="background:#faf9fc">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">The quiet half of the reform</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:17ch">It reaches into fourteen other laws</h2>
    <p class="body" style="margin-top:32px;max-width:46ch">Article 147 deletes the procurement provision sitting inside each of them and redirects its references here. Seven separate green procurement clauses now point at one article.</p>
    <p class="body" style="margin-top:22px;max-width:46ch">Ecodesign, Net-Zero Industry, Batteries, Construction Products, Packaging, Energy Efficiency, Waste Framework, Critical Raw Materials, Accessibility, Gender Balance, Cyber Resilience, Due Diligence, Waste Shipments, Public Transport.</p>
    <div style="border-left:3px solid var(--amber);padding:6px 0 6px 26px;margin-top:32px">
      <p class="body" style="max-width:44ch">The proposal&rsquo;s own title lists <strong style="color:var(--ink)">thirteen</strong>. Article 147 amends <strong style="color:var(--ink)">fourteen</strong>. Build your compliance register from the title and you will miss public transport.</p>
    </div>
    <p class="src">Article 147, points 1 to 14</p>
  </div>
  <div class="pagenum">13</div>
</section>""")

    # 14 close
    s.append(f"""<section class="slide" style="display:flex;flex-direction:column;
  background:linear-gradient(180deg,rgba(9,12,30,.52),rgba(9,16,44,.90)),url('{close}');
  background-size:cover;background-position:center;color:#fff">
  <div class="pad" style="flex:1;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:#c9b8ff">Applies two years after entry into force</div>
    <hr class="rule" style="margin:20px 0 24px;width:110px">
    <h2 style="font-size:46px;max-width:15ch;text-shadow:0 2px 20px rgba(0,0,0,.35)">All 149 articles, explained one by one</h2>
    <p class="lead" style="color:rgba(255,255,255,.9);margin-top:22px;max-width:36ch">
      Brubru has read the proposal, the annexes, the subsidiarity grid and the 432-page impact assessment, and explains every article in six languages.</p>
    <p class="lead" style="color:rgba(255,255,255,.72);margin-top:18px;font-size:18px">brubru.beresol.eu/public-procurement-act</p>
  </div>
  <div style="background:#fff;color:var(--ink);padding:22px 64px;display:flex;align-items:center;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:14px">
      <img src="{beresol}" alt="Beresol" style="height:38px;width:auto">
      <span style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--faint);letter-spacing:.05em">brubru.beresol.eu</span>
    </div>
    <div style="font-size:15px;color:var(--soft)">All the EU, with AI.</div>
  </div>
  <div class="credit" style="bottom:88px">Photo: {CLOSE_CREDIT} / Pexels</div>
</section>""")

    html = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
            "<title>The Public Procurement Act, in plain language - Brubru</title>\n"
            f"<style>{CSS}</style>\n</head><body>\n"
            + "\n".join(s) + "\n</body></html>\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}  ({OUT.stat().st_size/1_000_000:.2f} MB, {len(s)} slides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
