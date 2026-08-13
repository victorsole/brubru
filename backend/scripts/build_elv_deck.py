"""Build the End-of-Life Vehicles Regulation slide deck (lawdrop phase 4).

Follows the /design brand kit and copies the structure of ppwr_deck.html, which
is the template that shipped: Adobe Caslon Pro, the blue to purple gradient as a
3px rule, light canvas, Pexels heroes with photographer credits, the Brubru mark
top-left of slide 1, and a closing slide whose light footer carries the Beresol
logo and the motto.

Images are embedded as base64 data URIs so the file converts to PowerPoint and
PDF without any external fetch.

Usage:
  python3.12 scripts/build_elv_deck.py
"""
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

OUT = ROOT / "docs" / "marketing" / "designs" / "elv_deck.html"
ASSETS = ROOT / "frontend" / "public" / "assets"
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")


def data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def pexels(query: str, index: int = 0):
    """Return (data_uri, photographer). Landscape, large size, embedded."""
    if not PEXELS_KEY:
        print("[ERROR] PEXELS_API_KEY missing from .env")
        sys.exit(1)
    url = ("https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "landscape", "per_page": 8}))
    # Pexels 403s the default Python-urllib User-Agent, on the API host as well
    # as on the image CDN. curl with the same key works, which is the tell.
    req = urllib.request.Request(url, headers={"Authorization": PEXELS_KEY, "User-Agent": UA})
    data = json.load(urllib.request.urlopen(req, timeout=45))
    photos = data.get("photos") or []
    if not photos:
        print(f"[ERROR] no Pexels result for {query!r}")
        sys.exit(1)
    photo = photos[min(index, len(photos) - 1)]
    # images.pexels.com 403s a bare urllib request; the API host does not.
    img_req = urllib.request.Request(photo["src"]["large2x"],
                                     headers={"User-Agent": UA})
    img = urllib.request.urlopen(img_req, timeout=60).read()
    print(f"  [OK] {query!r} -> {photo['photographer']} ({len(img) // 1024} KB)")
    return (f"data:image/jpeg;base64,{base64.b64encode(img).decode()}",
            photo["photographer"])


def main():
    print("[INFO] fetching Pexels heroes")
    hero, hero_credit = pexels("car scrapyard dismantling", 0)
    cta, cta_credit = pexels("car factory production line", 1)
    brubru = data_uri(ASSETS / "brubru_mainlogo.png")
    beresol = data_uri(ASSETS / "beresol-logo.png")

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>End-of-Life Vehicles Regulation in force 13 August 2026 - Brubru</title>
<style>
:root{{
  --ink:#141414; --soft:#4a4a4a; --faint:#7a7a7a;
  --blue:#0693e3; --purple:#9b51e0; --line:#e6e6ea;
  --serif:'Adobe Caslon Pro',Georgia,'Times New Roman',serif;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#33343a;font-family:var(--serif);color:var(--ink)}}
.slide{{
  position:relative;width:1280px;height:720px;margin:24px auto;background:#fff;
  overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.35);
}}
.rule{{height:3px;width:96px;background:linear-gradient(90deg,var(--blue),var(--purple));border:0}}
.overline{{font-family:'JetBrains Mono',ui-monospace,monospace;letter-spacing:.22em;
  text-transform:uppercase;font-size:13px;color:var(--purple);font-weight:600}}
.pad{{padding:72px 84px}}
.credit{{position:absolute;bottom:14px;right:20px;font-size:11px;color:rgba(255,255,255,.72);
  font-family:ui-sans-serif,system-ui;letter-spacing:.02em}}
.pagenum{{position:absolute;bottom:26px;left:84px;font-size:12px;color:var(--faint);
  font-family:'JetBrains Mono',monospace;letter-spacing:.1em}}
h1{{font-size:64px;line-height:1.08;font-weight:600;letter-spacing:-.01em}}
h2{{font-size:44px;line-height:1.12;font-weight:600;letter-spacing:-.01em}}
.lead{{font-size:23px;line-height:1.5;color:var(--soft);max-width:46ch}}
</style></head>
<body>

<!-- 01 title -->
<section class="slide" style="display:flex;align-items:flex-end;
  background:linear-gradient(180deg,rgba(9,12,30,.15) 0%,rgba(9,16,44,.86) 100%),url('{hero}');
  background-size:cover;background-position:center;color:#fff">
  <img src="{brubru}" alt="Brubru" style="position:absolute;top:40px;left:74px;height:76px;width:auto;z-index:5;filter:drop-shadow(0 2px 10px rgba(0,0,0,.45))">
  <div class="pad" style="padding-bottom:96px">
    <div class="overline" style="color:#c9b8ff">EU Vehicle Circularity Law &middot; Regulation (EU) 2026/1738</div>
    <hr class="rule" style="margin:20px 0 26px;width:110px">
    <h1 style="max-width:21ch;text-shadow:0 2px 20px rgba(0,0,0,.35)">The End-of-Life Vehicles Regulation is in force from 13 August 2026</h1>
    <p class="lead" style="color:rgba(255,255,255,.9);margin-top:24px;max-width:54ch">One regulation for the whole vehicle life cycle, from how a car is designed to who pays when it becomes waste. It replaces two directives that had governed the field since 2000 and 2005.</p>
  </div>
  <div class="credit">Photo: {hero_credit} / Pexels</div>
  <div class="pagenum" style="color:rgba(255,255,255,.7)">01</div>
</section>

<!-- 02 what changed -->
<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">What has changed</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:25ch">Two directives become one regulation, and vehicle design becomes law</h2>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:28px;margin-top:52px">
      <div><div style="font-size:52px;font-weight:600;color:var(--blue)">2000 &rarr; 2026</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:8px">The 2000 End-of-Life Vehicles Directive and the 2005 type-approval directive are repealed, with effect from 1 September 2028.</p></div>
      <div><div style="font-size:52px;font-weight:600;color:var(--purple)">27</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:8px">Member States, one rulebook. Directly applicable, so the same duties bind you in every market you sell into.</p></div>
      <div><div style="font-size:52px;font-weight:600;color:var(--blue)">Design<br>to scrap</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:8px">From the materials chosen at the drawing board, through the passport that travels with the vehicle, to who pays for its treatment.</p></div>
    </div>
  </div>
  <div class="pagenum">02</div>
</section>

<!-- 03 the date -->
<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">The date that matters today</div>
    <hr class="rule" style="margin:18px 0 26px">
    <div style="display:flex;align-items:baseline;gap:22px">
      <div style="font-size:120px;font-weight:600;letter-spacing:-.03em;line-height:.9">13 Aug</div>
      <div style="font-size:120px;font-weight:600;letter-spacing:-.03em;line-height:.9;
        background:linear-gradient(90deg,var(--blue),var(--purple));-webkit-background-clip:text;background-clip:text;color:transparent">2026</div>
    </div>
    <p class="lead" style="margin-top:22px;max-width:62ch">The Regulation enters into force today, the twentieth day after publication. Most of it applies from 2028, but one article binds immediately:</p>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px 44px;margin-top:26px;max-width:1010px">
      <div style="font-size:19px;color:var(--ink)"><b>Battery substance limits reach vehicles.</b> Annex I of the Batteries Regulation is replaced, extending the mercury, cadmium and lead limits expressly to batteries incorporated in vehicles (Art 53).</div>
      <div style="font-size:19px;color:var(--ink)"><b>Four old exemptions close.</b> Entries 5(a), 5(b)(i), 5(b)(ii) and 16 of Annex II to the 2000 Directive cease to apply on the same day (Art 57).</div>
      <div style="font-size:19px;color:var(--ink)"><b>Legacy fleets get their own clock.</b> Vehicles put on the market before today sit under a separate cost derogation when producer responsibility starts (Art 20).</div>
      <div style="font-size:19px;color:var(--ink)"><b>The delegated machinery starts 14 September 2026,</b> which is when the methodologies behind every later target begin to be written.</div>
    </div>
  </div>
  <div class="pagenum">03</div>
</section>

<!-- 04 phase-in -->
<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">How it phases in</div>
    <hr class="rule" style="margin:18px 0 24px">
    <h2 style="margin-bottom:40px">Ten years of duties, arriving in waves</h2>
    <div style="display:flex;gap:34px;align-items:stretch">
      <div style="flex:1">
        <div style="font-weight:600;font-size:21px;color:#0693e3">2026 to 2028</div>
        <div style="height:3px;background:#0693e3;margin:10px 0 14px;border-radius:2px"></div>
        <ul style="list-style:none;color:var(--soft);font-size:16px;line-height:1.5">
          <li style="margin-bottom:9px"><b style="color:var(--ink)">13 Aug 2026</b> battery substance limits in vehicles</li>
          <li style="margin-bottom:9px"><b style="color:var(--ink)">14 Sep 2026</b> delegated empowerments</li>
          <li style="margin-bottom:9px"><b style="color:var(--ink)">1 Sep 2028</b> the Regulation applies; the 2000 Directive is repealed</li>
        </ul>
      </div>
      <div style="flex:1">
        <div style="font-weight:600;font-size:21px;color:#5a72e4">2029 to 2031</div>
        <div style="height:3px;background:#5a72e4;margin:10px 0 14px;border-radius:2px"></div>
        <ul style="list-style:none;color:var(--soft);font-size:16px;line-height:1.5">
          <li style="margin-bottom:9px"><b style="color:var(--ink)">1 Sep 2029</b> producer responsibility, circularity strategy, national penalties</li>
          <li style="margin-bottom:9px"><b style="color:var(--ink)">1 Jan 2030</b> 95 % recovery and 85 % recycling per vehicle per year</li>
          <li style="margin-bottom:9px"><b style="color:var(--ink)">1 Sep 2031</b> only roadworthy vehicles may be exported</li>
        </ul>
      </div>
      <div style="flex:1">
        <div style="font-weight:600;font-size:21px;color:#9b51e0">2032 to 2036</div>
        <div style="height:3px;background:#9b51e0;margin:10px 0 14px;border-radius:2px"></div>
        <ul style="list-style:none;color:var(--soft);font-size:16px;line-height:1.5">
          <li style="margin-bottom:9px"><b style="color:var(--ink)">1 Sep 2032</b> 85 % recyclable and 95 % recoverable by mass at type-approval</li>
          <li style="margin-bottom:9px"><b style="color:var(--ink)">1 Sep 2032</b> 15 % recycled plastic, and the Digital Circularity Vehicle Passport</li>
          <li style="margin-bottom:9px"><b style="color:var(--ink)">1 Sep 2036</b> 25 % recycled plastic</li>
        </ul>
      </div>
    </div>
  </div>
  <div class="pagenum">04</div>
</section>

<!-- 05 what to do -->
<section class="slide" style="display:flex">
  <div style="flex:1;background:linear-gradient(160deg,#f7f8ff,#eef1fb);padding:72px 60px;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">What a business does now</div>
    <hr class="rule" style="margin:18px 0 26px">
    <h2 style="font-size:38px;max-width:16ch">Five moves, in the order the dates arrive</h2>
    <p style="color:var(--soft);font-size:17px;line-height:1.5;margin-top:22px;max-width:34ch">The recycled-content targets look distant. The supply contracts that deliver them are signed years earlier.</p>
  </div>
  <div style="flex:1.25;padding:72px 64px;display:flex;flex-direction:column;justify-content:center">
    <ol style="list-style:none">
      <li style="position:relative;padding-left:44px;margin:14px 0;font-size:19px;line-height:1.4">
        <span style="position:absolute;left:0;top:-2px;font-weight:600;color:var(--purple);font-size:22px">1</span>
        <b>Audit every battery in every vehicle</b> against the new Annex I table today, not against the exemptions that closed.</li>
      <li style="position:relative;padding-left:44px;margin:14px 0;font-size:19px;line-height:1.4">
        <span style="position:absolute;left:0;top:-2px;font-weight:600;color:var(--purple);font-size:22px">2</span>
        <b>Establish which category and which date</b> applies to your fleet: cars and vans first, buses, lorries and two-wheelers from 2031.</li>
      <li style="position:relative;padding-left:44px;margin:14px 0;font-size:19px;line-height:1.4">
        <span style="position:absolute;left:0;top:-2px;font-weight:600;color:var(--purple);font-size:22px">3</span>
        <b>Start the recyclate supply now.</b> Third-country recyclate only counts from 14 August 2030, and only from audited installations.</li>
      <li style="position:relative;padding-left:44px;margin:14px 0;font-size:19px;line-height:1.4">
        <span style="position:absolute;left:0;top:-2px;font-weight:600;color:var(--purple);font-size:22px">4</span>
        <b>Register as a producer in every market</b> before responsibility begins on 1 September 2029.</li>
      <li style="position:relative;padding-left:44px;margin:14px 0;font-size:19px;line-height:1.4">
        <span style="position:absolute;left:0;top:-2px;font-weight:600;color:var(--purple);font-size:22px">5</span>
        <b>Design the passport into the vehicle,</b> not onto it, so it interoperates with the battery passport rather than duplicating it.</li>
    </ol>
  </div>
  <div class="pagenum" style="left:auto;right:36px">05</div>
</section>

<!-- 06 who is bound -->
<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">Who is bound</div>
    <hr class="rule" style="margin:18px 0 24px">
    <h2 style="margin-bottom:38px">The duty follows your role, and roles can stack</h2>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:22px;max-width:1040px">
      <div style="border:1px solid var(--line);border-radius:14px;padding:26px 24px;background:#fcfcfe">
        <div style="font-weight:600;font-size:21px;margin-bottom:8px">Manufacturer</div>
        <p style="color:var(--soft);font-size:16px;line-height:1.45">Designs to the recyclability and recycled-content thresholds, holds the material data through the supply chain, files the circularity strategy and issues the vehicle passport.</p></div>
      <div style="border:1px solid var(--line);border-radius:14px;padding:26px 24px;background:#fcfcfe">
        <div style="font-weight:600;font-size:21px;margin-bottom:8px">Producer</div>
        <p style="color:var(--soft);font-size:16px;line-height:1.45">Registers in every Member State where it first makes a vehicle available, and funds collection, treatment, awareness and reporting for those vehicles.</p></div>
      <div style="border:1px solid var(--line);border-radius:14px;padding:26px 24px;background:#fcfcfe">
        <div style="font-weight:600;font-size:21px;margin-bottom:8px">Treatment facility</div>
        <p style="color:var(--soft);font-size:16px;line-height:1.45">Depollutes, removes and assesses each part for reuse, remanufacturing or recycling, and issues the electronic certificate of destruction that discharges the last owner.</p></div>
      <div style="border:1px solid var(--line);border-radius:14px;padding:26px 24px;background:#fcfcfe">
        <div style="font-weight:600;font-size:21px;margin-bottom:8px">Exporter</div>
        <p style="color:var(--soft);font-size:16px;line-height:1.45">From 2031 proves at the customs counter that the vehicle is not an end-of-life vehicle and is roadworthy, or it does not leave the Union.</p></div>
    </div>
    <p style="margin-top:30px;color:var(--faint);font-size:15px">Sell a used part from a dismantled vehicle and you inherit the labelling duty that came with it.</p>
  </div>
  <div class="pagenum">06</div>
</section>

<!-- 07 CTA -->
<section class="slide" style="display:flex;flex-direction:column;
  background:linear-gradient(180deg,rgba(9,12,30,.35),rgba(9,16,44,.82)),url('{cta}');
  background-size:cover;background-position:center;color:#fff">
  <div class="pad" style="flex:1;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:#c9b8ff">In force today, binding for the next decade</div>
    <hr class="rule" style="margin:20px 0 24px;width:110px">
    <h2 style="font-size:50px;max-width:21ch;text-shadow:0 2px 20px rgba(0,0,0,.35)">Check your vehicles against the Regulation, obligation by obligation</h2>
    <p class="lead" style="color:rgba(255,255,255,.9);margin-top:22px;max-width:58ch">
      Brubru&rsquo;s EU Law Comply reads your documentation against the 25 binding obligations in this Regulation and shows you the gaps, with the article and the date each one binds.</p>
  </div>
  <div style="background:#fff;color:var(--ink);padding:22px 84px;display:flex;align-items:center;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:14px">
      <img src="{beresol}" alt="Beresol" style="height:38px;width:auto">
      <span style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--faint);letter-spacing:.05em">brubru.beresol.eu</span>
    </div>
    <div style="font-size:15px;color:var(--soft)">All the EU, with AI.</div>
  </div>
  <div class="credit" style="bottom:88px">Photo: {cta_credit} / Pexels</div>
</section>
</body></html>
"""
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] wrote {OUT} ({OUT.stat().st_size // 1024} KB, 7 slides)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
