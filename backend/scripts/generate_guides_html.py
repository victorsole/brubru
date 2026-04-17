#!/usr/bin/env python3.12
"""
Generate a static HTML page listing all Brubru knowledge guides.
Run this after creating or updating guides. Called from /news skill.

Usage:
    python3.12 scripts/generate_guides_html.py

Output:
    frontend/public/guides/index.html
"""

import re
import sys
import os
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base.knowledge_loader import KnowledgeLoader, GUIDE_KEYWORD_TRIGGERS


def extract_guide_metadata(name: str, content: str) -> dict:
    """Extract structured metadata from a guide's content."""
    lines = content.split('\n')
    title = lines[0].replace('# ', '') if lines[0].startswith('#') else name.replace('_', ' ').title()

    # Parse QUICK FACTS
    qf_lines = []
    in_qf = False
    for line in lines:
        if 'QUICK FACTS' in line:
            in_qf = True
            continue
        if in_qf and line.startswith('##'):
            break
        if in_qf and line.strip().startswith('- '):
            qf_lines.append(line.strip()[2:])

    # Extract key metadata
    com_ref = ''
    procedure_ref = ''
    responsible_dg = ''
    ep_committee = ''
    status = ''
    legal_type = ''

    for qf in qf_lines:
        qf_lower = qf.lower()
        # COM reference
        m = re.search(r'COM\(\d{4}\)\s*\d+', qf, re.IGNORECASE)
        if m and not com_ref:
            com_ref = m.group(0)
        # Procedure
        m = re.search(r'\d{4}/\d{4}\([A-Z]+\)', qf)
        if m and not procedure_ref:
            procedure_ref = m.group(0)
        # DG
        if 'responsible dg' in qf_lower or 'lead dg' in qf_lower or qf_lower.startswith('dg'):
            responsible_dg = qf.split(':')[-1].strip() if ':' in qf else qf
        # EP committee
        if 'ep lead committee' in qf_lower or 'lead committee' in qf_lower:
            ep_committee = qf.split(':')[-1].strip() if ':' in qf else qf
        # Status
        if 'status' in qf_lower and 'current' in qf_lower:
            status = qf.split(':')[-1].strip() if ':' in qf else qf
        elif 'status' in qf_lower and not status:
            status = qf.split(':')[-1].strip() if ':' in qf else qf
        # Type
        if qf_lower.startswith('type:'):
            legal_type = qf.split(':')[-1].strip()

    trigger_count = sum(1 for t in GUIDE_KEYWORD_TRIGGERS.values() if name in t)

    # Categorise
    category = categorise_guide(name, title, content)

    return {
        'id': name,
        'title': title,
        'com_ref': com_ref,
        'procedure_ref': procedure_ref,
        'responsible_dg': responsible_dg[:40],
        'ep_committee': ep_committee[:20],
        'status': status[:60],
        'legal_type': legal_type[:30],
        'chars': len(content),
        'triggers': trigger_count,
        'category': category,
    }


def categorise_guide(name: str, title: str, content: str) -> str:
    """Assign a thematic category to a guide."""
    text = (name + ' ' + title + ' ' + content[:500]).lower()

    if any(k in text for k in ['energy', 'climate', 'green', 'hydrogen', 'nuclear', 'smr', 'grid', 'battery', 'renewable', 'fusion']):
        return 'Energy and Climate'
    if any(k in text for k in ['digital', 'ai act', 'dsa', 'dma', 'data', 'cyber', 'copyright', 'media']):
        return 'Digital and Technology'
    if any(k in text for k in ['trade', 'customs', 'tariff', 'fta', 'mercosur', 'australia']):
        return 'Trade and Customs'
    if any(k in text for k in ['migration', 'asylum', 'border', 'eurodac', 'smuggling', 'visa', 'georgia']):
        return 'Migration and Home Affairs'
    if any(k in text for k in ['defence', 'safe rearm', 'military', 'security']):
        return 'Defence and Security'
    if any(k in text for k in ['health', 'pharma', 'medical', 'rare disease', 'ehds']):
        return 'Health'
    if any(k in text for k in ['environment', 'water', 'natura', 'chemicals', 'reach', 'ecodesign', 'packaging']):
        return 'Environment'
    if any(k in text for k in ['competition', 'state aid', 'antitrust', 'merger', 'late payment', 'payment']):
        return 'Competition and Single Market'
    if any(k in text for k in ['transport', 'road safety', 'autonomous', 'rail']):
        return 'Transport'
    if any(k in text for k in ['budget', 'mff', 'financial regulation', 'emu', 'ecb', 'banking', 'taxonomy', 'sustainable finance', 'fiscal']):
        return 'Economic and Financial Affairs'
    if any(k in text for k in ['agriculture', 'cap', 'fisheries', 'bioeconomy', 'food']):
        return 'Agriculture and Food'
    if any(k in text for k in ['enlargement', 'ipa', 'neighbourhood', 'development', 'global gateway']):
        return 'External Relations'
    if any(k in text for k in ['employment', 'social', 'equality', 'gender', 'housing', 'intergenerational', 'disability']):
        return 'Employment and Social Affairs'
    if any(k in text for k in ['space', 'horizon', 'research', 'innovation', 'startup', 'scaleup', 'fp10', 'knowledge valorisation']):
        return 'Research and Innovation'
    if any(k in text for k in ['parliament', 'council', 'commission guide', 'committee of the regions', 'jargon', 'staff', 'personnel', 'epso']):
        return 'Institutional'
    if any(k in text for k in ['lobby', 'public affairs', 'stakeholder', 'monitoring', 'methodology', 'event planning']):
        return 'Professional Skills'
    if any(k in text for k in ['corruption', 'justice', 'rule of law', 'tobacco', 'travel']):
        return 'Justice and Home Affairs'
    if any(k in text for k in ['iran', 'strait', 'hormuz']):
        return 'Foreign Affairs and Crisis'
    if any(k in text for k in ['brubru', 'feature']):
        return 'Brubru Platform'
    return 'Other'


CATEGORY_COLORS = {
    'Energy and Climate': '#059669',
    'Digital and Technology': '#0693e3',
    'Trade and Customs': '#d97706',
    'Migration and Home Affairs': '#dc2626',
    'Defence and Security': '#6b7280',
    'Health': '#059669',
    'Environment': '#059669',
    'Competition and Single Market': '#9b51e0',
    'Transport': '#d97706',
    'Economic and Financial Affairs': '#0693e3',
    'Agriculture and Food': '#059669',
    'External Relations': '#9b51e0',
    'Employment and Social Affairs': '#dc2626',
    'Research and Innovation': '#0693e3',
    'Institutional': '#6b7280',
    'Professional Skills': '#d97706',
    'Justice and Home Affairs': '#dc2626',
    'Foreign Affairs and Crisis': '#dc2626',
    'Brubru Platform': '#0693e3',
    'Other': '#6b7280',
}

CATEGORY_ICONS = {
    'Energy and Climate': 'mdi-flash',
    'Digital and Technology': 'mdi-chip',
    'Trade and Customs': 'mdi-swap-horizontal',
    'Migration and Home Affairs': 'mdi-passport',
    'Defence and Security': 'mdi-shield-outline',
    'Health': 'mdi-hospital-box-outline',
    'Environment': 'mdi-leaf',
    'Competition and Single Market': 'mdi-scale-balance',
    'Transport': 'mdi-train-car',
    'Economic and Financial Affairs': 'mdi-chart-line',
    'Agriculture and Food': 'mdi-sprout',
    'External Relations': 'mdi-earth',
    'Employment and Social Affairs': 'mdi-account-group',
    'Research and Innovation': 'mdi-lightbulb-on-outline',
    'Institutional': 'mdi-bank',
    'Professional Skills': 'mdi-briefcase-variant',
    'Justice and Home Affairs': 'mdi-gavel',
    'Foreign Affairs and Crisis': 'mdi-alert-circle-outline',
    'Brubru Platform': 'mdi-robot-outline',
    'Other': 'mdi-file-document-outline',
}


def generate_html(guides: list[dict]) -> str:
    """Generate the full HTML page."""
    today = datetime.now().strftime('%d %B %Y')
    total_triggers = sum(g['triggers'] for g in guides)
    total_chars = sum(g['chars'] for g in guides)

    # Group by category
    categories = {}
    for g in guides:
        cat = g['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(g)

    # Sort categories by count (descending)
    sorted_cats = sorted(categories.items(), key=lambda x: -len(x[1]))

    # Build guide cards HTML
    cards_html = ''
    for cat, cat_guides in sorted_cats:
        color = CATEGORY_COLORS.get(cat, '#6b7280')
        icon = CATEGORY_ICONS.get(cat, 'mdi-file-document-outline')
        cards_html += f'''
    <section class="section" id="{cat.lower().replace(' ', '-').replace('&', 'and')}">
      <div class="section__header">
        <div class="section__icon" style="background: {color};"><span class="mdi {icon}"></span></div>
        <h2 class="section__title">{cat}</h2>
      </div>
      <p class="section__subtitle">{len(cat_guides)} guide{"s" if len(cat_guides) != 1 else ""}</p>
      <div class="guide-grid">
'''
        for g in sorted(cat_guides, key=lambda x: x['title']):
            meta_parts = []
            if g['com_ref']:
                meta_parts.append(g['com_ref'])
            if g['procedure_ref']:
                meta_parts.append(g['procedure_ref'])
            if g['ep_committee']:
                meta_parts.append(g['ep_committee'])
            meta_line = ' | '.join(meta_parts) if meta_parts else ''

            status_html = ''
            if g['status']:
                status_text = g['status'][:50]
                if 'block' in status_text.lower():
                    status_html = f'<span class="pill pill--red">{status_text}</span>'
                elif 'adopt' in status_text.lower() or 'conclude' in status_text.lower():
                    status_html = f'<span class="pill pill--green">{status_text}</span>'
                else:
                    status_html = f'<span class="pill pill--blue">{status_text}</span>'

            cards_html += f'''        <div class="guide-card">
          <div class="guide-card__header">
            <span class="guide-card__title">{g["title"][:80]}</span>
            <span class="guide-card__stats">{g["triggers"]} triggers | {g["chars"]:,} chars</span>
          </div>
          <div class="guide-card__meta">{meta_line}</div>
          {f'<div class="guide-card__status">{status_html}</div>' if status_html else ''}
        </div>
'''
        cards_html += '      </div>\n    </section>\n'

    # Build TOC
    toc_html = ''
    for i, (cat, cat_guides) in enumerate(sorted_cats, 1):
        anchor = cat.lower().replace(' ', '-').replace('&', 'and')
        toc_html += f'        <a href="#{anchor}" class="toc__link"><span class="toc__num">{len(cat_guides)}</span> {cat}</a>\n'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Brubru Knowledge Guide Library | {len(guides)} EU Policy Guides</title>
  <meta name="description" content="Browse all {len(guides)} Brubru knowledge guides covering EU policy, legislation, and institutional processes. {total_triggers:,} keyword triggers, updated {today}.">
  <link href="https://cdn.jsdelivr.net/npm/@mdi/font@7.4.47/css/materialdesignicons.min.css" rel="stylesheet">
  <style>
    @font-face {{ font-family: 'Adobe Caslon Pro'; src: url('../New-Yorker-Font/ACaslonPro-Regular.otf') format('opentype'); font-weight: 400; font-style: normal; font-display: swap; }}
    @font-face {{ font-family: 'Adobe Caslon Pro'; src: url('../New-Yorker-Font/ACaslonPro-Semibold.otf') format('opentype'); font-weight: 600; font-style: normal; font-display: swap; }}
    @font-face {{ font-family: 'Adobe Caslon Pro'; src: url('../New-Yorker-Font/ACaslonPro-Bold.otf') format('opentype'); font-weight: 700; font-style: normal; font-display: swap; }}

    :root {{
      --color-blue: #0693e3; --color-green: #059669; --color-purple: #9b51e0;
      --color-amber: #d97706; --color-red: #dc2626; --color-text: #111827;
      --color-secondary: #6b7280; --color-muted: #9ca3af; --color-border: #e5e7eb;
      --color-bg-alt: #f3f4f6; --color-bg: #ffffff; --radius: 12px; --radius-sm: 8px;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Adobe Caslon Pro', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, serif; background: var(--color-bg); color: var(--color-text); line-height: 1.7; font-size: 1.05rem; }}

    .header {{ background: var(--color-bg); border-bottom: 1px solid var(--color-border); padding: 1rem 2rem; display: flex; align-items: center; gap: 1.5rem; position: sticky; top: 0; z-index: 100; }}
    .header__logo {{ height: 40px; }}
    .header__text {{ flex: 1; }}
    .header__title {{ font-size: 1rem; font-weight: 700; }}
    .header__subtitle {{ font-size: 0.8rem; color: var(--color-secondary); }}
    .header__cta {{ display: inline-block; padding: 0.5rem 1.25rem; border-radius: 8px; font-weight: 700; font-size: 0.85rem; color: white; border: none; cursor: pointer; background-size: 300% 100%; background-image: linear-gradient(90deg, var(--color-blue), var(--color-green), var(--color-purple), var(--color-amber), var(--color-blue)); animation: rainbowShift 4s ease infinite; transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease; text-decoration: none; letter-spacing: 0.03em; }}
    .header__cta:hover {{ transform: scale(1.08) translateY(-2px); box-shadow: 0 8px 30px rgba(6,147,227,0.35), 0 4px 15px rgba(155,81,224,0.25); }}
    @keyframes rainbowShift {{ 0% {{ background-position: 0% 50%; }} 50% {{ background-position: 100% 50%; }} 100% {{ background-position: 0% 50%; }} }}

    .container {{ max-width: 1100px; margin: 0 auto; padding: 2rem; }}
    .hero {{ text-align: center; padding: 3rem 1rem 2rem; }}
    .hero__tag {{ display: inline-block; background: rgba(6,147,227,0.1); color: var(--color-blue); font-size: 0.8rem; font-weight: 600; padding: 0.35rem 1rem; border-radius: 20px; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1rem; }}
    .hero__title {{ font-size: 2.8rem; font-weight: 700; line-height: 1.15; margin-bottom: 0.75rem; }}
    .hero__title span {{ color: var(--color-blue); background-size: 300% 100%; background-image: linear-gradient(90deg, var(--color-blue), var(--color-green), var(--color-purple), var(--color-amber), var(--color-blue)); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }}
    .hero__title:hover span {{ animation: rainbowShift 4s ease infinite; }}
    .hero__subtitle {{ font-size: 1.15rem; color: var(--color-secondary); max-width: 750px; margin: 0 auto 1.5rem; }}
    .hero__meta {{ font-size: 0.85rem; color: var(--color-muted); display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap; }}
    .hero__meta span {{ display: inline-flex; align-items: center; gap: 0.35rem; }}

    .figures {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin: 2rem 0 3rem; }}
    .figure-card {{ background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius); padding: 1.5rem; text-align: center; transition: all 0.25s; }}
    .figure-card:hover {{ border-color: var(--color-blue); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(6,147,227,0.1); }}
    .figure-card__number {{ font-size: 2.2rem; font-weight: 700; line-height: 1; margin-bottom: 0.25rem; }}
    .figure-card__label {{ font-size: 0.85rem; color: var(--color-secondary); }}
    .fc-blue .figure-card__number {{ color: var(--color-blue); }}
    .fc-green .figure-card__number {{ color: var(--color-green); }}
    .fc-purple .figure-card__number {{ color: var(--color-purple); }}
    .fc-amber .figure-card__number {{ color: var(--color-amber); }}

    .toc {{ background: var(--color-bg-alt); border: 1px solid var(--color-border); border-radius: var(--radius); padding: 1.75rem; margin-bottom: 3rem; }}
    .toc__title {{ font-size: 1.2rem; font-weight: 700; margin-bottom: 1rem; }}
    .toc__grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; }}
    .toc__link {{ display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; border-radius: var(--radius-sm); text-decoration: none; color: var(--color-text); font-size: 0.9rem; transition: all 0.15s; }}
    .toc__link:hover {{ background: rgba(6,147,227,0.08); color: var(--color-blue); }}
    .toc__num {{ display: inline-flex; align-items: center; justify-content: center; min-width: 22px; height: 22px; padding: 0 4px; background: var(--color-blue); color: white; border-radius: 11px; font-size: 0.7rem; font-weight: 700; flex-shrink: 0; }}

    .section {{ margin-bottom: 3rem; scroll-margin-top: 80px; }}
    .section__header {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; }}
    .section__icon {{ width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.3rem; flex-shrink: 0; }}
    .section__title {{ font-size: 1.6rem; font-weight: 700; }}
    .section__subtitle {{ font-size: 1rem; color: var(--color-secondary); margin-bottom: 1.5rem; }}

    .guide-grid {{ display: grid; grid-template-columns: 1fr; gap: 0.75rem; }}
    .guide-card {{ background: var(--color-bg); border: 1px solid var(--color-border); border-radius: var(--radius-sm); padding: 1rem 1.25rem; transition: all 0.2s; }}
    .guide-card:hover {{ border-color: var(--color-blue); transform: translateY(-1px); }}
    .guide-card__header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-bottom: 0.25rem; }}
    .guide-card__title {{ font-size: 0.95rem; font-weight: 700; }}
    .guide-card__stats {{ font-size: 0.75rem; color: var(--color-muted); white-space: nowrap; }}
    .guide-card__meta {{ font-size: 0.8rem; color: var(--color-secondary); }}
    .guide-card__status {{ margin-top: 0.35rem; }}

    .pill {{ display: inline-block; padding: 0.15rem 0.5rem; border-radius: 10px; font-size: 0.72rem; font-weight: 600; }}
    .pill--blue {{ background: rgba(6,147,227,0.1); color: var(--color-blue); }}
    .pill--green {{ background: rgba(5,150,105,0.1); color: var(--color-green); }}
    .pill--red {{ background: rgba(220,38,38,0.1); color: var(--color-red); }}

    .footer {{ background: var(--color-bg-alt); border-top: 1px solid var(--color-border); padding: 2rem; text-align: center; font-size: 0.85rem; color: var(--color-secondary); margin-top: 3rem; }}
    .footer a {{ color: var(--color-blue); text-decoration: none; }}
    .footer a:hover {{ text-decoration: underline; }}

    .back-to-top {{ position: fixed; bottom: 2rem; right: 2rem; width: 44px; height: 44px; border-radius: 50%; background: var(--color-blue); color: white; display: flex; align-items: center; justify-content: center; font-size: 1.3rem; text-decoration: none; box-shadow: 0 4px 12px rgba(0,0,0,0.15); opacity: 0; transition: all 0.3s; z-index: 50; }}
    .back-to-top.visible {{ opacity: 1; }}
    .back-to-top:hover {{ transform: translateY(-2px); }}

    @media (max-width: 1024px) {{ .figures {{ grid-template-columns: repeat(2, 1fr); }} .toc__grid {{ grid-template-columns: repeat(2, 1fr); }} }}
    @media (max-width: 767px) {{ .hero__title {{ font-size: 1.8rem; }} .figures {{ grid-template-columns: 1fr 1fr; }} .toc__grid {{ grid-template-columns: 1fr; }} .header {{ padding: 0.75rem 1rem; }} .header__cta {{ display: none; }} .container {{ padding: 1.25rem; }} .hero__meta {{ flex-direction: column; gap: 0.5rem; }} .guide-card__header {{ flex-direction: column; gap: 0.25rem; }} }}
    html {{ scroll-behavior: smooth; }}
  </style>
</head>
<body>

<header class="header" id="top">
  <img src="../assets/brubru_mainlogo.png" alt="Brubru" class="header__logo">
  <div class="header__text">
    <div class="header__title">Knowledge Guide Library</div>
    <div class="header__subtitle">All EU policy domains covered by Brubru's chatbot</div>
  </div>
  <a href="https://brubru.beresol.eu" class="header__cta">Try Brubru Free</a>
</header>

<div class="container">

<section class="hero">
  <div class="hero__tag">Updated {today}</div>
  <h1 class="hero__title">Brubru's <span>Knowledge Guides</span></h1>
  <p class="hero__subtitle">
    Every guide is a verified, structured briefing that powers Brubru's chatbot answers.
    Browse {len(guides)} guides across {len(sorted_cats)} EU policy domains.
  </p>
  <div class="hero__meta">
    <span><span class="mdi mdi-book-open-page-variant"></span> {len(guides)} guides</span>
    <span><span class="mdi mdi-tag-multiple"></span> {total_triggers:,} keyword triggers</span>
    <span><span class="mdi mdi-text-box-outline"></span> {total_chars:,} characters</span>
    <span><span class="mdi mdi-folder-multiple"></span> {len(sorted_cats)} categories</span>
  </div>
</section>

<div class="figures">
  <div class="figure-card fc-blue">
    <div class="figure-card__number">{len(guides)}</div>
    <div class="figure-card__label">Knowledge guides</div>
  </div>
  <div class="figure-card fc-green">
    <div class="figure-card__number">{total_triggers:,}</div>
    <div class="figure-card__label">Keyword triggers</div>
  </div>
  <div class="figure-card fc-purple">
    <div class="figure-card__number">{len(sorted_cats)}</div>
    <div class="figure-card__label">Policy domains</div>
  </div>
  <div class="figure-card fc-amber">
    <div class="figure-card__number">{total_chars // 1000}K</div>
    <div class="figure-card__label">Characters of knowledge</div>
  </div>
</div>

<nav class="toc">
  <div class="toc__title">Categories</div>
  <div class="toc__grid">
{toc_html}  </div>
</nav>

{cards_html}

</div>

<footer class="footer">
  <p>
    Knowledge Guide Library by <a href="https://brubru.beresol.eu">Brubru</a>, the AI-powered EU policy assistant by <a href="https://beresol.eu">Beresol</a>.
    <br>Guides are updated daily during the <a href="https://brubru.beresol.eu">morning routine</a>. Last updated: {today}.
    <br><a href="https://beresol.eu/public-affairs">Beresol Public Affairs</a> | <a href="https://beresol.eu/startup-monitor">Beresol Startup Monitor</a>
  </p>
</footer>

<a href="#top" class="back-to-top" id="backToTop"><span class="mdi mdi-chevron-up"></span></a>
<script>
  window.addEventListener('scroll', function() {{
    var btn = document.getElementById('backToTop');
    if (window.scrollY > 400) {{ btn.classList.add('visible'); }}
    else {{ btn.classList.remove('visible'); }}
  }});
  document.getElementById('backToTop').addEventListener('click', function(e) {{
    e.preventDefault();
    window.scrollTo({{ top: 0, behavior: 'smooth' }});
  }});
</script>
</body>
</html>'''


def update_data_architecture_counts(guide_count: int, trigger_count: int) -> bool:
    """Sync hardcoded guide/trigger counts in data-architecture/index.html.

    Rewrites four hotspots:
      1. figure-card data-count attribute for "expert knowledge guides"
      2. section__intro line "519 europa.eu sources, N knowledge guides"
      3. subsection__title "N expert knowledge guides"
      4. subsection__title "N,NNN keyword triggers in 6 languages"
    """
    data_arch = Path(__file__).parent.parent.parent / 'frontend' / 'public' / 'data-architecture' / 'index.html'
    if not data_arch.exists():
        print(f'[WARN] data-architecture page not found: {data_arch}')
        return False

    html = data_arch.read_text(encoding='utf-8')
    original = html

    # 1. figure-card data-count + label
    html = re.sub(
        r'(<div class="figure-card__number" data-count=")\d+(">0</div>\s*<div class="figure-card__label">expert knowledge guides)',
        rf'\g<1>{guide_count}\g<2>',
        html,
    )
    # 2. "519 europa.eu sources, N knowledge guides"
    html = re.sub(
        r'(519 europa\.eu sources,\s*)\d+(\s+knowledge guides)',
        rf'\g<1>{guide_count}\g<2>',
        html,
    )
    # 3. subsection title for guides count
    html = re.sub(
        r'(<h3 class="subsection__title">)\d+(\s+expert knowledge guides</h3>)',
        rf'\g<1>{guide_count}\g<2>',
        html,
    )
    # 4. subsection title for triggers count (with comma, e.g. 5,379)
    html = re.sub(
        r'(<h3 class="subsection__title">)[\d,]+(\s+keyword triggers in 6 languages</h3>)',
        rf'\g<1>{trigger_count:,}\g<2>',
        html,
    )

    if html != original:
        data_arch.write_text(html, encoding='utf-8')
        print(f'[OK] Updated {data_arch} (guides={guide_count}, triggers={trigger_count:,})')
        return True
    print(f'[INFO] data-architecture counts already match guides={guide_count}, triggers={trigger_count:,}')
    return False


def main():
    loader = KnowledgeLoader()
    loader.load_all()

    guides = []
    for name, content in loader.guides.items():
        guides.append(extract_guide_metadata(name, content))

    html = generate_html(guides)

    output_dir = Path(__file__).parent.parent.parent / 'frontend' / 'public' / 'guides'
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'index.html'
    output_path.write_text(html, encoding='utf-8')

    total_triggers = sum(g["triggers"] for g in guides)
    print(f'[OK] Generated {output_path}')
    print(f'     {len(guides)} guides, {total_triggers} triggers')
    print(f'     {len(set(g["category"] for g in guides))} categories')

    # Keep data-architecture page in sync with current counts.
    update_data_architecture_counts(len(guides), total_triggers)


if __name__ == '__main__':
    main()
