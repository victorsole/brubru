"""Build the Cyber Resilience Act /lawdrop deck.

Seven 1280x720 slides in the canonical Brubru aesthetic, copied structurally
from docs/marketing/designs/ppwr_deck.html: Adobe Caslon Pro, the blue to purple
gradient as a 3px accent rule, light canvas, Pexels heroes with photographer
credits, every image embedded as a base64 data URI so the file converts.

Every date and figure comes from Regulation (EU) 2024/2847 read directly, and
from the Commission FAQ v1.0 of 3 December 2025.

  python3.12 scripts/build_cra_deck.py
"""
from __future__ import annotations

import base64
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path("/Users/victorsole/Documents/GitHub/brubru")
load_dotenv(ROOT / ".env")

OUT = ROOT / "docs/marketing/designs/cra_deck.html"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36"

# Chosen from the Pexels landscape search; ids pinned so the deck is reproducible.
# The first pick, a bright green circuit board (18372332), rendered loud and
# fought the blue-to-purple brand palette. The monochrome board sits back and
# lets the gradient rule and the type carry the slide.
HERO = {"id": 3520692, "photographer": "Miguel A. Padrinan"}   # circuit board, monochrome
CLOSE = {"id": 18071864, "photographer": "Jaycee300s"}         # home router / connected devices


def pexels_src(photo_id: int) -> str:
    key = (os.environ.get("PEXELS_API_KEY") or "").strip()
    req = urllib.request.Request(
        f"https://api.pexels.com/v1/photos/{photo_id}",
        headers={"Authorization": key, "User-Agent": UA, "Accept": "application/json"},
    )
    import json
    data = json.load(urllib.request.urlopen(req, timeout=60))
    return data["src"]["large2x"]


def data_uri_from_url(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=90).read()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def data_uri_from_file(path: Path) -> str:
    raw = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode()


def main() -> int:
    hero = data_uri_from_url(pexels_src(HERO["id"]))
    close = data_uri_from_url(pexels_src(CLOSE["id"]))
    logo = data_uri_from_file(ROOT / "frontend/public/assets/brubru_mainlogo.png")
    beresol = data_uri_from_file(ROOT / "frontend/public/assets/beresol-logo.png")

    css = """
:root{
  --ink:#141414; --soft:#4a4a4a; --faint:#7a7a7a;
  --blue:#0693e3; --purple:#9b51e0; --line:#e6e6ea;
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
.credit.dark{color:var(--faint)}
.pagenum{position:absolute;bottom:26px;left:64px;font-size:12px;color:var(--faint);
  font-family:'JetBrains Mono',monospace;letter-spacing:.1em}
h1{font-size:60px;line-height:1.08;font-weight:600;letter-spacing:-.01em}
h2{font-size:42px;line-height:1.12;font-weight:600;letter-spacing:-.01em}
.lead{font-size:22px;line-height:1.5;color:var(--soft);max-width:40ch}
.tl{display:grid;grid-template-columns:1fr;gap:0;align-items:start}
.tl .d{font-family:'JetBrains Mono',monospace;font-size:15px;font-weight:600;letter-spacing:.04em}
.tl .b{padding:6px 0 30px 24px;border-left:2px solid var(--line);margin-left:6px}
"""

    def slide1() -> str:
        return f"""<section class="slide" style="display:flex;align-items:flex-end;
  background:linear-gradient(180deg,rgba(9,12,30,.20) 0%,rgba(9,16,44,.88) 100%),url('{hero}');
  background-size:cover;background-position:center;color:#fff">
  <img src="{logo}" alt="Brubru" style="position:absolute;top:44px;left:60px;height:72px;width:auto;z-index:5;filter:drop-shadow(0 2px 10px rgba(0,0,0,.45))">
  <div class="pad" style="padding-bottom:104px">
    <div class="overline" style="color:#c9b8ff">EU Cybersecurity Law &middot; Regulation (EU) 2024/2847</div>
    <hr class="rule" style="margin:20px 0 26px;width:110px">
    <h1 style="max-width:14ch;text-shadow:0 2px 20px rgba(0,0,0,.35)">The Cyber Resilience Act starts biting on 11 September 2026</h1>
    <p class="lead" style="color:rgba(255,255,255,.9);margin-top:26px;max-width:34ch">Most of the Regulation waits until December 2027. The reporting duty does not, and it reaches the products you have already sold.</p>
  </div>
  <div class="credit">Photo: {HERO['photographer']} / Pexels</div>
  <div class="pagenum" style="color:rgba(255,255,255,.7)">01</div>
</section>"""

    def slide2() -> str:
        return """<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">What the Regulation does</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:18ch">Cybersecurity stops being good practice and becomes a condition of sale</h2>
    <div style="display:grid;grid-template-columns:1fr;gap:34px;margin-top:56px">
      <div><div style="font-size:44px;font-weight:600;color:var(--blue)">Any product with digital elements</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:8px">Hardware and software, finished goods and components. A chip and an operating system are in scope, not only the smartphone they sit in.</p></div>
      <div><div style="font-size:44px;font-weight:600;color:var(--purple)">Secure by default</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:8px">No shipping "password" as the default password. Access control, cryptography and automatic security updates become essential requirements.</p></div>
      <div><div style="font-size:44px;font-weight:600;color:var(--blue)">A stated support period</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:8px">You must state how long you will maintain the product, and then handle vulnerabilities for that whole period.</p></div>
    </div>
  </div>
  <div class="pagenum">02</div>
</section>"""

    def slide3() -> str:
        return """<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">The date that matters</div>
    <hr class="rule" style="margin:18px 0 34px">
    <div style="display:flex;align-items:baseline;gap:22px">
      <div style="font-size:104px;line-height:.94;font-weight:600;letter-spacing:-.02em">11 September</div>
      <div style="font-size:56px;font-weight:600;color:var(--purple)">2026</div>
    </div>
    <p class="lead" style="margin-top:28px;max-width:44ch">Article 14 starts applying. From that day a manufacturer that becomes aware of an actively exploited vulnerability, or of a severe incident affecting the security of its product, must notify it.</p>
    <div style="display:grid;grid-template-columns:1fr;gap:22px;margin-top:44px">
      <div style="border-top:3px solid var(--blue);padding-top:14px">
        <div style="font-size:40px;font-weight:600">24 hours</div>
        <p style="color:var(--soft);font-size:17px;line-height:1.4;margin-top:6px">Early warning, from becoming aware.</p></div>
      <div style="border-top:3px solid var(--purple);padding-top:14px">
        <div style="font-size:40px;font-weight:600">72 hours</div>
        <p style="color:var(--soft);font-size:17px;line-height:1.4;margin-top:6px">The notification itself, with what is known and what users can do.</p></div>
      <div style="border-top:3px solid var(--blue);padding-top:14px">
        <div style="font-size:40px;font-weight:600">14 days</div>
        <p style="color:var(--soft);font-size:17px;line-height:1.4;margin-top:6px">Final report, once a corrective measure exists.</p></div>
    </div>
    <p style="color:var(--faint);font-size:16px;margin-top:30px">To the coordinating national CSIRT and to ENISA at the same time, through a single reporting platform.</p>
  </div>
  <div class="pagenum">03</div>
</section>"""

    def slide4() -> str:
        return """<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">How it phases in</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:18ch">One Regulation, four dates</h2>
    <div style="margin-top:44px">
      <div class="tl"><div class="d" style="color:var(--faint)">11 June 2026</div>
        <div class="b"><strong style="font-size:20px">Already applying.</strong>
          <span style="color:var(--soft);font-size:19px">Member States designate the authorities that assess and notify conformity assessment bodies.</span></div></div>
      <div class="tl"><div class="d" style="color:var(--blue)">11 September 2026</div>
        <div class="b"><strong style="font-size:20px">Reporting starts.</strong>
          <span style="color:var(--soft);font-size:19px">Actively exploited vulnerabilities and severe incidents, on the 24 hour clock, for your whole portfolio.</span></div></div>
      <div class="tl"><div class="d" style="color:var(--purple)">11 December 2027</div>
        <div class="b"><strong style="font-size:20px">The Regulation applies in full.</strong>
          <span style="color:var(--soft);font-size:19px">Essential requirements, conformity assessment, CE marking, technical documentation, market surveillance.</span></div></div>
      <div class="tl"><div class="d" style="color:var(--faint)">11 June 2028</div>
        <div class="b" style="border-left:2px solid transparent"><strong style="font-size:20px">Old certificates expire.</strong>
          <span style="color:var(--soft);font-size:19px">Cybersecurity certificates issued under other EU legislation stop being valid, if they have not lapsed sooner.</span></div></div>
    </div>
  </div>
  <div class="pagenum">04</div>
</section>"""

    def slide5() -> str:
        return """<section class="slide" style="background:#faf9fc">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:var(--blue)">The part that catches people</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:16ch">It applies to products you have already sold</h2>
    <div style="display:grid;grid-template-columns:1fr;gap:26px;margin-top:44px">
      <div style="background:#fff;border:1px solid var(--line);padding:30px 32px">
        <div style="font-family:'JetBrains Mono',monospace;font-size:13px;letter-spacing:.14em;color:var(--faint);text-transform:uppercase">The general rule</div>
        <p style="font-size:20px;line-height:1.5;margin-top:14px;color:var(--soft)">Products placed on the market before 11 December 2027 are only caught if they are substantially modified after that date.</p>
        <p style="font-size:19px;line-height:1.5;margin-top:14px;color:var(--soft)">Read that alone and the Regulation looks like a 2027 problem.</p>
      </div>
      <div style="background:#fff;border:1px solid var(--line);border-left:3px solid var(--purple);padding:30px 32px">
        <div style="font-family:'JetBrains Mono',monospace;font-size:13px;letter-spacing:.14em;color:var(--purple);text-transform:uppercase">The exception</div>
        <p style="font-size:20px;line-height:1.5;margin-top:14px;color:var(--soft)">For the reporting duty, that carve-out is expressly switched off. From 11 September 2026 it covers every in-scope product you have placed on the market.</p>
        <p style="font-size:19px;line-height:1.5;margin-top:14px;color:var(--soft)">For those older products you must notify, but you are not required to run full vulnerability handling on code you can no longer build.</p>
      </div>
    </div>
    <p style="color:var(--faint);font-size:16px;margin-top:34px">Regulation (EU) 2024/2847, Article 69(2) and (3). The limit on older products is set out in the Commission FAQ, version 1.0 of 3 December 2025.</p>
  </div>
  <div class="pagenum">05</div>
</section>"""

    def slide6() -> str:
        return """<section class="slide">
  <div class="pad" style="height:100%;display:flex;flex-direction:column;justify-content:center">
    <div class="overline">Who carries it</div>
    <hr class="rule" style="margin:18px 0 30px">
    <h2 style="max-width:17ch">The duty follows the name on the product</h2>
    <div style="display:grid;grid-template-columns:1fr;gap:24px;margin-top:44px">
      <div><div style="font-size:22px;font-weight:600;color:var(--blue)">Manufacturers</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:6px">Design and build to the essential requirements, run the conformity assessment, declare conformity, state a support period, handle vulnerabilities, and report.</p></div>
      <div><div style="font-size:22px;font-weight:600;color:var(--purple)">Importers and distributors</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:6px">Verify before you place a product on the market. Put your own name on it, or modify it, and you take on the manufacturer's obligations in full.</p></div>
      <div><div style="font-size:22px;font-weight:600;color:var(--blue)">Open source stewards</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:6px">A lighter regime, and no administrative fines for any infringement of the Regulation.</p></div>
      <div><div style="font-size:22px;font-weight:600;color:var(--purple)">Smaller companies</div>
        <p style="color:var(--soft);font-size:18px;line-height:1.45;margin-top:6px">Microenterprises and small enterprises are not fined for missing the 24 hour early warning. Every other duty still applies.</p></div>
    </div>
    <div style="margin-top:36px;border-top:1px solid var(--line);padding-top:22px;display:grid;grid-template-columns:1fr;gap:18px">
      <div><div style="font-size:34px;font-weight:600">15m euro or 2,5%</div>
        <p style="color:var(--faint);font-size:16px;margin-top:4px">of worldwide turnover, whichever is higher, for the essential requirements and for Articles 13 and 14.</p></div>
      <div><div style="font-size:34px;font-weight:600">Ex post</div>
        <p style="color:var(--faint);font-size:16px;margin-top:4px">No pre-approval. You place the product on the market on your own responsibility, and Member States enforce.</p></div>
    </div>
  </div>
  <div class="pagenum">06</div>
</section>"""

    def slide7() -> str:
        return f"""<section class="slide" style="display:flex;flex-direction:column;
  background:linear-gradient(180deg,rgba(9,12,30,.52),rgba(9,16,44,.88)),url('{close}');
  background-size:cover;background-position:center;color:#fff">
  <div class="pad" style="flex:1;display:flex;flex-direction:column;justify-content:center">
    <div class="overline" style="color:#c9b8ff">Be ready for 11 September 2026</div>
    <hr class="rule" style="margin:20px 0 24px;width:110px">
    <h2 style="font-size:46px;max-width:15ch;text-shadow:0 2px 20px rgba(0,0,0,.35)">Check your products against the Regulation, obligation by obligation</h2>
    <p class="lead" style="color:rgba(255,255,255,.9);margin-top:22px;max-width:36ch">
      Brubru&rsquo;s EU Law Comply reads your documentation against the Cyber Resilience Act&rsquo;s duties and shows you the gaps, with the article and the date each one binds.</p>
  </div>
  <div style="background:#fff;color:var(--ink);padding:22px 64px;display:flex;align-items:center;justify-content:space-between">
    <div style="display:flex;align-items:center;gap:14px">
      <img src="{beresol}" alt="Beresol" style="height:38px;width:auto">
      <span style="font-family:'JetBrains Mono',monospace;font-size:13px;color:var(--faint);letter-spacing:.05em">brubru.beresol.eu</span>
    </div>
    <div style="font-size:15px;color:var(--soft)">All the EU, with AI.</div>
  </div>
  <div class="credit" style="bottom:88px">Photo: {CLOSE['photographer']} / Pexels</div>
</section>"""

    html = ("<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">\n"
            "<title>Cyber Resilience Act reporting starts 11 September 2026 - Brubru</title>\n"
            f"<style>{css}</style>\n</head><body>\n"
            + "\n".join([slide1(), slide2(), slide3(), slide4(), slide5(), slide6(), slide7()])
            + "\n</body></html>\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"[OK] {OUT}  ({OUT.stat().st_size/1_000_000:.2f} MB, 7 slides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
