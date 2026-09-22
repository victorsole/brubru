"""Brubru carousel: the new Union Customs Code (Regulation (EU) 2026/2108).

Eight 1080x1350 slides in the canonical Brubru aesthetic, structurally copied from
`build_soteu_2026_deck.py` (v2). Written 22 September 2026 after a first attempt
produced a bespoke two-page A4 PDF that did not follow this method at all.

Type floor enforced in CSS px on the 1080px canvas, per
[[feedback_carousel_type_floor_for_phones]]: slide titles >=80px (cover >=104px),
row headlines >=46px, body >=38px, labels and footnotes >=30px, big numbers
>=100px. A carousel is read on a phone at roughly 0.36 feed scale, so 30px on the
canvas is 11px on the phone: a floor for labels, not for text.

Three automated checks run in the same pass and FAIL THE BUILD (exit 1), because a
slide that overflows or whispers still screenshots as if it were finished:
  (a) overflow   -- no section may scroll,
  (b) type floor -- every text node outside the footer computes to >=30px,
  (c) empty band -- no gap over 120px between blocks or before the footer.
The footer is excluded by design and carries its own floor (logo >=40px).

Every fact was read from the act itself on 22 September 2026 (Cellar XHTML, CELEX
32026R2108, Articles 285 to 287 and Recital 88). Nothing here comes from trade
press.

Usage:  python3.12 scripts/build_customs_code_2026_deck.py
Output: docs/marketing/designs/customs_code_2026_deck.{html,pdf} + _slides/
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "marketing" / "designs" / "customs_code_2026_deck.html"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

# Stacked shipping containers at a seaport. Checked against the photo's own alt
# text before use: "Sunset over a bustling seaport filled with stacked shipping
# containers". Goods crossing a border is exactly what this Regulation governs.
HERO = {"id": 3057960, "photographer": "Tom Fisk"}


def pexels_src(photo_id: int) -> str:
    key = (os.environ.get("PEXELS_API_KEY") or "").strip()
    req = urllib.request.Request(
        f"https://api.pexels.com/v1/photos/{photo_id}",
        headers={"Authorization": key, "User-Agent": UA, "Accept": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=60))["src"]["large2x"]


def data_uri_from_url(url: str, mime: str = "image/jpeg") -> str:
    raw = urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90).read()
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


def data_uri_from_file(path: Path, mime: str = "image/png") -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


CSS = """
:root{
  --ink:#141414; --soft:#4a4a4a; --faint:#7a7a7a;
  --blue:#0693e3; --purple:#9b51e0; --line:#e6e6ea;
  --serif:'Adobe Caslon Pro',Georgia,'Times New Roman',serif;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:#33343a;font-family:var(--serif);color:var(--ink)}
.slide{position:relative;width:1080px;height:1350px;margin:24px auto;background:#fff;
  overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.35)}
.rule{height:4px;width:120px;background:linear-gradient(90deg,var(--blue),var(--purple));border:0}
.overline{font-family:'JetBrains Mono',ui-monospace,monospace;letter-spacing:.08em;
  text-transform:uppercase;font-size:32px;color:var(--purple);font-weight:700}
.pad{padding:80px 64px 0}
.pagenum{font-family:'JetBrains Mono',monospace;font-size:22px;color:var(--faint);letter-spacing:.06em}
h1{font-size:104px;line-height:1.12;font-weight:600;letter-spacing:-.01em}
h2{font-size:84px;line-height:1.16;font-weight:600;letter-spacing:-.01em}
.lead{font-size:42px;line-height:1.3;color:var(--soft)}
.body{color:var(--soft);font-size:40px;line-height:1.32}
.tag{font-family:'JetBrains Mono',monospace;font-size:32px;letter-spacing:.06em;
  color:var(--faint);text-transform:uppercase}
.src{color:var(--faint);font-size:30px;line-height:1.3}

.stat{border-top:3px solid var(--line);padding:26px 0 22px}
.stat-num{font-size:100px;font-weight:600;line-height:1.02;letter-spacing:-.02em}
.stat-label{font-size:32px;color:var(--faint);font-family:'JetBrains Mono',monospace;
  letter-spacing:.05em;text-transform:uppercase;margin-top:10px}
.stat-note{font-size:34px;color:var(--soft);line-height:1.28;margin-top:12px}

.row{border-top:3px solid var(--line);padding:30px 0}
.row-head{font-weight:600;font-size:50px;line-height:1.16}
.row-body{color:var(--soft);font-size:38px;line-height:1.3;margin-top:12px}

.wave{display:flex;align-items:baseline;gap:26px;border-top:3px solid var(--line);padding:28px 0}
.wave-year{font-family:'JetBrains Mono',monospace;font-size:64px;font-weight:700;
  color:var(--ink);line-height:1;min-width:230px}
.wave-text{font-size:40px;line-height:1.28;color:var(--soft)}
.wave-text b{color:var(--ink);font-weight:600}

.warnbox{background:#fffbeb;border-left:8px solid #d97706;padding:36px 40px}
.warnbox .body{color:var(--ink)}

.footer-brand{position:absolute;left:64px;right:64px;bottom:26px;display:flex;
  align-items:center;justify-content:space-between}
.footer-brand-left{display:flex;align-items:center;gap:16px}
.footer-logo{height:62px;width:auto;display:block}
.footer-icon{height:46px;width:auto;display:block}
.footer-by{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:24px;
  color:var(--faint);letter-spacing:.04em}
.footer-word{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:27px;
  font-weight:700;color:var(--ink);letter-spacing:.02em}
.footer-pill{background:rgba(255,255,255,.94);border-radius:40px;padding:12px 22px}
.footer-pill .footer-word{color:var(--soft)}
.credit{font-size:20px;color:rgba(255,255,255,.75);font-family:ui-sans-serif,system-ui;
  letter-spacing:.02em}
"""


def footer(page: str, *, on_dark: bool = False, credit: str | None = None) -> str:
    """Brubru icon + "Brubru" + "by" + a visible Beresol logo (hard rule 7).

    Excluded from the 30px text floor by design; it carries its own floor
    (brand text >=24px, logo >=40px tall). The brubru.beresol.eu CTA text is
    reserved for the final slide alone, per the single-CTA rule.
    """
    left_wrap = "footer-brand-left footer-pill" if on_dark else "footer-brand-left"
    pagenum_style = "color:rgba(255,255,255,.85)" if on_dark else "color:var(--faint)"
    credit_html = f'<span class="credit" style="margin-right:18px">{credit}</span>' if credit else ""
    return f"""<div class="footer-brand">
    <div class="{left_wrap}">
      <img src="{{brubru_icon}}" alt="" class="footer-icon">
      <span class="footer-word">Brubru</span>
      <span class="footer-by">by</span>
      <img src="{{beresol}}" alt="Beresol" class="footer-logo">
    </div>
    <div style="display:flex;align-items:center">
      {credit_html}
      <span class="pagenum" style="{pagenum_style}">{page}</span>
    </div>
  </div>"""


def main() -> int:
    hero = data_uri_from_url(pexels_src(HERO["id"]))
    beresol = data_uri_from_file(ROOT / "frontend/public/assets/beresol-logo_transparent.png")
    brubru_icon = data_uri_from_file(ROOT / "frontend/public/assets/brubru_icon_colours.png")

    def f(page: str, **kw) -> str:
        return footer(page, **kw).replace("{brubru_icon}", brubru_icon).replace("{beresol}", beresol)

    S: list[str] = []

    # 1 — cover
    S.append(f"""<section class="slide" style="background:#0b0c10">
  <img src="{hero}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.52">
  <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(9,12,30,.30),rgba(9,12,30,.86))"></div>
  <div class="pad" style="position:relative;height:100%;display:flex;flex-direction:column;justify-content:flex-end;padding-bottom:190px">
    <div class="overline" style="color:#c9b8ff">Adopted law &middot; in force</div>
    <hr class="rule" style="margin:24px 0 30px">
    <h1 style="color:#fff">The EU has a<br>new Customs Code</h1>
    <p class="lead" style="color:rgba(255,255,255,.88);margin-top:30px">
      It replaces the 2013 Code, creates a European Union Customs Authority,
      and starts a decade-long move onto a single EU Customs Data Hub.</p>
  </div>
  {f("01", on_dark=True, credit=f"Photo: {HERO['photographer']} / Pexels")}
</section>""")

    # 2 — the four dates
    S.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">Four dates</div>
    <hr class="rule" style="margin:22px 0 34px">
    <h2>Two of them are<br>already behind you</h2>
    <div style="margin-top:44px">
      <div class="stat"><div class="stat-num">19 Sep</div>
        <div class="stat-label">2026 &middot; published in the Official Journal</div></div>
      <div class="stat"><div class="stat-num">20 Sep</div>
        <div class="stat-label">2026 &middot; in force, the day after publication</div></div>
      <div class="stat"><div class="stat-num">29 Sep</div>
        <div class="stat-label">2026 &middot; first deadline for the Commission</div></div>
      <div class="stat"><div class="stat-num">21 Sep</div>
        <div class="stat-label">2027 &middot; the Regulation generally applies</div></div>
    </div>
  </div>
  {f("02")}
</section>""")

    # 3 — what changes
    S.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">What changes</div>
    <hr class="rule" style="margin:22px 0 34px">
    <h2>Three things that<br>did not exist before</h2>
    <div style="margin-top:44px">
      <div class="row"><div class="row-head">A European Union Customs Authority</div>
        <div class="row-body">A new EU body, to be located in Lille, France.</div></div>
      <div class="row"><div class="row-head">An EU Customs Data Hub</div>
        <div class="row-body">One place to provide customs information, replacing the
          declaration-by-declaration model over a staged decade.</div></div>
      <div class="row"><div class="row-head">A Union handling fee</div>
        <div class="row-body">Introduced for consignments in distance sales. The Regulation
          creates the fee; a delegated act sets the amount.</div></div>
    </div>
  </div>
  {f("03")}
</section>""")

    # 4 — in force is not applies
    S.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">The trap</div>
    <hr class="rule" style="margin:22px 0 34px">
    <h2>"In force" does not<br>mean "applies"</h2>
    <p class="body" style="margin-top:30px">Most of the Regulation waits until
      <b style="color:var(--ink)">21 September 2027</b>.</p>
    <div class="warnbox" style="margin-top:28px">
      <p class="body">But a specific list applied <b>immediately</b> on 20 September 2026,
        including every power for the Commission to adopt delegated and implementing acts.</p>
    </div>
    <div class="row" style="margin-top:26px"><div class="row-head">Also live since 20 September</div>
      <div class="row-body">The handling-fee article, bar three of its paragraphs. The articles
        on the Data Hub itself. The penalty and review provisions.</div></div>
    <p class="body" style="margin-top:24px">So a deadline can already fall in September 2026,
      a year before the Regulation generally applies.</p>
  </div>
  {f("04")}
</section>""")

    # 5 — the first deadline
    S.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">Next week</div>
    <hr class="rule" style="margin:22px 0 34px">
    <h2>The first deadline<br>is the fee</h2>
    <div class="stat" style="margin-top:52px;border-top:0">
      <div class="stat-num" style="font-size:150px">29 Sep</div>
      <div class="stat-label">2026</div>
      <p class="stat-note" style="font-size:40px;margin-top:26px">By this date the Commission
        must adopt the delegated act setting the <b style="color:var(--ink)">amount</b> of the
        new Union handling fee.</p>
    </div>
    <p class="body" style="margin-top:34px">The fee is charged on consignments in
      <b style="color:var(--ink)">distance sales</b>: the parcels that arrive from outside
      the EU when someone buys online.</p>
    <p class="src" style="margin-top:30px">A second delegated act follows by 1 March 2028.
      Until the first is published, any figure circulating for the fee is a forecast.</p>
  </div>
  {f("05")}
</section>""")

    # 6 — the Data Hub in three waves
    S.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">The Data Hub</div>
    <hr class="rule" style="margin:22px 0 34px">
    <h2>It arrives in three<br>waves, not one</h2>
    <div style="margin-top:34px">
      <div class="wave"><div class="wave-year">2028</div>
        <div class="wave-text"><b>Importers for distance sales</b> move onto the Hub
          on 1 July.</div></div>
      <div class="wave"><div class="wave-year">2031</div>
        <div class="wave-text">Everyone else <b>may</b> use it, from 1 March.</div></div>
      <div class="wave"><div class="wave-year">2034</div>
        <div class="wave-text">Everyone else <b>must</b> use it, from 1 March.</div></div>
    </div>
    <div class="row" style="margin-top:26px"><div class="row-head">Behind the waves</div>
      <div class="row-body">The Hub must work by 1 June 2028 and fully by 1 February 2034.</div></div>
    <p class="src" style="margin-top:26px">Until 30 June 2028 all goods are still covered by
      a customs declaration.</p>
  </div>
  {f("06")}
</section>""")

    # 7 — e-commerce
    S.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">E-commerce</div>
    <hr class="rule" style="margin:22px 0 34px">
    <h2>Someone has to be<br>the importer</h2>
    <p class="body" style="margin-top:38px">The Regulation puts the customs obligations on a
      named <b style="color:var(--ink)">"importer for distance sales"</b>, so the seller or the
      platform answers to customs rather than the buyer.</p>
    <div class="row" style="margin-top:40px"><div class="row-head">The question for this week</div>
      <div class="row-body">Which entity in your chain is that importer? The answer decides who
        registers, who reports and who pays the fee.</div></div>
    <div class="row"><div class="row-head">And the old Code is gone</div>
      <div class="row-body">The 2013 Union Customs Code is repealed outright, so compliance
        built on it needs rereading against the new text, not patching.</div></div>
  </div>
  {f("07")}
</section>""")

    # 8 — CTA
    S.append(f"""<section class="slide" style="background:#0b0c10">
  <img src="{hero}" style="position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.26">
  <div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(9,12,30,.72),rgba(9,12,30,.92))"></div>
  <div class="pad" style="position:relative;height:100%;display:flex;flex-direction:column;justify-content:center;padding-bottom:120px">
    <div class="overline" style="color:#c9b8ff">Every date here came from the act</div>
    <hr class="rule" style="margin:24px 0 32px">
    <h2 style="color:#fff">Ask Brubru what<br>it means for you</h2>
    <p class="lead" style="color:rgba(255,255,255,.9);margin-top:32px;font-size:46px">
      Chat answers from the act's own articles. Amendator opens all 287 of them.
      My EU Bubble tracks the delegated acts as they arrive.</p>
    <p class="lead" style="color:rgba(255,255,255,.82);margin-top:30px;font-size:40px">
      Read on 22 September 2026 from the consolidated act, Articles 285 to 287 and
      Recital 88. Nothing here is taken from trade press.</p>
    <p class="lead" style="color:rgba(255,255,255,.82);margin-top:26px;font-size:40px">
      This is an explainer, not legal advice. The act runs to 122 recitals and 287
      articles; these eight slides are the parts with a date attached.</p>
    <p class="lead" style="color:#fff;margin-top:46px;font-size:60px;font-weight:600">
      brubru.beresol.eu</p>
  </div>
  {f("08", on_dark=True)}
</section>""")

    html = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
            "<title>The EU has a new Customs Code - Brubru</title>\n"
            f"<style>{CSS}</style>\n</head><body>\n" + "\n".join(S) + "\n</body></html>\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}  ({OUT.stat().st_size/1_000_000:.2f} MB, {len(S)} slides)")

    shots = OUT.parent / (OUT.stem + "_slides")
    if shots.exists():
        shutil.rmtree(shots)
    shots.mkdir(parents=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] playwright missing, nothing measured: the build is NOT done")
        return 1

    pngs: list[Path] = []
    exit_code = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage",
                                          "--no-zygote", "--disable-gpu"])
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.goto(OUT.as_uri())
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(900)
        total = page.locator("section.slide").count()

        # (a) overflow
        over = page.evaluate(
            "Array.from(document.querySelectorAll('section.slide'))"
            ".map((s,i)=>({i:i+1, over: s.scrollHeight - s.clientHeight}))"
            ".filter(x=>x.over>2)")
        if over:
            print(f"[ERROR] {len(over)} of {total} slides OVERFLOW: {over}")
            exit_code = 1
        else:
            print(f"[OK] no overflow on any of {total} slides")

        # (b) computed font-size floor, footer excluded (it has its own floor)
        small = page.evaluate("""
Array.from(document.querySelectorAll('section.slide')).flatMap((s,i)=>
  Array.from(s.querySelectorAll('*')).filter(el=>
    !el.closest('.footer-brand') &&
    el.children.length===0 &&
    (el.textContent||'').trim().length>0 &&
    parseFloat(getComputedStyle(el).fontSize) < 30
  ).map(el=>({slide:i+1, px:Math.round(parseFloat(getComputedStyle(el).fontSize)),
              text:(el.textContent||'').trim().slice(0,40)}))
)""")
        if small:
            print(f"[ERROR] {len(small)} text node(s) below the 30px floor: {small[:6]}")
            exit_code = 1
        else:
            print("[OK] every text node outside the footer is >= 30px")

        # (c) empty-band check
        gaps = page.evaluate("""
Array.from(document.querySelectorAll('section.slide')).map((s,idx)=>{
  const footer = s.querySelector('.footer-brand');
  const blocks = Array.from(s.querySelectorAll('.pad > *, .pad > div > *'))
    .filter(el=>!el.closest('.footer-brand') && el.getBoundingClientRect().height>0);
  const sr = s.getBoundingClientRect();
  const rects = blocks.map(el=>{const r=el.getBoundingClientRect();
    return {top:r.top-sr.top, bottom:r.bottom-sr.top};}).sort((a,b)=>a.top-b.top);
  let maxGap=0, cursor = rects.length ? rects[0].bottom : 0;
  for (const r of rects){ if (r.top>cursor){ const g=r.top-cursor; if(g>maxGap) maxGap=g; }
    cursor = Math.max(cursor, r.bottom); }
  const fr = footer ? footer.getBoundingClientRect() : null;
  const footerGap = fr ? (fr.top - sr.top) - cursor : null;
  return {slide:idx+1, gap:Math.round(maxGap),
          before_footer: fr ? Math.round(footerGap) : null};
})""")
        worst = 0
        for g in gaps:
            bf = g["before_footer"]
            # NOT clamped to 0: a negative value is a real footer OVERLAP and must show.
            if bf is not None and bf < 0:
                print(f"[ERROR] slide {g['slide']}: content OVERLAPS the footer by {-bf}px")
                exit_code = 1
            worst = max(worst, g["gap"], bf if bf and bf > 0 else 0)
        if worst > 120:
            print(f"[ERROR] a gap of {worst}px exceeds the 120px empty-band cap: {gaps}")
            exit_code = 1
        else:
            print(f"[OK] largest gap anywhere: {worst}px (cap 120px)")

        loc = page.locator("section.slide")
        for i in range(total):
            el = loc.nth(i)
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(150)
            png = shots / f"slide_{i+1:02d}.png"
            el.screenshot(path=str(png))
            pngs.append(png)
        browser.close()
    print(f"[OK] captured {len(pngs)} PNGs -> {shots.name}/")

    try:
        from PIL import Image
    except ImportError:
        print("[WARN] Pillow missing, PDF not written")
        return exit_code

    imgs = [Image.open(p).convert("RGB") for p in pngs]
    pdf = OUT.with_suffix(".pdf")
    imgs[0].save(str(pdf), save_all=True, append_images=imgs[1:], resolution=150.0)
    print(f"[OK] {pdf}  ({pdf.stat().st_size/1_000_000:.2f} MB, {len(imgs)} pages)")

    # Phone-scale contact sheet: every slide at 390px wide, which is what Victor sees.
    sheet_w, cols = 390, 4
    thumbs = [im.resize((sheet_w, round(sheet_w * im.height / im.width))) for im in imgs]
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * sheet_w, rows * thumbs[0].height), "#33343a")
    for i, th in enumerate(thumbs):
        sheet.paste(th, ((i % cols) * sheet_w, (i // cols) * thumbs[0].height))
    contact = OUT.with_name(OUT.stem + "_contact_sheet.png")
    sheet.save(contact)
    print(f"[OK] contact sheet at phone scale -> {contact.name}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
