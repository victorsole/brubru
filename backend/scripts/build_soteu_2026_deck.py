"""Build the 2026 State of the Union LinkedIn carousel (16 September 2026), v2 large type.

Eleven 1080x1350 slides in the canonical Brubru aesthetic, structurally copied from
scripts/build_juri_eu_inc_deck.py: Adobe Caslon Pro, the blue to purple gradient as a
3px accent rule, light canvas, a Pexels hero on the cover slide, every image embedded
as a base64 data URI so the file converts cleanly, and hard rule #12's Playwright
overflow measurement before the deck is called done.

v2 (16 September 2026, after Victor's "nobody can read them" review of v1): the deck
was rebuilt around a hard type floor, because v1 shipped body text around 17-18px on
a 1080px canvas (about 6px on a phone feed), and more than half of several slides was
empty white space. v2 enforces, in CSS px on the 1080px canvas: slide titles >=80px
(cover >=104px), row headlines >=46px, body text >=38px, labels/chips/legend/footnotes
>=30px, big numbers >=100px. No empty band taller than 120px anywhere. The trade
promise ("signed" free trade agreements, 2 of 5 actually signed) now gets its own
11th slide instead of sharing slide 8 with three other promises, and every table slide
carries at most 3-5 short rows so the type floor still fits the fixed canvas.

Scope: Ursula von der Leyen's 2026 State of the Union address, delivered in Strasbourg
on 16 September 2026. Three sources, all in backend/data/soteu_2026/:

  - speech_en.txt / speech_ov.txt: the published SPEECH text (English and the
    original-version transcript), Commission reference SPEECH/26/1868.
  - promises.json: Brubru's promise ledger, 45 commitments extracted from the speech
    and checked against the law as it stands, bucketed NEW / SCHEDULED / EXISTS /
    PROPOSED (one entry left unverified and excluded from the count of 44).
  - places.json / attributed.md: the place-name count behind slide 3's map and slide
    2's "50 places named" stat.

The copy for every slide is FINAL and fact-checked; it comes from a session content
specification (content_v2.md), not from this script. The only edits this script makes
to that copy are documented removals of fact-free words needed to fit a line, listed in
the session report, never an addition or a rewording of a fact. Verdict/status chip
words (CONFIRMED, ABOVE FIGURE, ROUNDED UP, SIGNED, NOT SIGNED) are presentational UI
labels this script adds for the colour-plus-word accessibility rule, not new facts:
CONFIRMED / ABOVE THE COMMISSION'S FIGURE / ROUNDED UP carry over the exact verdict
categorisation already fact-checked in the v1 content spec.

Hard rule #12 (skills/brubru-design/SKILL.md): every slide is measured for overflow
with Playwright before the deck is called done, because a fixed-canvas slide clips
silently and the screenshot still looks finished. v2 adds two more automated checks
in the same pass: a computed-style font-size floor (every text element outside the
footer must be >=30px, matching the spec) and an empty-band check (no gap between
consecutive content blocks, or between the last block and the footer, taller than
120px).

  /opt/anaconda3/bin/python3.12 backend/scripts/build_soteu_2026_deck.py
"""
from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break it.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])

import base64
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(_REPO_ROOT)
load_dotenv(ROOT / ".env")

OUT = ROOT / "docs/marketing/designs/soteu_2026_deck.html"
DATA = ROOT / "backend/data/soteu_2026"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/151 Safari/537.36"

# The cover hero. Pexels has no genuine interior shot of the Strasbourg hemicycle
# itself (searches for "Strasbourg parliament hemicycle interior", "european
# parliament interior strasbourg session" and "strasbourg parliament debate chamber"
# return Strasbourg EXTERIOR architecture, or other parliaments' chambers: the Dutch,
# Swiss, Norwegian and Turkish assemblies). The one genuine European Parliament
# hemicycle interior on Pexels, and the consistent top result across every query, is
# Jonas Horsch's photo of the Brussels hemicycle. Same institution, same chamber
# design used for SOTEU rehearsals and committee weeks, standard editorial practice
# (the JURI deck used the same Brussels/Strasbourg substitution for the same reason).
# The overline states the true event location, Strasbourg, as text; the credit names
# the photo for what it is, without claiming the building.
HERO = {"id": 11682403, "photographer": "Jonas Horsch"}

# Verdict/status chip words. CONFIRMED / ABOVE THE COMMISSION'S FIGURE / ROUNDED UP
# carry over the exact verdict wording fact-checked in the v1 content spec, kept here
# as compact chip labels per v2's "colour plus the words, never colour alone" rule.
CHIP = {
    "new": ("NEW", "#dc2626", "#fee2e2"),
    "scheduled": ("SCHEDULED", "#d97706", "#fef3c7"),
    "exists": ("EXISTS", "#059669", "#d1fae5"),
    "proposed": ("PROPOSED", "#0693e3", "#dbeafe"),
    "signed": ("SIGNED", "#059669", "#d1fae5"),
    "not_signed": ("NOT SIGNED", "#d97706", "#fef3c7"),
    "confirmed": ("CONFIRMED", "#059669", "#d1fae5"),
    "above": ("HIGHER", "#d97706", "#fef3c7"),
    "rounded": ("ROUNDED UP", "#d97706", "#fef3c7"),
}

THEME = {
    "economy": ("Economy, AI and partners", "#2a78d6"),
    "climate": ("Climate and preparedness", "#eb6834"),
    "security": ("Security, borders and democracy", "#1baf7a"),
}


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


def chip(key: str) -> str:
    label, fg, bg = CHIP[key]
    return f'<span class="chip" style="color:{fg};background:{bg}">{label}</span>'


CSS = """
:root{
  --ink:#141414; --soft:#3d3d3d; --faint:#6b6b6b;
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
.pagenum{font-family:'JetBrains Mono',monospace;font-size:20px;color:var(--faint);letter-spacing:.06em}
h1{font-size:110px;line-height:1.14;font-weight:600;letter-spacing:-.01em}
h2{font-size:84px;line-height:1.16;font-weight:600;letter-spacing:-.01em}
.lead{font-size:42px;line-height:1.3;color:var(--soft)}
.body{color:var(--soft);font-size:40px;line-height:1.3}
.card{background:#fff;border:1px solid var(--line)}
.tag{font-family:'JetBrains Mono',monospace;font-size:32px;letter-spacing:.06em;
  color:var(--faint);text-transform:uppercase}
.quote{font-size:46px;line-height:1.28;font-style:italic;color:var(--ink)}
.quote-sm{font-size:36px;line-height:1.28;font-style:italic;color:var(--ink)}
.chip{display:inline-flex;align-items:center;padding:10px 22px;border-radius:30px;
  font-family:'JetBrains Mono',monospace;font-size:30px;font-weight:700;letter-spacing:.01em;
  text-transform:uppercase;white-space:nowrap;flex-shrink:0}

/* stat rows, slide 2 */
.stat-row{display:flex;align-items:baseline;gap:28px;border-top:4px solid var(--blue);padding-top:14px}
.stat-row:nth-child(2){border-top-color:var(--purple)}
.stat-row:nth-child(3){border-top-color:#1baf7a}
.stat-num{font-size:104px;font-weight:600;line-height:1.05}
.stat-label{font-size:32px;color:var(--faint);font-family:'JetBrains Mono',monospace;
  letter-spacing:.03em;text-transform:uppercase}

/* map legend, slides 3 and 4 */
.legend{display:flex;flex-wrap:wrap;gap:14px 34px;align-items:center}
.legend-item{display:flex;align-items:center;gap:12px;font-size:32px;color:var(--soft)}
.swatch{width:24px;height:24px;border-radius:50%;flex-shrink:0}

/* tracker bars, slide 5 */
.bar-row{background:#fff;border:1px solid var(--line);padding:16px 26px}
.bar-head{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:4px}
.bar-desc{font-size:40px;color:var(--soft)}
.bar-count{font-family:'JetBrains Mono',monospace;font-size:92px;font-weight:700;color:var(--ink)}
.bar-track{height:24px;background:#f0f0f2;border-radius:5px;overflow:hidden}
.bar-fill{height:100%;border-radius:5px}

/* promise rows, slides 6, 7, 9 (3 rows). Row-to-row spacing is a flex `gap` on the
   wrapping container (set per slide in Python), not a margin baked into .prow, so
   short-content slides (6, 7) can be given more breathing room than dense ones (9)
   without a shared CSS rule change perturbing every slide at once. */
.prow{display:flex;flex-direction:column;gap:14px;background:#fff;border:1px solid var(--line);
  padding:26px 30px}
.prow-head{display:flex;align-items:flex-start;justify-content:space-between;gap:20px}
.prow-promise{font-weight:600;font-size:48px;line-height:1.18}
.prow-law{color:var(--soft);font-size:40px;line-height:1.3}

/* partner rows, slide 8 */
.partner-row{display:flex;align-items:center;justify-content:space-between;gap:20px;
  background:#fff;border:1px solid var(--line);padding:10px 24px}
.partner-text{flex:1}
.partner-name{font-weight:600;font-size:46px;line-height:1.18}
.partner-status{color:var(--soft);font-size:38px;line-height:1.25;margin-top:4px}

/* verdict rows, slide 10 */
.vrow{display:flex;flex-direction:column;gap:8px;background:#fff;border:1px solid var(--line);
  padding:22px 26px}
.vrow-figure{font-weight:600;font-size:46px;line-height:1.2}
.vrow-record{display:flex;align-items:center;gap:14px;color:var(--soft);font-size:38px;line-height:1.25}
.vrow-dot{width:20px;height:20px;border-radius:50%;flex-shrink:0}

/* timeline, slide 11 */
.trow{display:flex;gap:30px;padding:16px 0;border-bottom:1px solid rgba(255,255,255,.18);align-items:baseline}
.trow:last-of-type{border-bottom:0}
.tdate{font-family:'JetBrains Mono',monospace;font-size:34px;color:#c9b8ff;letter-spacing:.02em;
  width:250px;flex-shrink:0}
.titem{font-size:40px;line-height:1.28;color:rgba(255,255,255,.94)}

/* footer brand, every slide */
.footer-brand{position:absolute;left:64px;right:64px;bottom:26px;display:flex;
  align-items:center;justify-content:space-between}
.footer-brand-left{display:flex;align-items:center;gap:16px}
.footer-logo{height:62px;width:auto;display:block}
.footer-icon{height:46px;width:auto;display:block}
.footer-by{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:24px;color:var(--faint);letter-spacing:.04em}
.footer-word{font-family:'JetBrains Mono',ui-monospace,monospace;font-size:27px;
  letter-spacing:.03em;color:var(--faint);text-transform:uppercase}
.footer-pill{background:rgba(255,255,255,.94);border-radius:40px;padding:12px 22px}
.footer-pill .footer-word{color:var(--soft)}
.credit{font-size:20px;color:rgba(255,255,255,.75);font-family:ui-sans-serif,system-ui;
  letter-spacing:.01em}
"""


def footer(page: str, *, on_dark: bool = False, credit: str | None = None) -> str:
    """The Beresol-logo footer that appears on every slide (hard rule 7).

    The actual brubru.beresol.eu CTA text is reserved for slide 11 alone, per hard
    rule 6 (single CTA) and the content spec's "the only link in the deck"
    instruction; every other footer carries the brand mark without a URL. This
    entire element is excluded from the v2 30px text-floor check by design (the spec
    sets its own separate floor: footer brand text >=26px, logo >=40px tall).
    """
    left_wrap = "footer-brand-left footer-pill" if on_dark else "footer-brand-left"
    pagenum_style = "color:rgba(255,255,255,.8)" if on_dark else "color:var(--faint)"
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
    logo = data_uri_from_file(ROOT / "frontend/public/assets/brubru_mainlogo.png")
    beresol = data_uri_from_file(ROOT / "frontend/public/assets/beresol-logo_transparent.png")
    brubru_icon = data_uri_from_file(ROOT / "frontend/public/assets/brubru_icon_colours.png")
    map_world = data_uri_from_file(DATA / "map_world_big.png")
    map_europe = data_uri_from_file(DATA / "map_europe_big.png")

    def f(page: str, **kw) -> str:
        return footer(page, **kw).replace("{beresol}", beresol).replace("{brubru_icon}", brubru_icon)

    slides: list[str] = []

    # 01 cover
    slides.append(f"""<section class="slide" style="display:flex;align-items:flex-end;
  background:linear-gradient(180deg,rgba(9,12,30,.38) 0%,rgba(9,16,44,.93) 100%),url('{hero}');
  background-size:cover;background-position:center;color:#fff">
  <img src="{logo}" alt="Brubru" class="chrome" style="position:absolute;top:44px;left:60px;height:76px;width:auto;z-index:5;filter:drop-shadow(0 2px 10px rgba(0,0,0,.45))">
  <div class="pad" style="padding-bottom:140px">
    <div class="overline" style="color:#c9b8ff">State of the Union 2026 &middot; Strasbourg &middot; 16&nbsp;September</div>
    <hr class="rule" style="margin:24px 0 30px;width:130px">
    <h1 style="text-shadow:0 2px 24px rgba(0,0,0,.4)">45 promises. How many are already law?</h1>
    <p class="lead" style="color:rgba(255,255,255,.94);margin-top:30px;max-width:19ch">We checked every commitment in von der Leyen&rsquo;s speech against the law today.</p>
  </div>
  {f("01", on_dark=True, credit=f"Photo: {HERO['photographer']} / Pexels")}
</section>""")

    # 02 the speech
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">The speech</div>
    <hr class="rule" style="margin:18px 0 28px">
    <h2>Strongest, and most precarious</h2>
    <div class="card" style="margin-top:32px;border-left:4px solid var(--purple);padding:26px 30px">
      <p class="quote">&ldquo;The state of our Union is the strongest it has ever been. The state of our Union can also feel as precarious as it has ever been.&rdquo;</p>
    </div>
    <p class="body" style="margin-top:28px">Two tipping points: climate change and AI.</p>
    <div style="margin-top:36px;display:grid;gap:24px">
      <div class="stat-row"><span class="stat-num">7,647</span><span class="stat-label">words</span></div>
      <div class="stat-row"><span class="stat-num">45</span><span class="stat-label">commitments</span></div>
      <div class="stat-row"><span class="stat-num">50</span><span class="stat-label">places named</span></div>
    </div>
  </div>
  {f("02")}
</section>""")

    # 03 world map
    slides.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">Where the speech went</div>
    <hr class="rule" style="margin:16px 0 24px">
    <h2>From Terrace to Tokyo</h2>
    <img src="{map_world}" alt="World map of places named in the speech" style="width:100%;height:auto;margin-top:44px;display:block;border:1px solid var(--line)">
    <div class="legend" style="margin-top:40px">
      <div class="legend-item"><span class="swatch" style="background:{THEME['economy'][1]}"></span>{THEME['economy'][0]}</div>
      <div class="legend-item"><span class="swatch" style="background:{THEME['climate'][1]}"></span>{THEME['climate'][0]}</div>
      <div class="legend-item"><span class="swatch" style="background:{THEME['security'][1]}"></span>{THEME['security'][0]}</div>
      <div class="legend-item">filled dot = city or site</div>
      <div class="legend-item">ring = country or region</div>
    </div>
    <p class="body" style="margin-top:36px">Ukraine is named 14 times, Canada 7, China and Russia 5 each.</p>
  </div>
  {f("03")}
</section>""")

    # 04 europe map
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">Closer to home</div>
    <hr class="rule" style="margin:14px 0 16px">
    <h2>Fires, threats and borders</h2>
    <div style="display:flex;justify-content:center;margin-top:14px">
      <img src="{map_europe}" alt="Map of Europe showing places named in the speech" style="width:712px;height:auto;display:block;border:1px solid var(--line)">
    </div>
    <div style="margin-top:14px;display:grid;gap:8px">
      <p class="body">This summer&rsquo;s fires, from Belgium to Greece.</p>
      <p class="body">Threats in Denmark, Lithuania and Poland.</p>
      <p class="body" style="font-style:italic">&ldquo;Ceuta is Spain. Ceuta is Europe.&rdquo;</p>
    </div>
  </div>
  {f("04")}
</section>""")

    # 05 the tracker
    bars = [
        ("new", "New: no text, no date", 26),
        ("scheduled", "Scheduled: a date, no text", 9),
        ("exists", "Already exists", 6),
        ("proposed", "Proposed: text tabled", 3),
    ]
    max_count = max(b[2] for b in bars)
    bar_rows = []
    for key, desc, count in bars:
        _, fg, _ = CHIP[key]
        pct = max(round(count / max_count * 100), 10)
        bar_rows.append(f"""<div class="bar-row" style="padding:12px 26px">
      <div class="bar-head">
        <span class="bar-desc">{desc}</span>
        <span class="bar-count">{count}</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{fg}"></div></div>
    </div>""")
    slides.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">Promises against the law</div>
    <hr class="rule" style="margin:14px 0 18px">
    <h2>26 of 44 promises have no legal text and no date</h2>
    <div style="margin-top:8px;display:flex;flex-direction:column;gap:10px">{''.join(bar_rows)}</div>
    <p class="body" style="margin-top:8px;font-size:32px;color:var(--faint);line-height:1.3">By Brubru&rsquo;s count. One of 45 commitments could not be verified and is left out.</p>
  </div>
  {f("05")}
</section>""")

    def prow(promise: str, law: str, chip_key: str, *, pad: str = "26px 30px",
             promise_size: int = 48, law_size: int = 40) -> str:
        return f"""<div class="prow" style="padding:{pad}">
      <div class="prow-head">
        <div class="prow-promise" style="font-size:{promise_size}px">{promise}</div>
        {chip(chip_key)}
      </div>
      <div class="prow-law" style="font-size:{law_size}px">{law}</div>
    </div>"""

    # 06 economy and climate (3 rows). Only 3 short rows against the fixed canvas
    # leaves slack once the type floor is met, so these rows use extra card padding
    # (36px vs the 26px default), a moderate row gap and a size step above the floor
    # to close the empty band under the 120px cap without any single row-to-row gap
    # exceeding it either (hard rule 8 / v2 instruction).
    rows6 = [
        prow("A Climate Insurance Alliance", "An EU reinsurance idea is under discussion, not law.", "new", pad="36px 40px"),
        prow("Proposals for a European Firefighting Fleet", "rescEU already has firefighting planes in six Member States.", "new", pad="36px 40px"),
        prow("A European Corporation on Critical Raw Materials", "The 2024 Critical Raw Materials Act already coordinates stockpiling.", "new", pad="36px 40px"),
    ]
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">Economy and climate</div>
    <hr class="rule" style="margin:16px 0 22px">
    <h2>What already exists</h2>
    <div style="margin-top:40px;display:flex;flex-direction:column;gap:28px">{''.join(rows6)}</div>
  </div>
  {f("06")}
</section>""")

    # 07 AI, children and care (3 rows). Shortest row text in the deck: a padding-only
    # fix produced a single row-to-row gap of 158px (over the cap), so this slide
    # instead steps the type up (56px headline, 44px body, both still comfortably
    # above the v2 floor) to fill the row itself rather than the gap between rows,
    # and keeps the row-to-row gap modest.
    rows7 = [
        prow("The EU Kids Act", "Due 17 September. Her outline: no social media under 13.", "scheduled",
             pad="44px 40px", promise_size=64, law_size=50),
        prow("The Digital Fairness Act", "Promised for autumn.", "scheduled",
             pad="44px 40px", promise_size=64, law_size=50),
        prow("A European Care Deal", "No text and no date.", "new",
             pad="44px 40px", promise_size=64, law_size=50),
    ]
    slides.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">AI, children and care</div>
    <hr class="rule" style="margin:16px 0 22px">
    <h2>Dated, and not dated</h2>
    <div style="margin-top:36px;display:flex;flex-direction:column;gap:26px">{''.join(rows7)}</div>
  </div>
  {f("07")}
</section>""")

    # 08 trade (new standalone slide)
    def partner_row(name: str, status: str, chip_key: str) -> str:
        return f"""<div class="partner-row">
      <div class="partner-text">
        <div class="partner-name">{name}</div>
        <div class="partner-status">{status}</div>
      </div>
      {chip(chip_key)}
    </div>"""

    partners = [
        partner_row("Mercosur", "Signed 17 January", "signed"),
        partner_row("Mexico", "Signed 22 May", "signed"),
        partner_row("India", "Negotiations concluded, not signed", "not_signed"),
        partner_row("Australia", "Negotiations concluded, not signed", "not_signed"),
        partner_row("Indonesia", "Negotiations concluded, not signed", "not_signed"),
    ]
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">Trade</div>
    <hr class="rule" style="margin:16px 0 20px">
    <h2>&ldquo;Signed&rdquo; this year: 2&nbsp;of&nbsp;5</h2>
    <div style="margin-top:16px;display:flex;flex-direction:column;gap:10px">{''.join(partners)}</div>
    <div class="card" style="margin-top:14px;border-left:4px solid var(--purple);padding:16px 22px">
      <p class="quote-sm">Her words: &ldquo;This year, we have signed free trade agreements with India, Mercosur, Mexico, Australia and Indonesia.&rdquo;</p>
    </div>
  </div>
  {f("08")}
</section>""")

    # 09 security and borders (3 rows)
    rows9 = [
        prow("Canada as the first associate member of the EU", "No associate-membership status exists in the Treaties.", "new"),
        prow("&ldquo;Europe&rsquo;s own Article 4&rdquo;", "The Treaties already have mutual-assistance and solidarity clauses.", "new"),
        prow("A European Emergency Response Framework for migration", "The Pact&rsquo;s Crisis Regulation has applied since 12 June 2026.", "new"),
    ]
    slides.append(f"""<section class="slide" style="background:#faf9fc">
  <div class="pad">
    <div class="overline">Security and borders</div>
    <hr class="rule" style="margin:16px 0 22px">
    <h2>Where the words run ahead of the law</h2>
    <div style="margin-top:30px;display:flex;flex-direction:column;gap:22px">{''.join(rows9)}</div>
  </div>
  {f("09")}
</section>""")

    # 10 her numbers, checked (5 compact rows)
    def vrow(figure: str, record: str, verdict_key: str) -> str:
        _, fg, _ = CHIP[verdict_key]
        return f"""<div class="vrow" style="padding:11px 22px">
      <div class="vrow-figure">{figure}</div>
      <div class="vrow-record"><span class="vrow-dot" style="background:{fg}"></span>{chip(verdict_key)} {record}</div>
    </div>"""

    rows10 = [
        vrow("&euro;1bn a day deficit with China", "&euro;359.8bn in 2025 (Eurostat)", "confirmed"),
        vrow("A further 35% drop in irregular arrivals", "Detections, January to August (Frontex)", "confirmed"),
        vrow("Almost 1 litre in 4 lost from pipes", "22.9% (EurEau)", "confirmed"),
        vrow("&euro;90bn extra from the Hormuz crisis", "The Commission&rsquo;s own brochure: over &euro;80bn", "above"),
        vrow("Nearly &euro;1bn to rebuild Gaza", "The Commission&rsquo;s figure: &euro;883.6m", "rounded"),
    ]
    slides.append(f"""<section class="slide">
  <div class="pad">
    <div class="overline">Her numbers, checked</div>
    <hr class="rule" style="margin:16px 0 22px">
    <h2>Five figures against the record</h2>
    <div style="margin-top:16px;display:flex;flex-direction:column;gap:10px">{''.join(rows10)}</div>
  </div>
  {f("10")}
</section>""")

    # 11 what to watch (close)
    timeline = [
        ("17 Sep", "EU Kids Act"),
        ("6 Oct", "European product package (planned)"),
        ("20 Oct", "Climate resilience framework, enlargement package, Arctic strategy (planned)"),
        ("28 Oct", "Border and migration package (planned)"),
        ("November", "Industrial AI initiatives"),
        ("Autumn", "Digital Fairness Act"),
        ("Year end", "Quality Jobs Act"),
    ]
    trows = "".join(
        f'<div class="trow"><div class="tdate">{d}</div><div class="titem">{i}</div></div>'
        for d, i in timeline
    )
    slides.append(f"""<section class="slide" style="display:flex;flex-direction:column;
  background:linear-gradient(180deg,rgba(9,12,30,.88),rgba(9,16,44,.95)),url('{hero}');
  background-size:cover;background-position:center 20%;color:#fff">
  <div class="pad">
    <div class="overline" style="color:#c9b8ff">What to watch</div>
    <hr class="rule" style="margin:18px 0 22px;width:130px">
    <h2 style="color:#fff;text-shadow:0 2px 18px rgba(0,0,0,.45)">The calendar she set</h2>
    <div style="margin-top:26px">{trows}</div>
    <div class="card" style="margin-top:26px;background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.28);border-left:4px solid var(--purple);padding:22px 26px">
      <p class="quote" style="color:#fff;font-size:40px">Follow every promise as it becomes law.</p>
    </div>
    <p style="margin-top:22px;font-family:'JetBrains Mono',monospace;font-size:56px;font-weight:700;letter-spacing:.01em;color:#fff">brubru.beresol.eu</p>
  </div>
  {f("11", on_dark=True)}
</section>""")

    html = ('<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
            "<title>2026 State of the Union: 45 promises against the law - Brubru</title>\n"
            f"<style>{CSS}</style>\n</head><body>\n"
            + "\n".join(slides) + "\n</body></html>\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}  ({OUT.stat().st_size/1_000_000:.2f} MB, {len(slides)} slides)")

    # Delete stale slide PNGs so exactly len(slides) remain after this run.
    shots = OUT.parent / (OUT.stem + "_slides")
    if shots.exists():
        shutil.rmtree(shots)
    shots.mkdir(parents=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[ERROR] playwright missing, overflow NOT measured: the build is not done")
        return 1

    pngs: list[Path] = []
    exit_code = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.goto(OUT.as_uri())
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(900)

        # (a) overflow
        over = page.evaluate(
            "Array.from(document.querySelectorAll('section.slide'))"
            ".map((s,i)=>({i:i+1, over: s.scrollHeight - s.clientHeight}))"
            ".filter(x=>x.over>2)"
        )
        total = page.locator("section.slide").count()
        if over:
            print(f"[ERROR] {len(over)} of {total} slides OVERFLOW: {over}")
            exit_code = 1
        else:
            print(f"[OK] overflow: 0 of {total} slides clip")

        # (b) font-size floor, excluding the footer
        font_report = page.evaluate("""
Array.from(document.querySelectorAll('section.slide')).map((s, idx) => {
  const footer = s.querySelector('.footer-brand');
  const nodes = Array.from(s.querySelectorAll('*')).filter(el => {
    if (footer && (el === footer || footer.contains(el))) return false;
    if (el.classList.contains('chrome')) return false;
    return Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
  });
  const sizes = nodes.map(el => parseFloat(getComputedStyle(el).fontSize));
  const minSize = sizes.length ? Math.min(...sizes) : null;
  return {slide: idx + 1, min_font_px: minSize};
});
""")
        min_overall = min(r["min_font_px"] for r in font_report if r["min_font_px"] is not None)
        print("[INFO] min font-size per slide (excluding footer):",
              ", ".join(f"{r['slide']}:{r['min_font_px']:.0f}px" for r in font_report))
        if min_overall < 30:
            print(f"[ERROR] a slide has text below the 30px floor: {min_overall:.0f}px")
            exit_code = 1
        else:
            print(f"[OK] smallest non-footer text across the deck: {min_overall:.0f}px (floor is 30px)")

        # (c) empty-band check: largest vertical gap between stacked content blocks,
        # and between the last block and the footer.
        gap_report = page.evaluate("""
Array.from(document.querySelectorAll('section.slide')).map((s, idx) => {
  const footer = s.querySelector('.footer-brand');
  const els = Array.from(s.querySelectorAll('*')).filter(el => {
    if (footer && (el === footer || footer.contains(el))) return false;
    if (el.classList.contains('chrome')) return false;
    const hasText = Array.from(el.childNodes).some(n => n.nodeType === 3 && n.textContent.trim().length > 0);
    return hasText || el.tagName === 'IMG';
  });
  const rects = els.map(el => el.getBoundingClientRect()).filter(r => r.width > 0 && r.height > 0);
  rects.sort((a, b) => a.top - b.top);
  let maxGap = 0;
  let cursor = rects.length ? rects[0].bottom : 0;
  for (const r of rects) {
    if (r.top > cursor) {
      const gap = r.top - cursor;
      if (gap > maxGap) maxGap = gap;
    }
    cursor = Math.max(cursor, r.bottom);
  }
  const footerRect = footer ? footer.getBoundingClientRect() : null;
  const footerGap = footerRect ? Math.max(0, footerRect.top - cursor) : null;
  return {slide: idx + 1, max_inter_block_gap: Math.round(maxGap), footer_gap: footerRect ? Math.round(footerGap) : null};
});
""")
        print("[INFO] gap report (max inter-block gap / gap before footer):")
        worst = 0
        for r in gap_report:
            g1, g2 = r["max_inter_block_gap"], r["footer_gap"]
            worst = max(worst, g1, g2 or 0)
            print(f"       slide {r['slide']}: inter-block={g1}px, before-footer={g2}px")
        if worst > 120:
            print(f"[ERROR] a gap of {worst}px exceeds the 120px empty-band cap")
            exit_code = 1
        else:
            print(f"[OK] largest gap anywhere in the deck: {worst}px (cap is 120px)")

        slides_loc = page.locator("section.slide")
        for i in range(total):
            el = slides_loc.nth(i)
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

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
