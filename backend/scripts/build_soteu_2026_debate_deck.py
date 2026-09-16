#!/usr/bin/env python3.12
"""Build the 9-slide LinkedIn carousel on the 2026 State of the Union DEBATE.

Companion to build_soteu_2026_deck.py (the speech carousel, published 16 September
2026). Same canvas (1080x1350), same type floor, same footer, same measurement
pass; this file imports those pieces instead of copying them.

Every figure comes from backend/data/soteu_2026/debate_analysis.json and the
knowledge guide soteu_2026_debate.md. Attribution is by political group: the
EP verbatim report was not out, and the source is Brubru's recording of the
English interpretation.

The map PNG (backend/data/soteu_2026/debate_map_europe.png: places named in 4 or more
speeches, bubble area by speech count) was rendered once with d3 and a one-off
script outside the repo; this builder only embeds it. The data folder is not
tracked, so the deck rebuilds only on a machine that has it.

Usage: python3.12 scripts/build_soteu_2026_debate_deck.py
Output: docs/marketing/designs/soteu_2026_debate_deck.html / .pdf / _slides/
"""

from __future__ import annotations

import pathlib
import shutil
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_soteu_2026_deck as base  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(pathlib.Path(__file__).resolve().parents[2] / ".env")
except ImportError:
    pass

ROOT = base.ROOT
DATA = base.DATA
OUT = ROOT / "docs/marketing/designs/soteu_2026_debate_deck.html"

# Stance is ordinal, so it is a diverging scale with a grey midpoint, not a
# categorical palette: supportive and hostile at the poles. Colour-blind
# separation of adjacent steps passes validate_palette.js; every segment count and
# the legend are written out, so colour is never the only carrier.
STANCE = [
    ("supportive", "Supportive", "#0693e3"),
    ("mixed", "Mixed", "#b8bcc6"),
    ("critical", "Critical", "#f2a33a"),
    ("hostile", "Hostile", "#b91c1c"),
]
# (group, supportive, mixed, critical, hostile): debate_analysis.json group_positions
GROUPS = [
    ("EPP", 12, 1, 0, 0),
    ("Renew", 4, 2, 0, 0),
    ("S&amp;D", 5, 6, 3, 0),
    ("Greens/EFA", 1, 2, 3, 0),
    ("The Left", 0, 0, 6, 0),
    ("ECR", 0, 2, 1, 5),
    ("PfE", 0, 0, 1, 9),
    ("ESN", 0, 0, 0, 5),
]

CHIP = {
    "answered": ("ANSWERED", "#059669", "#d1fae5"),
    "skipped": ("NOT ANSWERED", "#b91c1c", "#fee2e2"),
    "welcomed": ("WELCOMED", "#059669", "#d1fae5"),
    "questioned": ("QUESTIONED", "#d97706", "#fef3c7"),
    "objected": ("OBJECTED", "#b91c1c", "#fee2e2"),
    "stated": ("NOT FILED", "#d97706", "#fef3c7"),
    "target": ("TARGET", "#0693e3", "#dbeafe"),
    "proposed": ("PROPOSED", "#0693e3", "#dbeafe"),
}

EXTRA_CSS = """
.sbar-row{display:flex;align-items:center;gap:22px}
.sbar-name{width:292px;flex-shrink:0;font-size:46px;font-weight:600;line-height:1.1}
.sbar{display:flex;gap:3px;height:62px;flex-shrink:0}
.sbar span{display:flex;align-items:center;justify-content:center;font-family:'JetBrains Mono',monospace;
  font-size:32px;font-weight:700;color:#fff}
.sbar span:first-child{border-radius:6px 0 0 6px}.sbar span:last-child{border-radius:0 6px 6px 0}
.sbar span:only-child{border-radius:6px}
.sbar-total{font-family:'JetBrains Mono',monospace;font-size:32px;color:var(--faint)}
.rrow{display:flex;align-items:center;justify-content:space-between;gap:20px;background:#fff;
  border:1px solid var(--line);padding:16px 26px}
.rrow-text{font-size:44px;line-height:1.2;font-weight:600}
.rrow-sub{font-size:38px;line-height:1.25;color:var(--soft);font-weight:400;margin-top:4px}
"""


def chip(key: str) -> str:
    label, fg, bg = CHIP[key]
    return f'<span class="chip" style="color:{fg};background:{bg}">{label}</span>'


def rrow(text: str, key: str, sub: str = "") -> str:
    sub_html = f'<div class="rrow-sub">{sub}</div>' if sub else ""
    return f"""<div class="rrow"><div><div class="rrow-text">{text}</div>{sub_html}</div>{chip(key)}</div>"""


def prow(promise: str, law: str, key: str) -> str:
    return f"""<div class="prow" style="padding:30px 34px">
      <div class="prow-head"><div class="prow-promise">{promise}</div>{chip(key)}</div>
      <div class="prow-law">{law}</div>
    </div>"""


def main() -> int:
    hero = base.data_uri_from_url(base.pexels_src(base.HERO["id"]))
    logo = base.data_uri_from_file(ROOT / "frontend/public/assets/brubru_mainlogo.png")
    beresol = base.data_uri_from_file(ROOT / "frontend/public/assets/beresol-logo_transparent.png")
    brubru_icon = base.data_uri_from_file(ROOT / "frontend/public/assets/brubru_icon_colours.png")
    debate_map = base.data_uri_from_file(DATA / "debate_map_europe.png")

    def f(page: str, **kw) -> str:
        return base.footer(page, **kw).replace("{beresol}", beresol).replace("{brubru_icon}", brubru_icon)

    slides: list[str] = []

    # 01 cover
    slides.append(f"""<section class="slide" style="display:flex;align-items:flex-end;
  background:linear-gradient(180deg,rgba(9,12,30,.38) 0%,rgba(9,16,44,.93) 100%),url('{hero}');
  background-size:cover;background-position:center;color:#fff">
  <img src="{logo}" alt="Brubru" class="chrome" style="position:absolute;top:44px;left:60px;height:76px;width:auto;z-index:5;filter:drop-shadow(0 2px 10px rgba(0,0,0,.45))">
  <div class="pad" style="padding-bottom:140px">
    <div class="overline" style="color:#c9b8ff">State of the Union 2026 &middot; The debate &middot; 16&nbsp;September</div>
    <hr class="rule" style="margin:24px 0 30px;width:130px">
    <h1 style="text-shadow:0 2px 24px rgba(0,0,0,.4)">78 speeches. One reply.</h1>
    <p class="lead" style="color:rgba(255,255,255,.94);margin-top:30px;max-width:21ch">How Parliament&rsquo;s groups answered von der Leyen, and what her reply left out.</p>
  </div>
  {f("01", on_dark=True, credit=f"Photo: {base.HERO['photographer']} / Pexels")}
</section>""")

    # 02 the debate, counted
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">The debate</div>
    <hr class="rule" style="margin:18px 0 28px">
    <h2>Two hours and forty minutes, counted</h2>
    <div style="margin-top:40px;display:grid;gap:26px">
      <div class="stat-row"><span class="stat-num">78</span><span class="stat-label">MEP speeches</span></div>
      <div class="stat-row"><span class="stat-num">9</span><span class="stat-label">blue-card exchanges</span></div>
      <div class="stat-row"><span class="stat-num">1</span><span class="stat-label">reply from von der Leyen</span></div>
    </div>
    <div class="card" style="margin-top:40px;border-left:4px solid var(--purple);padding:24px 30px">
      <p class="body">Brubru recorded and transcribed the English interpretation live. The verbatim report was not out, so speakers are counted by political group.</p>
    </div>
  </div>
  {f("02")}
</section>""")

    # 03 stance by group
    unit = 40
    rows = []
    for name, *counts in GROUPS:
        segs = "".join(
            f'<span style="width:{n * unit}px;background:{STANCE[i][2]};'
            f'color:{"#141414" if STANCE[i][0] in ("mixed", "critical") else "#fff"}">{n if n >= 2 else ""}</span>'
            for i, n in enumerate(counts) if n
        )
        rows.append(f'<div class="sbar-row"><div class="sbar-name">{name}</div>'
                    f'<div class="sbar">{segs}</div><div class="sbar-total">{sum(counts)}</div></div>')
    legend = "".join(
        f'<div class="legend-item"><span class="swatch" style="background:{c};border-radius:4px"></span>{label}</div>'
        for _, label, c in STANCE
    )
    slides.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">Where the groups stood</div>
    <hr class="rule" style="margin:14px 0 18px">
    <h2>23 supportive, 21 hostile</h2>
    <div class="legend" style="margin-top:22px">{legend}</div>
    <div style="margin-top:28px;display:flex;flex-direction:column;gap:18px">{''.join(rows)}</div>
    <p class="body" style="margin-top:26px;font-size:32px;color:var(--faint);line-height:1.3">Speeches per group; stance is Brubru&rsquo;s reading. Not shown: 2 non-attached and 8 unattributed speeches.</p>
  </div>
  {f("03")}
</section>""")

    # 04 cost of living
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">The top complaint</div>
    <hr class="rule" style="margin:16px 0 22px">
    <h2>19 speeches on bills. No measure in the speech.</h2>
    <div style="margin-top:30px;display:flex;flex-direction:column;gap:14px">
      {rrow("Fuel, heating and living costs", "skipped", "Raised by six groups, from S&amp;D and the Greens to PfE and ESN. Not in her reply.")}
    </div>
    <div style="margin-top:22px;display:grid;gap:18px">
      <p class="body"><strong style="color:var(--ink)">The speech</strong> names the cost of living once and proposes nothing on fuel or household energy.</p>
      <p class="body"><strong style="color:var(--ink)">The law today</strong>: the new carbon price on heating and road fuels starts in 2028, a year later than planned. The Social Climate Fund is meant to cushion households.</p>
    </div>
  </div>
  {f("04")}
</section>""")

    # 05 her reply
    slides.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">Her five-minute reply</div>
    <hr class="rule" style="margin:14px 0 18px">
    <h2>What she answered, what she did not</h2>
    <div style="margin-top:24px;display:flex;flex-direction:column;gap:10px">
      {rrow("EU Inc must stay a regulation", "answered")}
      {rrow("New own resources for the budget", "answered")}
      {rrow("The wildfire response", "answered")}
      {rrow("A yes or no on Article&nbsp;42(7) for Cyprus", "skipped")}
      {rrow("Sanctions on Israel", "skipped")}
      {rrow("Fuel prices", "skipped")}
      {rrow("Claims about Hungary", "skipped")}
    </div>
  </div>
  {f("05")}
</section>""")

    # 06 map
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">Where MEPs took the debate</div>
    <hr class="rule" style="margin:14px 0 16px">
    <h2>Ceuta, named in 10 speeches</h2>
    <img src="{debate_map}" alt="Map of Europe: places named in four or more debate speeches" style="width:100%;height:auto;margin-top:22px;display:block;border:1px solid var(--line)">
    <p class="body" style="margin-top:20px">Speeches naming each place. Beyond Europe: Canada 19, the United States 10, China 8.</p>
  </div>
  {f("06")}
</section>""")

    # 07 canada
    slides.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">Canada as an associate member</div>
    <hr class="rule" style="margin:14px 0 18px">
    <h2>Welcomed, but not by all</h2>
    <div style="margin-top:20px;display:flex;flex-direction:column;gap:10px">
      {rrow("EPP, S&amp;D, Renew, Greens/EFA", "welcomed")}
      {rrow("The Irish Council Presidency", "welcomed", "Said it significantly advances EU-Canada relations")}
      {rrow("The Left", "questioned", "&ldquo;Who has given you a democratic mandate?&rdquo;")}
      {rrow("ECR", "objected", "Her bow to Carney &ldquo;embarrassing&rdquo;; why not the UK?")}
    </div>
    <div class="card" style="margin-top:14px;border-left:4px solid var(--purple);padding:14px 26px">
      <p class="body">The Treaties contain no associate-membership status. Quotes: English interpretation.</p>
    </div>
  </div>
  {f("07")}
</section>""")

    # 08 what comes next
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">What to follow</div>
    <hr class="rule" style="margin:16px 0 22px">
    <h2>Three things said in the chamber</h2>
    <div style="margin-top:30px;display:flex;flex-direction:column;gap:20px">
      {prow("A Green Deal committee of inquiry", "The Greens/EFA say they will ask. It needs a quarter of MEPs: 180 of 720.", "stated")}
      {prow("A budget deal by the end of 2026", "The Irish Presidency is confident. It needs every government and Parliament&rsquo;s consent.", "target")}
      {prow("EU Inc", "Tabled as one EU-wide regulation. She warned against 27 national versions.", "proposed")}
    </div>
  </div>
  {f("08")}
</section>""")

    # 09 close
    qrows = "".join(
        f'<div class="trow" style="padding:26px 0"><div class="titem" style="font-size:48px">{q}</div></div>'
        for q in (
            "How did the groups react to the State of the Union?",
            "What did von der Leyen&rsquo;s reply leave unanswered?",
            "What would a Green Deal committee of inquiry need?",
        )
    )
    slides.append(f"""<section class="slide" style="display:flex;flex-direction:column;
  background:linear-gradient(180deg,rgba(9,12,30,.88),rgba(9,16,44,.95)),url('{hero}');
  background-size:cover;background-position:center 20%;color:#fff">
  <div class="pad">
    <div class="overline" style="color:#c9b8ff">Ask Brubru</div>
    <hr class="rule" style="margin:18px 0 22px;width:130px">
    <h2 style="color:#fff;text-shadow:0 2px 18px rgba(0,0,0,.45)">The whole debate, answerable</h2>
    <div style="margin-top:26px">{qrows}</div>
    <div class="card" style="margin-top:26px;background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.28);border-left:4px solid var(--purple);padding:22px 26px">
      <p class="quote" style="color:#fff;font-size:40px">In English, French, Dutch, Spanish, Catalan and Italian.</p>
    </div>
    <p style="margin-top:22px;font-family:'JetBrains Mono',monospace;font-size:56px;font-weight:700;letter-spacing:.01em;color:#fff">brubru.beresol.eu</p>
  </div>
  {f("09", on_dark=True)}
</section>""")

    html = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
            "<title>2026 State of the Union: the debate - Brubru</title>\n"
            f"<style>{base.CSS}{EXTRA_CSS}</style>\n</head><body>\n"
            + "\n".join(slides) + "\n</body></html>\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}  ({OUT.stat().st_size/1_000_000:.2f} MB, {len(slides)} slides)")
    return measure_and_export()


def measure_and_export() -> int:
    """Overflow, type floor and footer-overlap checks, then PNGs and the PDF."""
    from playwright.sync_api import sync_playwright
    from PIL import Image

    shots = OUT.parent / (OUT.stem + "_slides")
    if shots.exists():
        shutil.rmtree(shots)
    shots.mkdir(parents=True)
    code = 0
    pngs = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.goto(OUT.as_uri())
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(900)
        over = page.evaluate("Array.from(document.querySelectorAll('section.slide'))"
                             ".map((s,i)=>({i:i+1, over:s.scrollHeight-s.clientHeight})).filter(x=>x.over>2)")
        total = page.locator("section.slide").count()
        print(f"[{'ERROR' if over else 'OK'}] overflow: {len(over)} of {total} slides clip {over or ''}")
        code |= bool(over)
        # Content must end above the footer: measured, not clamped (the speech deck hid an 8px overlap).
        clash = page.evaluate("""
Array.from(document.querySelectorAll('section.slide')).map((s,i)=>{
  const f=s.querySelector('.footer-brand').getBoundingClientRect();
  const pad=s.querySelector('.pad'); let bottom=0;
  pad.querySelectorAll('*').forEach(el=>{const r=el.getBoundingClientRect(); if(r.height>0) bottom=Math.max(bottom,r.bottom);});
  return {i:i+1, clearance:Math.round(f.top-bottom)};
})""")
        bad = [c for c in clash if c["clearance"] < 12]
        print("[INFO] clearance above footer:", ", ".join(f"{c['i']}:{c['clearance']}px" for c in clash))
        if bad:
            print(f"[ERROR] content touches the footer on {bad}")
            code = 1
        mins = page.evaluate("""
Array.from(document.querySelectorAll('section.slide')).map((s,i)=>{
  const foot=s.querySelector('.footer-brand');
  const sizes=Array.from(s.querySelectorAll('*')).filter(el=>!(foot&&foot.contains(el))&&!el.classList.contains('chrome')
    &&Array.from(el.childNodes).some(n=>n.nodeType===3&&n.textContent.trim())).map(el=>parseFloat(getComputedStyle(el).fontSize));
  return Math.min(...sizes);
})""")
        print("[INFO] smallest text per slide:", ", ".join(f"{i+1}:{m:.0f}px" for i, m in enumerate(mins)))
        if min(mins) < 30:
            print("[ERROR] text below the 30px floor")
            code = 1
        loc = page.locator("section.slide")
        for i in range(total):
            el = loc.nth(i)
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(120)
            png = shots / f"slide_{i+1:02d}.png"
            el.screenshot(path=str(png))
            pngs.append(png)
        browser.close()
    imgs = [Image.open(x).convert("RGB") for x in pngs]
    pdf = OUT.with_suffix(".pdf")
    imgs[0].save(str(pdf), save_all=True, append_images=imgs[1:], resolution=150.0)
    print(f"[OK] {pdf}  ({pdf.stat().st_size/1_000_000:.2f} MB, {len(imgs)} pages)")
    return code


if __name__ == "__main__":
    sys.exit(main())
