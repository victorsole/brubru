"""
Rebuild the endpoint tables of /api/docs/endpoints.html from the live OpenAPI spec, and every count the docs
state, so they stop drifting by hand. On 3 Nov 2026 the page said "every endpoint" and listed 596 of 1,059, its
funding table still described /funding/all as it was before the funding standard, and 50 API folders had no
section at all.

A row's hand-written text is kept where it exists, except on the funding lists and on deprecated routes, whose
summaries in the spec were rewritten by the funding standard. Numbers in changelog entries are history and stay.

Run after an endpoint is added, renamed or deprecated, then scripts/sync_api_docs_nav.py:

    python3.12 frontend/scripts/sync_api_docs_endpoints.py
    python3.12 frontend/scripts/sync_api_docs_nav.py
"""
from __future__ import annotations

import html
import json
import re
import ssl
import urllib.request
from html import escape
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "public" / "api" / "docs"
SPEC_URL = "https://brubru-production.up.railway.app/api/v2/openapi.json"

# Folders with no section until 3 Nov 2026: id -> heading. Names as each body calls itself.
NEW_GROUPS = [
    ("More EU agencies", {
        "easa": "EASA: aviation safety", "emsa": "EMSA: maritime safety", "era": "ERA: railways",
        "euspa": "EUSPA: space programme", "ela": "ELA: labour authority", "efca": "EFCA: fisheries control",
        "eurofound": "Eurofound: living and working conditions", "etf": "ETF: training foundation",
        "eurojust": "Eurojust: judicial cooperation", "cepol": "CEPOL: law enforcement training",
        "europol": "Europol: law enforcement", "frontex": "Frontex: border and coast guard"}),
    ("Executive agencies", {
        "cinea": "CINEA: climate, infrastructure, environment", "eacea": "EACEA: education, audiovisual, culture",
        "hadea": "HaDEA: health and digital", "eismea": "EISMEA: innovation and SMEs",
        "ercea": "ERCEA: European Research Council", "rea": "REA: research"}),
    ("Courts, auditors and advisory bodies", {
        "cjeu": "CJEU: Court of Justice", "eca": "ECA: Court of Auditors", "eesc": "EESC: Economic and Social Committee",
        "cor": "CoR: Committee of the Regions", "advisory-opinions": "Advisory opinions: EESC and CoR",
        "ombudsman": "European Ombudsman", "edps": "EDPS: data protection supervisor", "edpb": "EDPB: data protection board"}),
    ("Inter-institutional services", {
        "epso": "EPSO: personnel selection", "eas": "EUSA: School of Administration", "cdt": "CdT: translation centre",
        "cert-eu": "CERT-EU: cybersecurity for EU bodies"}),
    ("Security and defence", {
        "eccc": "ECCC: cybersecurity competence centre", "euiss": "EUISS: security studies", "eda": "EDA: defence agency",
        "satcen": "SatCen: satellite centre", "esdc": "ESDC: security and defence college"}),
    ("Joint undertakings", {
        "clean-hydrogen": "Clean Hydrogen", "edctp3": "EDCTP3: global health", "eurohpc": "EuroHPC: supercomputing",
        "clean-aviation": "Clean Aviation", "cbe": "CBE: circular bio-based", "ihi": "IHI: innovative health",
        "chips": "Chips", "sesar": "SESAR 3: air traffic", "f4e": "F4E: fusion energy", "europes-rail": "Europe's Rail",
        "sns": "SNS: smart networks", "euratom": "Euratom Supply Agency"}),
    ("Across EU bodies", {
        "news": "News across EU bodies", "events": "Events across EU bodies", "programmes": "Funding programmes directory",
        "bundles": "Bundles: routes grouped by what you want", "pricing": "What each call costs"}),
]
TENDER_DOCS = "/api/v2/proprietary/tender-docs"
# The funding standard's consolidated lists come first on the funding table.
FUNDING_FIRST = ["opportunities", "awards", "budgets", "partners", "tenders", "ft-calls-for-proposals",
                 "ft-calls-for-tenders", "ft-cascade-calls", "ft-funded-projects", "tender-awards", "eu-funding-recipients"]
# Whatever number the page last carried, in the page's own way of writing a thousand.
ENDPOINT_COUNT = re.compile(r"\b1(,|\.|&nbsp;| )0\d\d(?=(?:&nbsp;|\s)(?:REST\s|v2\s)?endpoints?)")
FOLDER_WORD = r"\b9\d(?=(?:&nbsp;|\s)(?:EU institution folders|EU|folders|carpetas|carpetes|dossiers|cartelle|mappen|r[ée]pertoires))"


def live_spec() -> dict:
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        ctx = ssl.create_default_context()
    return json.load(urllib.request.urlopen(SPEC_URL, timeout=120, context=ctx))["paths"]


def folder_of(path: str) -> str:
    if path.startswith(TENDER_DOCS):
        return "tender-docs"
    return path.split("/")[3]


def norm(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "X", html.unescape(path)).rstrip("/")


def clean_summary(op: dict) -> str:
    return " ".join(str(op.get("summary") or "").replace("[Deprecated]", "").split())


def sort_key(folder: str, path: str):
    tail = path[len("/api/v2/funding/"):] if folder == "funding" else path
    head = tail.split("/")[0]
    rank = FUNDING_FIRST.index(head) if folder == "funding" and head in FUNDING_FIRST else len(FUNDING_FIRST)
    return (rank, path.replace("{", "~"))


def row(method: str, path: str, text: str, deprecated: bool) -> str:
    badge = f'<span class="badge badge--{method.lower()}">{method}</span>'
    note = ' <span style="color:var(--text-mut);">(deprecated)</span>' if deprecated else ""
    return f"<tr><td>{badge}</td><td><code>{html.escape(path)}</code></td><td>{html.escape(text, quote=False)}{note}</td></tr>"


def rebuild_endpoints(paths: dict) -> dict:
    page = DOCS / "endpoints.html"
    s = page.read_text(encoding="utf-8")
    written = {}
    for m in re.finditer(r"<tr><td>.*?<code>(/api/v[12][^<]*)</code></td><td>(.*?)</td></tr>", s, flags=re.S):
        written.setdefault(norm(m.group(1)), m.group(2))
    by_folder: dict = {}
    for path, ops in paths.items():
        for method in ("get", "post"):
            if method in ops:
                by_folder.setdefault(folder_of(path), []).append((method.upper(), path, ops[method]))

    def table_rows(folder):
        rows = []
        for method, path, op in sorted(by_folder.get(folder, []), key=lambda x: sort_key(folder, x[1])):
            old = written.get(norm(path))
            deprecated = bool(op.get("deprecated"))
            if old and folder != "funding" and not deprecated:
                rows.append(f'<tr><td><span class="badge badge--{method.lower()}">{method}</span></td><td><code>{html.escape(path)}</code></td><td>{old}</td></tr>')
            else:
                rows.append(row(method, path, clean_summary(op), deprecated))
        return rows

    def word(n):
        return f"{n} endpoint" + ("" if n == 1 else "s")

    def replace_section(match):
        sid, head = match.group(1), match.group(2)
        rows = table_rows(sid)
        if not rows:
            return match.group(0)
        head = re.sub(r"\d+ endpoints?", word(len(rows)), head)
        body = re.sub(r"<tbody>.*?</tbody>", lambda _: "<tbody>\n" + "\n".join(rows) + "\n</tbody>", match.group(3), count=1, flags=re.S)
        return f'<h2 id="{sid}">{head}</h2>{body}'

    s = re.sub(r'<h2 id="([^"]+)">(.*?)</h2>(.*?)(?=<h2 id="|\Z)', replace_section, s, flags=re.S)
    if 'id="hadea"' not in s:
        blocks = []
        for group, members in NEW_GROUPS:
            for sid, title in members.items():
                rows = table_rows(sid)
                blocks.append(f'<h2 id="{sid}">{html.escape(title, quote=False)} <span style="font-weight:400;color:var(--text-mut);font-size:0.6em;">{word(len(rows))}</span></h2>\n'
                              '<table class="endpoint-table">\n<thead><tr><th>Method</th><th>Endpoint</th><th>What it returns</th></tr></thead>\n'
                              "<tbody>\n" + "\n".join(rows) + "\n</tbody>\n</table>\n")
        last = s.rfind("</table>") + len("</table>")
        s = s[:last] + "\n\n" + "\n".join(blocks) + s[last:]
    page.write_text(s, encoding="utf-8")
    return {sid: len(table_rows(sid)) for sid in by_folder}


def sync_counts(counts: dict) -> None:
    """Every "(N)" beside a link to a section, on every docs page; the totals in the prose."""
    total = sum(counts.values())
    folders = len({k for k in counts if k != "tender-docs"})
    # _assets/nav.html first: sync_api_docs_nav.py copies it over every English sidebar.
    for page in [DOCS / "_assets" / "nav.html", *DOCS.glob("*.html")]:
        s = page.read_text(encoding="utf-8")
        original = s

        s = re.sub(r'(<a href="/api/docs/endpoints\.html#)([\w-]+)("[^>]*>[^<(]*)()\(\d+\)(</a>)',
                   lambda m: f'{m.group(1)}{m.group(2)}{m.group(3)}({counts.get(m.group(2), 0)}){m.group(5)}' if counts.get(m.group(2)) else m.group(0), s)
        if page.name != "changelog.html":
            s = re.sub(r"(</strong>: all )[\d,]+( endpoints)", rf"\g<1>{total:,}\g<2>", s)
            s = ENDPOINT_COUNT.sub(lambda m: f"1{m.group(1)}{total % 1000:03d}", s)
            s = re.sub(FOLDER_WORD, str(folders), s)
        if s != original:
            page.write_text(s, encoding="utf-8")
    print(f"[OK] {total} endpoints across {folders} folders")


def add_to_nav(group_lang: dict) -> None:
    nav = DOCS / "_assets" / "nav.html"
    s = nav.read_text(encoding="utf-8")
    if "#hadea" not in s:
        blocks = []
        for group, members in NEW_GROUPS:
            items = "\n".join(f'    <li><a href="/api/docs/endpoints.html#{sid}" data-nav="ep-{sid}">{html.escape(title, quote=False)}</a></li>'
                              for sid, title in members.items())
            blocks.append(f"  <h3>{html.escape(group, quote=False)}</h3>\n  <ul>\n{items}\n  </ul>\n")
        s = s.replace("  <h3>Social &amp; extract</h3>", "\n".join(blocks) + "\n  <h3>Social &amp; extract</h3>", 1)
        nav.write_text(s, encoding="utf-8")
    # The translated landing pages keep their own sidebar: one group, the bodies' own acronyms.
    for lang, heading in group_lang.items():
        page = DOCS / f"{lang}.html"
        s = page.read_text(encoding="utf-8")
        if "#hadea" in s:
            continue
        links = "\n".join(f'    <li><a href="/api/docs/endpoints.html#{sid}">{html.escape(title.split(":")[0], quote=False)}</a></li>'
                          for _, members in NEW_GROUPS for sid, title in members.items())
        block = f"  <h3>{heading}</h3>\n  <ul>\n{links}\n  </ul>\n\n"
        at = s.find('<a href="/api/docs/institutions.html"')
        at = s.rfind("<h3>", 0, at)
        s = s[:at] + block.lstrip() + "  " + s[at:]
        page.write_text(s, encoding="utf-8")


# The bundles in reading order, as services/api_keys/bundles.py defines them; a bundle the spec does not name stops the run.
BUNDLES = [
    ("official-journal", "Official Journal", "What the EU publishes each day: its acts, by date or by reference."),
    ("legislation", "Laws and the legislative process", "EU laws and the files behind them: procedures, amendments, votes, adopted texts, Council documents, delegated and implementing acts, court rulings."),
    ("funding-procurement", "Funding and procurement", "Every call, tender and award, EU programmes and budgets, and who can partner."),
    ("news-events", "News and events", "News, press releases and events from every EU institution and body, and what is on the calendar."),
    ("agencies-bodies", "Agencies and bodies", "Everything from the EU's agencies, financial institutions, courts and advisory bodies, folder by folder."),
    ("people", "People and organisations", "Officials, MEPs and their assistants, Commissioners, expert groups, lobbyists and the organisations on the Transparency Register."),
    ("consultations", "Public consultations", "Public consultations of the Commission and the agencies, and the feedback they receive."),
    ("enforcement-markets", "Enforcement and markets", "Infringements, competition, state aid, digital markets cases, sanctions, trade defence, tariffs, food alerts, product passports and geographical indications."),
    ("research-data", "Research and data", "Studies, publications and topic pages, Parliament's research service, open data and statistics, and Brubru's own guides and translations."),
]


def write_bundles_page(paths: dict) -> None:
    """bundles.html: its tables come from the live spec. The page's shell is copied from rate-limits.html."""
    routes: dict = {b[0]: [] for b in BUNDLES}
    for path, ops in paths.items():
        for bundle in (ops.get("get") or {}).get("x-brubru-bundles", []):
            routes[bundle].append(path)
    missing = [b for b, r in routes.items() if not r]
    if missing:
        raise SystemExit(f"[ERROR] the live spec names no route in: {missing}. Is the backend deployed?")
    rows = "\n".join(
        f'<tr><td><strong>{escape(label)}</strong><br>{escape(text)}</td>'
        f'<td>{len(routes[bid])}</td><td>{sum(1 for p in routes[bid] if "{" not in p)}</td>'
        f'<td><a href="/api/try?bundle={bid}">Try it</a><br><code>{bid}</code></td></tr>'
        for bid, label, text in BUNDLES)
    body = f"""<div class="main__eyebrow">Bundles</div>
<h1>Bundles</h1>
<p class="main__lede">The API serves over a thousand routes. A bundle is a group of them by what you want: take the ones you need and leave the rest.</p>

<table>
<colgroup><col style="width:52%"><col style="width:10%"><col style="width:10%"><col style="width:28%"></colgroup>
<thead><tr><th>Bundle</th><th>Routes</th><th>Lists</th><th>Try it, and its id</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
<p>A route can sit in several bundles: an agency's news is both Agencies and News. Every data route sits in at least one.</p>

<h2 id="find">Find the routes in a bundle</h2>
<p><strong>In the browser:</strong> the <a href="/api/try">API Console</a> narrows its catalogue to one bundle, with no account.</p>
<p><strong>From code:</strong> both routes are public and free, and need no key.</p>
<pre><code>curl https://brubru-production.up.railway.app/api/v2/bundles
curl https://brubru-production.up.railway.app/api/v2/bundles/funding-procurement</code></pre>
<p>The <a href="/api/v2/openapi.json">OpenAPI spec</a> names each route's bundles in <code>x-brubru-bundles</code>.</p>

<h2 id="limit">Limit a key to bundles</h2>
<p>When you <a href="/api#your-keys">create a key</a>, choose "Only the bundles I choose". The key is then refused on anything else, with the error <code>route_not_included</code>, and routes added later join their bundle by themselves. The price of a call does not change.</p>
<p>A key limited to bundles does not open the MCP tools, because a tool reaches further than any one bundle. For those, create a key with every route.</p>
"""
    shell = (DOCS / "rate-limits.html").read_text(encoding="utf-8")
    start, end = shell.index('<div class="main__eyebrow">'), shell.index('</main>')
    page = shell[:start] + body + shell[end:]
    page = page.replace("<title>Rate limits: Brubru EU Data API</title>", "<title>Bundles: Brubru EU Data API</title>")
    (DOCS / "bundles.html").write_text(page, encoding="utf-8")
    print(f"[OK] bundles.html: {len(BUNDLES)} bundles")


def main() -> None:
    paths = live_spec()
    counts = rebuild_endpoints(paths)
    write_bundles_page(paths)
    add_to_nav({"es": "M&aacute;s organismos de la UE", "ca": "M&eacute;s organismes de la UE", "fr": "Autres organes de l'UE",
                "it": "Altri organismi dell'UE", "nl": "Meer EU-organen"})
    sync_counts(counts)


if __name__ == "__main__":
    main()
