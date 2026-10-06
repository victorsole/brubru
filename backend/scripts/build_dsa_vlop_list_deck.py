"""Build the DSA designated-services carousel (6 October 2026).

Six 1080x1350 slides in the canonical Brubru aesthetic: Adobe Caslon Pro (Georgia
fallback), gradient accent rule, light canvas, Beresol logo on a light footer.

Source of every name and date: the Official Journal C notice published on 6 October
2026 (Commission list of very large online platforms and search engines designated
under the Digital Services Act), read in full from Cellar. 25 platforms + 3 search
engines = 28 services. Stripchat is NOT in the notice (designation terminated by a
Commission decision of 27 May 2025, per the Commission's own list page).

Logos: Simple Icons (CC0 icon geometry, brand colour from the same dataset), inlined
as SVG. Services with no usable icon in that set (AliExpress, Shein, Temu) get a lettermark tile; the
three adult platforms are listed as text only, by decision, on a LinkedIn post.
Brand marks belong to their owners and are shown only to identify the service.

Hard rule #12: every slide is measured for overflow with Playwright; the build fails
on any overflow or on a service count other than 28.

  python3.12 backend/scripts/build_dsa_vlop_list_deck.py
"""
from __future__ import annotations

import base64
import json
import pathlib
import re
import sys
import urllib.request

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
ROOT = pathlib.Path(_REPO_ROOT)
OUT = ROOT / "docs/marketing/designs/dsa_vlop_list_deck.html"
CACHE = ROOT / "docs/marketing/designs/photos/si_icons"
CDN = "https://cdn.jsdelivr.net/npm/simple-icons@latest"

# (name, simple-icons slug or None, designation date as printed in the notice)
SEARCH = [("Bing", "microsoftbing", "25 Apr 2023"), ("Google Search", "google", "25 Apr 2023"),
          ("ChatGPT", "openai", "31 Aug 2026")]
SOCIAL = [("Facebook", "facebook", "25 Apr 2023"), ("Instagram", "instagram", "25 Apr 2023"),
          ("WhatsApp", "whatsapp", "26 Jan 2026"), ("TikTok", "tiktok", "25 Apr 2023"),
          ("Snapchat", "snapchat", "25 Apr 2023"), ("X", "x", "25 Apr 2023"),
          ("LinkedIn", "linkedin", "25 Apr 2023"), ("Pinterest", "pinterest", "25 Apr 2023"),
          ("Reddit", "reddit", "31 Aug 2026"), ("YouTube", "youtube", "25 Apr 2023"),
          ("Roblox", "roblox", "31 Aug 2026"), ("Wikipedia", "wikipedia", "25 Apr 2023")]
SHOP = [("AliExpress", None, "25 Apr 2023"), ("Amazon Store", "amazon", "25 Apr 2023"),
        ("Shein", None, "26 Apr 2024"), ("Temu", None, "31 May 2024"),
        ("Zalando", "zalando", "25 Apr 2023"), ("Booking.com", "bookingdotcom", "25 Apr 2023"),
        ("App Store", "appstore", "25 Apr 2023"), ("Google Play", "googleplay", "25 Apr 2023"),
        ("Google Maps", "googlemaps", "25 Apr 2023"), ("Google Shopping", "google", "25 Apr 2023")]
ADULT = [("Pornhub", "20 Dec 2023"), ("XVideos", "20 Dec 2023"), ("XNXX", "10 Jul 2024")]

_meta: dict[str, str] = {}


def b64(path: pathlib.Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def icon_svg(slug: str, size: int) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"{slug}.svg"
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(f"{CDN}/icons/{slug}.svg", timeout=30).read())
    if not _meta:
        mf = CACHE / "_meta.json"
        if not mf.exists():
            mf.write_bytes(urllib.request.urlopen(f"{CDN}/data/simple-icons.json", timeout=60).read())
        for e in json.loads(mf.read_text()):
            _meta[e["slug"]] = e["hex"]
    hexv = _meta.get(slug, "111111")
    r, g, b = (int(hexv[i:i + 2], 16) for i in (0, 2, 4))
    if (0.299 * r + 0.587 * g + 0.114 * b) > 190:      # too pale on a white tile
        hexv = "111111"
    svg = f.read_text()
    svg = re.sub(r"<svg ", f'<svg width="{size}" height="{size}" fill="#{hexv}" ', svg, count=1)
    return svg


def htile(name: str, slug: str | None, date: str, size: int) -> str:
    if slug:
        mark = icon_svg(slug, size)
    else:
        mark = (f'<div class="mono" style="width:{size}px;height:{size}px;font-size:{int(size*0.6)}px">{name[0]}</div>')
    return f'<div class="htile"><div class="mk">{mark}</div><div class="tx"><div class="nm">{name}</div><div class="dt">{date}</div></div></div>'


def tile(name: str, slug: str | None, date: str, size: int) -> str:
    if slug:
        mark = icon_svg(slug, size)
    else:
        mark = (f'<div class="mono" style="width:{size}px;height:{size}px;font-size:{int(size*0.6)}px">'
                f'{name[0]}</div>')
    return f'<div class="tile"><div class="mk">{mark}</div><div class="nm">{name}</div><div class="dt">{date}</div></div>'


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#d9dde3;font-family:'Adobe Caslon Pro',Georgia,'Times New Roman',serif;color:#000}
.slide{width:1080px;height:1350px;background:#fff;position:relative;overflow:hidden;display:flex;flex-direction:column;margin:0 auto 24px}
.hero{background:linear-gradient(135deg,rgba(6,17,47,.96) 0%,rgba(28,61,122,.88) 50%,rgba(91,58,140,.96) 100%);color:#fff;padding:90px 72px;display:flex;flex-direction:column;justify-content:flex-end;height:900px}
.cover .hero{flex:1;height:auto;padding-bottom:120px}
.s2 .row{padding:32px 44px;margin-bottom:26px;gap:44px}.s2 .row .mk{width:130px}.s2 .row .nm{font-size:74px;white-space:nowrap}.s2 .row .dt{font-size:36px;white-space:nowrap}.s2 .note{font-size:50px;padding:34px 40px}
.s4 .htile{padding:30px 24px}.s4 .htile .mk{width:88px}
.s5 .row{padding:50px 44px;margin-bottom:28px}.s5 .row .nm{font-size:88px}.s5 .row .dt{font-size:40px}.s5 .note{font-size:50px;padding:34px 40px}
.s6 .pt{font-size:46px;padding:20px 34px;margin-bottom:16px}.s6 .note{font-size:48px;padding:26px 36px}
.over{font-family:'JetBrains Mono',Menlo,monospace;font-size:32px;letter-spacing:.06em;text-transform:uppercase;opacity:.88;margin-bottom:28px}
.hero h1{font-size:124px;line-height:1.0;font-weight:700}
.hero p{font-size:50px;line-height:1.2;margin-top:34px;opacity:.95}
.body{padding:48px 72px 0;flex:1;display:flex;flex-direction:column;min-height:0}
.lab{font-family:'JetBrains Mono',Menlo,monospace;font-size:30px;letter-spacing:.06em;text-transform:uppercase;color:#7C4DFF;margin-bottom:16px}
h2{font-size:80px;line-height:1.02;font-weight:700;margin-bottom:26px}
.grid{display:grid;gap:18px;flex:1;min-height:0;align-content:start}
.g3{grid-template-columns:repeat(3,minmax(0,1fr))}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
.tile{border:3px solid #e5e7eb;background:#f9fafb;border-radius:14px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:12px 8px;text-align:center}
.mk{height:80px;display:flex;align-items:center;justify-content:center}
.nm{font-size:40px;font-weight:700;margin-top:6px;line-height:1.05}
.dt{font-family:'JetBrains Mono',Menlo,monospace;font-size:30px;color:#4b5563;margin-top:6px}
.htile{border:3px solid #e5e7eb;background:#f9fafb;border-radius:14px;display:flex;align-items:center;gap:22px;padding:14px 22px}
.htile .mk{height:auto;width:72px;flex:none}
.htile .tx{min-width:0}
.htile .nm{font-size:40px;margin:0}
.htile .dt{margin:2px 0 0}
.mono{display:flex;align-items:center;justify-content:center;border-radius:20px;background:linear-gradient(135deg,#0693e3,#9b51e0);color:#fff;font-weight:700}
.row{display:flex;align-items:center;gap:36px;border-left:12px solid #0693e3;background:#f9fafb;padding:26px 34px;margin-bottom:22px}
.row:nth-child(2){border-color:#9b51e0}.row:nth-child(3){border-color:#059669}
.row .mk{height:auto;width:120px}
.row .nm{font-size:62px;margin:0}
.row .dt{font-size:36px;margin:0 0 0 auto}
.note{font-size:44px;line-height:1.2;font-style:italic;background:#f9fafb;border-left:12px solid #9b51e0;padding:26px 34px;margin-top:10px}
.big{font-size:80px;font-weight:700;line-height:1.02}
.pt{border-left:12px solid #0693e3;background:#f9fafb;padding:18px 30px;margin-bottom:16px;font-size:42px;line-height:1.12}
.pt b{display:block}
.pt:nth-child(even){border-color:#9b51e0}
.foot{height:120px;border-top:6px solid;border-image:linear-gradient(135deg,#0693e3,#9b51e0) 1;display:flex;align-items:center;justify-content:space-between;padding:0 72px;background:#fff;margin-top:24px;flex:none}
.cta{display:flex;align-items:center;gap:18px;font-size:40px;font-weight:700}
.cta img{height:56px}
.by{display:flex;align-items:center;gap:16px;font-size:32px}
.by img{height:46px}
.src{font-size:30px;color:#4b5563;margin-top:14px;font-family:'JetBrains Mono',Menlo,monospace}
"""


def foot(icon_b64: str, beresol_b64: str) -> str:
    return (f'<div class="foot"><div class="cta"><img src="data:image/png;base64,{icon_b64}" alt="">brubru.beresol.eu</div>'
            f'<div class="by">by <img src="data:image/png;base64,{beresol_b64}" alt="Beresol"></div></div>')


def main() -> int:
    total = len(SEARCH) + len(SOCIAL) + len(SHOP) + len(ADULT)
    if total != 28:
        print(f"[ERROR] expected 28 services, got {total}")
        return 1
    icon = b64(ROOT / "frontend/public/assets/brubru_icon_colours.png")
    ber = b64(ROOT / "frontend/public/assets/beresol-logo.png")
    F = foot(icon, ber)

    s1 = (f'<section class="slide cover"><div class="hero"><div class="over">Digital Services Act, 6 October 2026</div>'
          f'<h1>28 services on the EU&rsquo;s official list.</h1><p>25 platforms and 3 search engines, '
          f'published in the Official Journal.</p></div>{F}</section>')
    s2 = (f'<section class="slide s2"><div class="body"><div class="lab">Search engines: 3</div><h2>The three search engines</h2>'
          + "".join(f'<div class="row"><div class="mk">{icon_svg(s,130)}</div><div class="nm">{n}</div><div class="dt">{d}</div></div>' for n, s, d in SEARCH)
          + '<div class="note">ChatGPT is the newest: designated on 31 August 2026.</div></div>' + F + '</section>')
    s3 = (f'<section class="slide"><div class="body"><div class="lab">Platforms: 12</div><h2>Social, video and community</h2>'
          f'<div class="grid g3">' + "".join(tile(n, s, d, 84) for n, s, d in SOCIAL) + '</div></div>' + F + '</section>')
    s4 = (f'<section class="slide s4"><div class="body"><div class="lab">Platforms: 10</div><h2>Shopping, travel and app stores</h2>'
          f'<div class="grid g2">' + "".join(htile(n, s, d, 88) for n, s, d in SHOP) + '</div></div>' + F + '</section>')
    s5 = ('<section class="slide s5"><div class="body"><div class="lab">Platforms: 3, and one removed</div>'
          '<h2>Adult platforms</h2>'
          + "".join(f'<div class="row"><div class="nm">{n}</div><div class="dt">{d}</div></div>' for n, d in ADULT)
          + '<div class="note">Stripchat is gone: its designation was terminated by a Commission decision of 27 May 2025. '
            'A count of 26 platforms is out of date.</div></div>' + F + '</section>')
    s6 = ('<section class="slide s6"><div class="body"><div class="lab">What designation means</div>'
          '<h2>Heavier duties from 45 million users</h2>'
          '<div class="pt"><b>Every year</b>a systemic-risk assessment and an independent audit</div>'
          '<div class="pt"><b>Public</b>an ad repository, and data access for vetted researchers</div>'
          '<div class="pt"><b>Up to 6%</b>of worldwide annual turnover as a fine</div>'
          '<div class="pt"><b>Four months</b>to comply after designation</div>'
          '<div class="note">Ask Brubru Chat who is on the list, and since when.</div></div>' + F + '</section>')

    html = (f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><title>DSA designated services</title>'
            f'<style>{CSS}</style></head><body>{s1}{s2}{s3}{s4}{s5}{s6}</body></html>')
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
        # body content must end above the footer
        gaps = pg.evaluate("""Array.from(document.querySelectorAll('section.slide')).map((s,i)=>{
            const f=s.querySelector('.foot').getBoundingClientRect(); let low=0;
            s.querySelectorAll('.body *').forEach(e=>{const r=e.getBoundingClientRect(); if(r.height>0) low=Math.max(low,r.bottom)});
            return {i:i+1,gap:Math.round(f.top-low)}})""")
        clash = [x for x in gaps if x['gap'] < 0]
        print('gap between content and footer (px):', [(x['i'], x['gap']) for x in gaps])
        print("overflowing slides:", over, "| body/footer overlaps:", clash)
        pngs = []
        for i, el in enumerate(pg.query_selector_all("section.slide"), 1):
            f = OUT.with_name(f"dsa_vlop_list_slide_{i}.png")
            el.screenshot(path=str(f))
            pngs.append(f)
        b.close()
    if over or clash:
        print("[ERROR] fix the layout before shipping")
        return 1
    imgs = [Image.open(f).convert("RGB") for f in pngs]
    pdf = OUT.with_suffix(".pdf")
    imgs[0].save(str(pdf), save_all=True, append_images=imgs[1:], resolution=150.0)
    sheet = Image.new("RGB", (390 * 6 + 70, 490), "#d9dde3")
    for k, im in enumerate(imgs):
        sheet.paste(im.resize((390, 488)), (10 + k * 400, 1))
    sheet.save(OUT.with_name("dsa_vlop_list_contact_390.png"))
    print(f"[OK] {pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
