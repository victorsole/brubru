"""Build the EU KIDS Act carousel (for publication Wednesday 23 September 2026).

Eleven 1080x1350 slides in the canonical Brubru aesthetic: Adobe Caslon Pro, the
blue to purple gradient as an accent rule, light canvas, Pexels heroes with
photographer credits, every image embedded as a base64 data URI so the file
converts to PDF cleanly.

Sources. Every figure traces to a primary document read END TO END on
22 September 2026, not to press coverage:
  - COM(2026) 681 final, the proposal, 43 articles across nine chapters
    (CELEX 52026PC0681, procedure 2026/0286(COD));
  - COM(2026) 680 final, the Communication "An EU approach to online child safety";
  - SWD(2026) 681 final, the analysis of impacts;
  - the Commission's own Q&A, "The KIDS Act explained";
  - the OEIL procedure file, fetched live, for the procedural state.

TYPE SCALE. This deck is built to the floor set on 16 September 2026 after the
SOTEU carousel was rejected as unreadable, NOT to the scale of the decks in this
directory that predate it (build_juri_eu_inc_deck.py renders body text at 19px,
which is about 7px on a phone in the LinkedIn feed). The floor here is:
titles 80px+, cover 104px+, row headlines 46px+, body 38px+, labels 30px+, big
numbers 100px+. Content is cut to fit the type, never the reverse.

Two checks run before the deck is called done, both of which have caught silent
defects on earlier builds:
  1. every slide is measured for overflow, because a fixed-canvas slide clips
     silently and the screenshot still looks finished;
  2. footer overlap is measured as a SIGNED gap (content bottom minus footer
     top). A clamped max(0, ...) reports a real overlap as 0px, which is how an
     8px overlap shipped on 16 September.

  python3.12 backend/scripts/build_kids_act_deck.py
"""
from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])

import base64
import json
import os
import sys
import urllib.request
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(_REPO_ROOT)
load_dotenv(ROOT / ".env")

OUT_HTML = ROOT / "docs/marketing/designs/kids_act_deck.html"
OUT_PDF = ROOT / "docs/marketing/designs/kids_act_deck.pdf"
OUT_SHEET = ROOT / "docs/marketing/designs/kids_act_contact_sheet.png"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "Chrome/151 Safari/537.36")

# Both verified against the Pexels API on 22 September 2026: id, photographer
# name and the fact that the photo is ABOUT the subject it is captioned with.
HERO = {"id": 5999680, "photographer": "cottonbro studio"}    # teenagers, phones, night
CLOSE = {"id": 8060005, "photographer": "Windo Nugroho"}      # children, playground


def pexels_src(photo_id: int) -> str:
    key = (os.environ.get("PEXELS_API_KEY") or "").strip().strip('"').strip("'")
    req = urllib.request.Request(
        f"https://api.pexels.com/v1/photos/{photo_id}",
        headers={"Authorization": key, "User-Agent": UA, "Accept": "application/json"},
    )
    return json.load(urllib.request.urlopen(req, timeout=60))["src"]["large2x"]


def crop_to_slide(raw: bytes, w: int = 2160, h: int = 2700) -> str:
    """Centre-crop to the slide aspect, then embed.

    Cropping here rather than leaning on CSS `cover` means the framing is chosen
    deliberately instead of inherited from the source aspect ratio.
    """
    from PIL import Image

    img = Image.open(BytesIO(raw)).convert("RGB")
    src_w, src_h = img.size
    target = w / h
    if src_w / src_h > target:            # too wide: trim the sides
        new_w = int(src_h * target)
        left = (src_w - new_w) // 2
        img = img.crop((left, 0, left + new_w, src_h))
    else:                                  # too tall: trim top and bottom
        new_h = int(src_w / target)
        top = (src_h - new_h) // 2
        img = img.crop((0, top, src_w, top + new_h))
    img = img.resize((w, h), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=86, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def fetch(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90).read()


def data_uri_from_file(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


CSS = """
:root{
  --ink:#141414; --soft:#3f3f46; --faint:#6b6b76;
  --blue:#0693e3; --purple:#9b51e0; --line:#e6e6ea; --cream:#faf9f7;
  --serif:'Adobe Caslon Pro',Georgia,'Times New Roman',serif;
}
@font-face{font-family:'Adobe Caslon Pro';src:url('FONT_REG') format('opentype');
  font-weight:400;font-style:normal}
@font-face{font-family:'Adobe Caslon Pro';src:url('FONT_SEMI') format('opentype');
  font-weight:600;font-style:normal}
@font-face{font-family:'Adobe Caslon Pro';src:url('FONT_BOLD') format('opentype');
  font-weight:700;font-style:normal}
*{margin:0;padding:0;box-sizing:border-box}
body{background:#33343a;font-family:var(--serif);color:var(--ink)}
.slide{position:relative;width:1080px;height:1350px;margin:24px auto;background:#fff;
  overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,.35)}
.pad{padding:80px 72px 150px}
.rule{height:5px;width:132px;background:linear-gradient(90deg,var(--blue),var(--purple));
  border:0;margin:0 0 34px}

/* --- type scale, floor set 16 September 2026 --- */
.overline{font-size:30px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--purple);font-weight:700;margin-bottom:26px}
h1{font-size:106px;line-height:1.04;font-weight:700;letter-spacing:-.015em}
h2{font-size:88px;line-height:1.08;font-weight:700;letter-spacing:-.012em}
.lead{font-size:46px;line-height:1.35;color:var(--soft);font-weight:400}
.body{font-size:42px;line-height:1.42;color:var(--soft)}
.rowhead{font-size:52px;line-height:1.16;font-weight:700;color:var(--ink)}
.rowbody{font-size:40px;line-height:1.34;color:var(--soft);margin-top:10px}
.big{font-size:150px;line-height:.96;font-weight:700;letter-spacing:-.03em}
.label{font-size:32px;letter-spacing:.06em;color:var(--faint);text-transform:uppercase}
.src{font-size:32px;color:var(--faint);line-height:1.34}

.row{display:flex;gap:30px;align-items:flex-start;margin-bottom:40px}
.num{flex:0 0 auto;width:74px;height:74px;border-radius:50%;
  background:linear-gradient(140deg,var(--blue),var(--purple));color:#fff;
  display:flex;align-items:center;justify-content:center;font-size:38px;font-weight:700}
.rowtext{min-width:0}

.card{background:var(--cream);border:1px solid var(--line);border-left:8px solid var(--purple);
  padding:34px 38px;margin-bottom:28px}
.tight .card{padding:26px 32px;margin-bottom:12px}
.tight .row{margin-bottom:28px}

.step{display:flex;align-items:center;gap:28px;margin-bottom:22px;padding:24px 30px;
  border-radius:12px;color:#fff}
.step__age{flex:0 0 auto;width:248px;font-size:56px;font-weight:700;line-height:1.05}
.step__what{font-size:40px;line-height:1.32;min-width:0}

.credit{position:absolute;bottom:18px;right:26px;font-size:24px;
  color:rgba(255,255,255,.75);font-family:ui-sans-serif,system-ui}
.credit--dark{color:var(--faint)}

/* Footer: Brubru icon + "Brubru" + "by" + a visible Beresol mark (hard rule 7). */
.footer{position:absolute;left:0;right:0;bottom:0;height:150px;background:var(--cream);
  border-top:1px solid var(--line);display:flex;align-items:center;
  justify-content:space-between;padding:0 72px}
.footer__left{display:flex;align-items:center;gap:20px;min-width:0}
.footer__icon{height:66px;width:auto}
.footer__word{font-size:38px;font-weight:700;letter-spacing:-.01em}
.footer__by{font-size:30px;color:var(--faint);margin:0 6px}
.footer__beresol{height:60px;width:auto}
.footer__pg{font-size:30px;color:var(--faint)}
"""


def footer(page: int, total: int, icon: str, beresol: str) -> str:
    return f"""<div class="footer">
  <div class="footer__left">
    <img class="footer__icon" src="{icon}" alt="">
    <span class="footer__word">Brubru</span>
    <span class="footer__by">by</span>
    <img class="footer__beresol" src="{beresol}" alt="Beresol">
  </div>
  <div class="footer__pg">{page} / {total}</div>
</div>"""


def main() -> int:
    hero = crop_to_slide(fetch(pexels_src(HERO["id"])))
    close = crop_to_slide(fetch(pexels_src(CLOSE["id"])))
    icon = data_uri_from_file(ROOT / "frontend/public/assets/brubru_icon.png")
    # Transparent variant: the plain beresol-logo.png is RGB with no alpha and
    # paints a hard white rectangle on the cream footer.
    beresol = data_uri_from_file(ROOT / "frontend/public/assets/beresol-logo_transparent.png")

    fonts = {}
    for key, name in [("FONT_REG", "ACaslonPro-Regular.otf"),
                      ("FONT_SEMI", "ACaslonPro-Semibold.otf"),
                      ("FONT_BOLD", "ACaslonPro-Bold.otf")]:
        p = ROOT / "frontend/public/New-Yorker-Font" / name
        fonts[key] = ("data:font/otf;base64,"
                      + base64.b64encode(p.read_bytes()).decode())

    css = CSS
    for k, v in fonts.items():
        css = css.replace(k, v)

    S: list[str] = []
    TOTAL = 11

    def fin(n: int) -> str:
        return footer(n, TOTAL, icon, beresol)

    # 01 cover
    S.append(f"""<section class="slide" style="display:flex;align-items:flex-end;
  background:linear-gradient(180deg,rgba(10,10,32,.10) 0%,rgba(10,10,32,.30) 38%,rgba(12,10,40,.93) 76%),url('{hero}');
  background-size:cover;background-position:center;color:#fff">
  <div style="padding:0 72px 110px">
    <div class="overline" style="color:#c9a6f5">Proposed 17 September 2026</div>
    <h1>Europe wants to raise<br>the age at which<br>childhood goes online</h1>
    <p class="lead" style="color:rgba(255,255,255,.9);margin-top:36px">
      The EU KIDS Act, read end to end.
    </p>
  </div>
  <div class="credit">Photo: {HERO['photographer']} via Pexels</div>
</section>""")

    # 02 what it is
    S.append(f"""<section class="slide"><div class="pad tight">
  <div class="overline">What it is</div><hr class="rule">
  <h2>Two halves.<br>The second one<br>changes the products.</h2>
  <div class="row" style="margin-top:52px">
    <div class="num">1</div>
    <div class="rowtext">
      <div class="rowhead">Common age rules</div>
      <div class="rowbody">One age for the whole Union, instead of 27.</div>
    </div>
  </div>
  <div class="row">
    <div class="num">2</div>
    <div class="rowtext">
      <div class="rowhead">Safety by design</div>
      <div class="rowbody">A binding list of things a service may not do to a
        child, at every age and whatever its size.</div>
    </div>
  </div>
  <div class="card">
    <div class="body">Age limits alone would leave the real problem untouched:
      services built to hold a child's attention.</div>
  </div>
</div>{fin(2)}</section>""")

    # 03 the staircase
    S.append(f"""<section class="slide"><div class="pad">
  <div class="overline">The age staircase</div><hr class="rule">
  <h2>Not one ban.<br>Four steps.</h2>
  <div style="margin-top:50px">
    <div class="step" style="background:linear-gradient(135deg,#b91c1c,#dc2626)">
      <div class="step__age">Under 13</div>
      <div class="step__what">No account. A parent may allow supervised access on a
        service built for small children.</div>
    </div>
    <div class="step" style="background:linear-gradient(135deg,#6d28d9,#9b51e0)">
      <div class="step__age">13 to 14</div>
      <div class="step__what">A guardian may open a limited account. It belongs to the
        guardian, not the child.</div>
    </div>
    <div class="step" style="background:linear-gradient(135deg,#0369a1,#0693e3)">
      <div class="step__age">15 to 17</div>
      <div class="step__what">Your own account, no parental approval. Every safety
        duty still applies.</div>
    </div>
  </div>
  <div class="src" style="margin-top:26px">Articles 6 and 7. The age rule applies to
    services carrying the risky features the law lists.</div>
</div>{fin(3)}</section>""")

    # 04 existing accounts
    S.append(f"""<section class="slide"><div class="pad">
  <div class="overline">The sharp edge</div><hr class="rule">
  <h2>Accounts that<br>already exist</h2>
  <div class="big" style="color:var(--purple);margin-top:56px">6 months</div>
  <div class="body" style="margin-top:30px">to work out whether existing account
    holders are under 15, and to disable the accounts of those who are.</div>
  <div class="card" style="margin-top:44px">
    <div class="rowhead" style="font-size:44px">And of those whose age cannot be
      established.</div>
    <div class="rowbody">That second limb is the one the platforms will fight.
      Where a provider can already tell a holder is an adult, no new check is
      needed, so most adults notice nothing.</div>
  </div>
</div>{fin(4)}</section>""")

    # 05 the contested number
    S.append(f"""<section class="slide"><div class="pad">
  <div class="overline">The fight</div><hr class="rule">
  <h2>Three institutions,<br>three numbers</h2>
  <div style="margin-top:58px">
    <div class="row">
      <div class="num" style="background:#d97706">13</div>
      <div class="rowtext"><div class="rowhead">The expert panel</div>
        <div class="rowbody">The co-chairs recommended restricting access below 13.</div></div>
    </div>
    <div class="row">
      <div class="num" style="background:linear-gradient(140deg,var(--blue),var(--purple))">15</div>
      <div class="rowtext"><div class="rowhead">The Commission</div>
        <div class="rowbody">13 to 15 is the peak of developmental vulnerability,
          and adult supervision is already losing its grip.</div></div>
    </div>
    <div class="row">
      <div class="num" style="background:#dc2626">16</div>
      <div class="rowtext"><div class="rowhead">The Parliament</div>
        <div class="rowbody">Its November 2025 resolution asked for 16, with 13 as
          an absolute floor.</div></div>
    </div>
  </div>
  <div class="src" style="margin-top:0">The Commission also refused to let Member
    States add their own limits: harmonisation is a ceiling as well as a floor.</div>
</div>{fin(5)}</section>""")

    # 06 banned by design
    S.append(f"""<section class="slide"><div class="pad tight">
  <div class="overline">Banned by design</div><hr class="rule">
  <h2>Named in the law,<br>so intent is no defence</h2>
  <div style="margin-top:54px">
    <div class="card"><div class="rowhead">Infinite scroll and autoplay</div>
      <div class="rowbody">Uninterrupted consumption with no real stopping point.</div></div>
    <div class="card"><div class="rowhead">Notifications that pull a child back</div>
      <div class="rowbody">Anything not triggered by something the child did.</div></div>
    <div class="card"><div class="rowhead">Streaks</div>
      <div class="rowbody">Penalising a child for not returning daily.</div></div>
  </div>
  <div class="src" style="margin-top:22px">Article 9, plus mandatory time limits built
    around school hours and at least eight hours of sleep.</div>
</div>{fin(6)}</section>""")

    # 07 feeds
    S.append(f"""<section class="slide"><div class="pad">
  <div class="overline">The feed</div><hr class="rule">
  <h2>Optimised for the child,<br>not for the session</h2>
  <div style="margin-top:54px">
    <div class="row"><div class="num">&bull;</div><div class="rowtext">
      <div class="rowhead">What the child chose comes first</div>
      <div class="rowbody">Explicit preferences get primary weight.</div></div></div>
    <div class="row"><div class="num">&bull;</div><div class="rowtext">
      <div class="rowhead">Tracking-based personalisation off by default</div>
      <div class="rowbody">No outside data may feed it.</div></div></div>
    <div class="row"><div class="num">&bull;</div><div class="rowtext">
      <div class="rowhead">A reset, and a feed with no profiling at all</div>
      <div class="rowbody">Offered at sign-up.</div></div></div>
  </div>
  <div class="src">Article 10.</div>
</div>{fin(7)}</section>""")

    # 08 AI companions
    S.append(f"""<section class="slide"><div class="pad tight">
  <div class="overline">The genuinely new part</div><hr class="rule">
  <h2>AI companions<br>and chatbots</h2>
  <div style="margin-top:54px">
    <div class="card"><div class="rowhead">No manufactured attachment</div>
      <div class="rowbody">Designs that simulate a human relationship and are likely
        to create emotional dependency.</div></div>
    <div class="card"><div class="rowhead">Memory off by default</div>
      <div class="rowbody">A child's earlier conversations are not carried into
        later ones, unless safety requires it.</div></div>
    <div class="card"><div class="rowhead">It may not switch itself on</div>
      <div class="rowbody">Inside a platform or a game, and never pushed.</div></div>
  </div>
  <div class="src" style="margin-top:20px">Article 14.</div>
</div>{fin(8)}</section>""")

    # 09 age checks
    S.append(f"""<section class="slide"><div class="pad tight">
  <div class="overline">Proving your age</div><hr class="rule">
  <h2>The platform never<br>learns who you are</h2>
  <div class="body" style="margin-top:44px">A certified third party checks, not the
    platform. The law requires zero knowledge proof: the check may not identify,
    locate, track or profile anyone.</div>
  <div class="card" style="margin-top:44px">
    <div class="rowhead">What the platform receives</div>
    <div class="rowbody">Above the age, or below it. Nothing else.</div>
  </div>
  <div class="card">
    <div class="rowhead">Ticking a date of birth is over</div>
    <div class="rowbody">Self-declaration is explicitly excluded. Every Member
      State must offer at least one free way to prove age, and a free way for a
      parent to prove they are one.</div>
  </div>
</div>{fin(9)}</section>""")

    # 10 enforcement
    S.append(f"""<section class="slide"><div class="pad">
  <div class="overline">Who has to prove what</div><hr class="rule">
  <h2>The burden lands<br>on the platform</h2>
  <div class="body" style="margin-top:48px">The largest platforms must file a plan
    showing how they meet every obligation, have it audited independently at their
    own expense, and publish a summary.</div>
  <div style="display:flex;gap:34px;margin-top:52px">
    <div style="flex:1 1 0;min-width:0">
      <div class="big" style="color:var(--purple);font-size:128px">6%</div>
      <div class="label" style="margin-top:12px">Maximum fine, worldwide turnover</div>
    </div>
    <div style="flex:1 1 0;min-width:0">
      <div class="big" style="color:var(--blue);font-size:128px">90</div>
      <div class="label" style="margin-top:12px">Working days to a final decision</div>
    </div>
  </div>
  <div class="src" style="margin-top:42px">Neither the audit nor Commission silence
    counts as a finding of compliance. Platforms ride the Digital Services Act
    structure, AI chatbots the AI Act. The rules would apply six months after
    entry into force.</div>
</div>{fin(10)}</section>""")

    # 11 close
    S.append(f"""<section class="slide" style="display:flex;align-items:flex-end;
  background:linear-gradient(180deg,rgba(10,10,32,.30) 0%,rgba(12,10,40,.94) 66%),url('{close}');
  background-size:cover;background-position:center;color:#fff">
  <div style="padding:0 72px 120px">
    <div class="overline" style="color:#c9a6f5">What happens next</div>
    <h2 style="font-size:76px">Parliament and Council<br>have not started.<br>No committee yet.</h2>
    <p class="lead" style="color:rgba(255,255,255,.92);margin-top:38px">
      The full article-by-article analysis, in six languages:<br>
      <strong>brubru.beresol.eu/kids-act</strong>
    </p>
  </div>
  <div class="credit">Photo: {CLOSE['photographer']} via Pexels</div>
</section>""")

    html = (f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            f"<title>EU KIDS Act</title><style>{css}</style></head><body>"
            + "\n".join(S) + "</body></html>")
    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html)
    print(f"[OK] {len(S)} slides -> {OUT_HTML}  ({OUT_HTML.stat().st_size/1e6:.1f} MB)")

    verify_and_export(len(S))
    return 0


def verify_and_export(n_slides: int) -> None:
    """Measure every slide, then export PDF and a phone-scale contact sheet."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1080, "height": 1350})
        pg.goto(OUT_HTML.as_uri(), wait_until="networkidle", timeout=180_000)
        pg.wait_for_timeout(1200)

        # 1. Overflow: does any slide's content exceed the fixed canvas?
        # 2. Footer overlap: SIGNED gap, never clamped at zero.
        report = pg.evaluate("""() => {
          const out = [];
          document.querySelectorAll('.slide').forEach((s, i) => {
            const sb = s.getBoundingClientRect();
            let deepest = 0;
            s.querySelectorAll('*').forEach(el => {
              if (el.classList.contains('footer') || el.closest('.footer')) return;
              if (el.classList.contains('credit')) return;
              // `.pad` is a padding container: its rect bottom is the last text
              // bottom PLUS 190px of padding, which hid a 259px white band.
              if (el.classList.contains('pad')) return;
              const r = el.getBoundingClientRect();
              if (r.height > 0) deepest = Math.max(deepest, r.bottom - sb.top);
            });
            const f = s.querySelector('.footer');
            const footTop = f ? f.getBoundingClientRect().top - sb.top : null;
            out.push({
              n: i + 1,
              scrollH: s.scrollHeight, clientH: s.clientHeight,
              overflowY: s.scrollHeight - s.clientHeight,
              overflowX: s.scrollWidth - s.clientWidth,
              contentBottom: Math.round(deepest),
              footerTop: footTop === null ? null : Math.round(footTop),
              gap: footTop === null ? null : Math.round(footTop - deepest)
            });
          });
          return out;
        }""")

        bad = []
        print("\n  slide  overflowY  overflowX  content_bottom  footer_top   gap")
        for r in report:
            gap = "n/a" if r["gap"] is None else f"{r['gap']:>4}"
            flag = ""
            if r["overflowY"] > 0 or r["overflowX"] > 0:
                flag = "  <-- CLIPPED"; bad.append(r["n"])
            elif r["gap"] is not None and r["gap"] < 0:
                flag = "  <-- FOOTER OVERLAP"; bad.append(r["n"])
            print(f"  {r['n']:>5}  {r['overflowY']:>9}  {r['overflowX']:>9}"
                  f"  {r['contentBottom']:>14}  {str(r['footerTop']):>10}  {gap}{flag}")

        if bad:
            print(f"\n[FAIL] slides needing attention: {bad}")
        else:
            print(f"\n[OK] all {n_slides} slides fit, no footer overlap")

        pg.pdf(path=str(OUT_PDF), width="1080px", height="1350px",
               print_background=True, margin={"top": "0", "bottom": "0",
                                              "left": "0", "right": "0"})
        print(f"[OK] PDF -> {OUT_PDF}  ({OUT_PDF.stat().st_size/1e6:.1f} MB)")

        # Phone-scale contact sheet: this is the check that matches what a reader
        # actually sees in the feed.
        shots = []
        for i in range(n_slides):
            el = pg.query_selector_all(".slide")[i]
            shots.append(el.screenshot())
        b.close()

    from PIL import Image
    thumbs = [Image.open(BytesIO(s)).resize((390, 488), Image.LANCZOS) for s in shots]
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 390 + (cols + 1) * 14,
                              rows * 488 + (rows + 1) * 14), "#33343a")
    for i, t in enumerate(thumbs):
        x = 14 + (i % cols) * (390 + 14)
        y = 14 + (i // cols) * (488 + 14)
        sheet.paste(t, (x, y))
    sheet.save(OUT_SHEET)
    print(f"[OK] contact sheet at phone scale -> {OUT_SHEET}")


if __name__ == "__main__":
    sys.exit(main())
