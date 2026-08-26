"""Instagram carousel: institutional memory in public affairs.

Six slides at 1080x1350, the portrait 4:5 format Instagram recommends for feed
posts. Carousels inherit sizing from the first image, so every slide is built at
identical dimensions rather than letting Instagram crop.

Aesthetic is the canonical coe/sem pattern read from
docs/marketing/designs/index.html (#design-2026-05-15-semana-brubru-es) rather
than invented: Pexels hero with the dark blue to purple overlay, Brubru mark on
a white pill, JetBrains Mono overline, Adobe Caslon title, white body, purple
section label, and the footer strip carrying the Brubru CTA plus the Beresol
mark on every slide.

The angle obeys the marketing rule: lead with what moved in the EU, never with
Brubru. Slide 1 is a regulation that entered into force this week and binds
until 2036; the product appears from slide 4.

Usage:
  python3.12 scripts/build_memory_carousel.py
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

OUT = ROOT / "docs" / "marketing" / "designs" / "memory_carousel.html"
ASSETS = ROOT / "frontend" / "public" / "assets"
KEY = os.environ.get("PEXELS_API_KEY", "")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/151 Safari/537.36")

W, H = 1080, 1350


def data_uri(path: Path) -> str:
    return f"data:image/png;base64,{base64.b64encode(path.read_bytes()).decode()}"


def pexels(query: str, index: int = 0):
    if not KEY:
        print("[ERROR] PEXELS_API_KEY missing"); sys.exit(1)
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "orientation": "portrait", "per_page": 8})
    req = urllib.request.Request(url, headers={"Authorization": KEY, "User-Agent": UA})
    photos = json.load(urllib.request.urlopen(req, timeout=45)).get("photos") or []
    if not photos:
        print(f"[ERROR] no Pexels result for {query!r}"); sys.exit(1)
    p = photos[min(index, len(photos) - 1)]
    img = urllib.request.urlopen(
        urllib.request.Request(p["src"]["large2x"], headers={"User-Agent": UA}), timeout=60).read()
    print(f"  [OK] {query!r} -> {p['photographer']} ({len(img)//1024} KB)")
    return f"data:image/jpeg;base64,{base64.b64encode(img).decode()}", p["photographer"]


def main():
    print("[INFO] fetching Pexels")
    hero, hero_by = pexels("brussels european quarter office", 0)
    close, close_by = pexels("archive shelves documents", 1)
    brubru = data_uri(ASSETS / "brubru_mainlogo.png")
    beresol = data_uri(ASSETS / "beresol-logo.png")

    css = f"""
:root {{
  --navy:#1c3d7a; --purple:#5b3a8c; --deep:#4c1d95;
  --ink:#111827; --soft:#4b5563; --line:#e5e7eb;
  --serif:'Adobe Caslon Pro',Georgia,'Times New Roman',serif;
  --mono:'JetBrains Mono',ui-monospace,monospace;
}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#20222a;font-family:var(--serif);}}
.slide{{
  position:relative;width:{W}px;height:{H}px;background:#fff;overflow:hidden;
  margin:26px auto;display:flex;flex-direction:column;box-shadow:0 10px 44px rgba(0,0,0,.4);
}}
.hero{{position:relative;height:820px;padding:36px 56px 52px;display:flex;
  flex-direction:column;justify-content:flex-end;background-size:cover;background-position:center}}
.hero-overlay{{position:absolute;inset:0;z-index:1;background:linear-gradient(135deg,
  rgba(6,17,47,.90) 0%, rgba(28,61,122,.60) 50%, rgba(91,58,140,.88) 100%)}}
.logo{{position:absolute;top:36px;left:56px;z-index:2;height:54px;width:auto;
  background:rgba(255,255,255,.95);border-radius:9px;padding:5px}}
.overline{{position:relative;z-index:2;font-family:var(--mono);font-size:15px;
  letter-spacing:.18em;text-transform:uppercase;color:rgba(255,255,255,.82);margin-bottom:16px}}
.hero-title{{position:relative;z-index:2;font-size:70px;font-weight:600;line-height:1.05;
  color:#fff;letter-spacing:-.02em}}
.hero-sub{{position:relative;z-index:2;margin-top:20px;font-size:29px;line-height:1.4;
  color:rgba(255,255,255,.92);max-width:26ch}}
.body{{flex:1;padding:56px 56px 30px;background:#fff;display:flex;flex-direction:column}}
.label{{font-family:var(--mono);font-size:15px;font-weight:700;letter-spacing:.16em;
  text-transform:uppercase;color:var(--deep);margin-bottom:26px}}
.h2{{font-size:62px;line-height:1.1;font-weight:600;letter-spacing:-.02em;color:var(--ink)}}
.p{{font-size:31px;line-height:1.45;color:var(--soft);margin-top:26px}}
.p.close{{margin-top:30px}}
.stat-row{{display:flex;gap:20px;margin-top:auto;padding-bottom:8px}}
.stat{{flex:1;border-left:4px solid var(--navy);padding:6px 0 6px 16px}}
.stat:nth-child(2){{border-color:var(--purple)}}
.stat:nth-child(3){{border-color:#0f766e}}
.stat-n{{font-size:64px;font-weight:600;color:var(--ink);line-height:1}}
.stat-l{{font-size:22px;color:var(--soft);margin-top:8px;line-height:1.3}}
.cards{{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:38px;flex:1;align-content:stretch}}
.card{{border:1px solid var(--line);border-radius:16px;padding:34px 30px;background:#fcfcfe;display:flex;flex-direction:column;justify-content:center}}
.card-t{{font-size:31px;font-weight:600;color:var(--ink);margin-bottom:10px}}
.card-d{{font-size:24px;line-height:1.4;color:var(--soft)}}
.quote{{background:#f9fafb;border-left:5px solid var(--purple);padding:34px 36px;margin-top:34px}}
.quote p{{font-style:italic;font-size:33px;line-height:1.42;color:var(--ink)}}
.tl{{margin-top:34px;display:flex;flex-direction:column;gap:0;flex:1;justify-content:center}}
.tl-row{{display:flex;gap:26px;align-items:flex-start;padding:14px 0;border-bottom:1px solid var(--line)}}
.tl-row:last-child{{border-bottom:0}}
.tl-y{{font-family:var(--mono);font-size:25px;font-weight:700;color:var(--navy);min-width:118px}}
.tl-y.now{{color:#b91c1c}}
.tl-t{{font-size:25px;line-height:1.35;color:var(--soft)}}
.footer{{background:#f8f9fa;border-top:1px solid var(--line)}}
.fstrip{{height:4px;background:linear-gradient(90deg,var(--navy) 0%,var(--purple) 100%)}}
.finner{{display:flex;align-items:center;justify-content:space-between;padding:20px 56px}}
.fl{{display:flex;flex-direction:column;gap:3px}}
.fcta{{font-family:var(--mono);font-size:13px;text-transform:uppercase;letter-spacing:.07em;
  color:#6b7280;font-weight:600}}
.furl{{font-size:23px;font-weight:700;color:var(--navy);letter-spacing:-.01em}}
.fr{{display:flex;align-items:center;gap:12px}}
.fr img{{height:34px;width:auto}}
.fby{{font-family:var(--mono);font-size:12px;color:#9ca3af}}
.credit{{position:absolute;bottom:16px;right:24px;z-index:2;font-family:var(--mono);
  font-size:12px;color:rgba(255,255,255,.72)}}
.pageno{{position:absolute;top:40px;right:56px;z-index:2;font-family:var(--mono);
  font-size:15px;color:rgba(255,255,255,.75);letter-spacing:.1em}}
.pageno.dark{{color:#9ca3af}}
"""

    def footer():
        return f"""<div class="footer"><div class="fstrip"></div><div class="finner">
      <div class="fl"><span class="fcta">All the EU, with AI</span>
        <span class="furl">brubru.beresol.eu</span></div>
      <div class="fr"><span class="fby">by</span><img src="{beresol}" alt="Beresol"></div>
    </div></div>"""

    slides = []

    # 1 hero
    slides.append(f"""<section class="slide">
  <div class="hero" style="background-image:url('{hero}')">
    <div class="hero-overlay"></div>
    <img class="logo" src="{brubru}" alt="Brubru">
    <div class="pageno">01</div>
    <p class="overline">EU vehicle circularity law &middot; 13 August 2026</p>
    <h1 class="hero-title">A rule that binds<br>in 2036 was decided<br>this week</h1>
    <p class="hero-sub">The person who took your position on it will probably have changed jobs twice.</p>
    <div class="credit">Photo: {hero_by} / Pexels</div>
  </div>
  <div class="body" style="padding-top:44px">
    <p class="label">What entered into force</p>
    <p class="p" style="margin-top:0">The End-of-Life Vehicles Regulation came into force on 13 August. Its duties arrive on ten separate dates, the last of them in 2036.</p>
    <div class="stat-row">
      <div class="stat"><div class="stat-n">59</div><div class="stat-l">articles</div></div>
      <div class="stat"><div class="stat-n">10</div><div class="stat-l">dated obligations</div></div>
      <div class="stat"><div class="stat-n">10</div><div class="stat-l">years to run</div></div>
    </div>
  </div>{footer()}</section>""")

    # 2 the problem
    slides.append(f"""<section class="slide">
  <div class="body" style="padding-top:64px">
    <div class="pageno dark">02</div>
    <p class="label">The part nobody budgets for</p>
    <h2 class="h2">Positions outlive<br>the people who<br>took them</h2>
    <p class="p">A file opened in 2026 is still live in 2032. By then the rapporteur has moved, the coalition has re-formed, and the reason you argued what you argued sits in an inbox nobody can search.</p>
    <div class="quote"><p>Who said what, why you took that position, and what a stakeholder actually cares about.</p></div>
    <p class="p" style="font-size:23px">Three questions every public affairs team answers from memory, until the memory leaves.</p>
  </div>{footer()}</section>""")

    # 3 where memory goes
    slides.append(f"""<section class="slide">
  <div class="body" style="padding-top:64px">
    <div class="pageno dark">03</div>
    <p class="label">Where it currently lives</p>
    <h2 class="h2">Four places, none<br>of them a system</h2>
    <div class="cards">
      <div class="card"><div class="card-t">An inbox</div><div class="card-d">Searchable only by the person who owns it, and only while they stay.</div></div>
      <div class="card"><div class="card-t">Someone's head</div><div class="card-d">The most reliable archive in Brussels, and the one that resigns.</div></div>
      <div class="card"><div class="card-t">A shared drive</div><div class="card-d">Where the position paper is, if you remember what it was called.</div></div>
      <div class="card"><div class="card-t">A meeting note</div><div class="card-d">Written for a meeting that happened, not for the question asked later.</div></div>
    </div>
    <p class="p" style="margin-top:auto;padding-bottom:6px">None of these tells you, in 2032, what changed and why you cared.</p>
  </div>{footer()}</section>""")

    # 4 what Brubru holds
    slides.append(f"""<section class="slide">
  <div class="body" style="padding-top:64px">
    <div class="pageno dark">04</div>
    <p class="label">What a record looks like instead</p>
    <h2 class="h2">The file remembers,<br>so you do not<br>have to</h2>
    <div class="cards">
      <div class="card"><div class="card-t">Tracked files</div><div class="card-d">Every procedure you follow, with its status and its dates, kept current.</div></div>
      <div class="card"><div class="card-t">Position analysis</div><div class="card-d">Where Commission, Parliament and Council each stand, and when that moved.</div></div>
      <div class="card"><div class="card-t">Lobby meetings</div><div class="card-d">Who met whom, on what subject, from the public register.</div></div>
      <div class="card"><div class="card-t">MEP watch</div><div class="card-d">The people on your file: committee, group, and how they voted.</div></div>
    </div>
    <p class="p" style="margin-top:auto;padding-bottom:6px">Four surfaces, one file, no institutional memory walking out of the door.</p>
  </div>{footer()}</section>""")

    # 5 timeline
    slides.append(f"""<section class="slide">
  <div class="body" style="padding-top:64px">
    <div class="pageno dark">05</div>
    <p class="label">The ten-year ladder, as an example</p>
    <h2 class="h2">One law, ten<br>dates to hold</h2>
    <div class="tl">
      <div class="tl-row"><span class="tl-y now">13 Aug 2026</span><span class="tl-t">In force. Battery substance limits reach vehicles.</span></div>
      <div class="tl-row"><span class="tl-y">14 Sep 2026</span><span class="tl-t">Delegated powers begin.</span></div>
      <div class="tl-row"><span class="tl-y">1 Sep 2028</span><span class="tl-t">The regulation applies. The 2000 directive is repealed.</span></div>
      <div class="tl-row"><span class="tl-y">31 Aug 2029</span><span class="tl-t">Member State producer registers must exist.</span></div>
      <div class="tl-row"><span class="tl-y">1 Sep 2029</span><span class="tl-t">Producer responsibility and circularity strategies.</span></div>
      <div class="tl-row"><span class="tl-y">1 Jan 2030</span><span class="tl-t">Reuse and recovery targets bite.</span></div>
      <div class="tl-row"><span class="tl-y">14 Aug 2030</span><span class="tl-t">Third-country recyclate may count, if audited.</span></div>
      <div class="tl-row"><span class="tl-y">1 Sep 2031</span><span class="tl-t">Only roadworthy vehicles may be exported.</span></div>
      <div class="tl-row"><span class="tl-y">1 Sep 2032</span><span class="tl-t">Design thresholds and the vehicle passport.</span></div>
      <div class="tl-row"><span class="tl-y">1 Sep 2036</span><span class="tl-t">Recycled plastic rises to a quarter.</span></div>
    </div>
  </div>{footer()}</section>""")

    # 6 close
    slides.append(f"""<section class="slide">
  <div class="hero" style="height:100%;background-image:url('{close}')">
    <div class="hero-overlay"></div>
    <img class="logo" src="{brubru}" alt="Brubru">
    <div class="pageno">06</div>
    <p class="overline">Brubru &middot; EU policy intelligence</p>
    <h1 class="hero-title">Keep the file,<br>not the folklore</h1>
    <p class="hero-sub">Tracked files, position analysis, lobby meetings and MEP watch, on the same record. 14-day free trial.</p>
    <div class="credit">Photo: {close_by} / Pexels</div>
  </div>{footer()}</section>""")

    html = (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<title>Institutional memory carousel {W}x{H} - Brubru</title>"
            f"<style>{css}</style></head><body>" + "\n".join(slides) + "</body></html>")
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] wrote {OUT} ({OUT.stat().st_size//1024} KB, {len(slides)} slides at {W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
