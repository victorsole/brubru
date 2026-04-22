#!/usr/bin/env python3.12
"""
Batch Catalan Translation Pipeline

Processes the translation queue file, translating acts one by one,
auditing each, importing to DB, and deploying to SiteGround.

Usage:
    cd backend

    # Translate next N acts from queue (default: 10)
    python3.12 scripts/batch_catalan_translate.py --count 10

    # Translate only small files (<10KB, fast)
    python3.12 scripts/batch_catalan_translate.py --max-size 10 --count 50

    # Translate medium files (10-50KB)
    python3.12 scripts/batch_catalan_translate.py --min-size 10 --max-size 50 --count 20

    # Dry run (show what would be translated)
    python3.12 scripts/batch_catalan_translate.py --count 20 --dry-run

    # Resume from a specific CELEX
    python3.12 scripts/batch_catalan_translate.py --start-from 32020R0001 --count 10

Created: 8 April 2026
"""

import argparse
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


QUEUE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'legislacio-ue-catala', 'translation_queue.txt'
)

TRANSLATE_SCRIPT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'catalan_translate.py'
)

TRANSLATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'data', 'legislacio-ue-catala'
)

# Category auto-classification based on keywords in title
# Rules checked top-to-bottom; first match wins. More specific rules first.
# Supports both English (from Formex XML titles) and Catalan (from translated titles).
CATEGORY_RULES = [
    # --- Agriculture, food safety, fisheries ---
    (['pesticide', 'fitosanitari', 'substància activa', 'substancia activa', 'biocid', 'producte biocida',
      'plant protection', 'protecció vegetal', 'proteccio vegetal', 'herbicid', 'fungicid', 'insecticid'],
     'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),
    (['additiu', 'additive', 'pinso', 'feed additive', 'novel food', 'nou aliment', 'flavouring',
      'aroma', 'food supplement', 'complement alimentari', 'food contact', 'contaminant'],
     'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),
    (['fisheries', 'fishing', 'aquaculture', 'fish', 'pesca', 'pesquer', 'aqüicultura', 'atún', 'tuna',
      'catch', 'captura', 'quota de pesca'],
     'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),
    (['agriculture', 'CAP', 'agri', 'farm', 'crop', 'wine', 'olive', 'sugar', 'milk', 'beef', 'poultry',
      'cereal', 'fruit', 'vegetable', 'seed', 'organic', 'ecològic', 'PAC', 'vi ', 'sucre', 'llet',
      'cereals', 'fruita', 'hortalissa', 'carn', 'ovelles', 'bovins', 'porcí'],
     'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),
    (['animal', 'veterinary', 'plant health', 'phytosanitary', 'food safety', 'feed', 'zoo',
      'salut animal', 'veterinari', 'sanitat animal', 'zoonos', 'epizoòtia'],
     'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),
    (['denominació', 'denominacio', 'indicació geogràfica', 'indicacio geografica', 'geographical indication',
      'protected designation', 'denominació d\'origen', 'IGP', 'DOP', 'TSG'],
     'Agricultura i recursos naturals', 'Agriculture and Natural Resources'),

    # --- Trade, customs, sanctions ---
    (['antidumping', 'countervailing', 'anti-dumping', 'antidúmping', 'safeguard measure',
      'drets provisionals', 'drets definitius', 'dret compensatori', 'mesura de salvaguarda'],
     'Comerç i política exterior', 'Trade and External Policy'),
    (['customs', 'tariff', 'aranzel', 'duana', 'duaner', 'contingent', 'nomenclatura combinada',
      'combined nomenclature', 'codi NC', 'CN code', 'classificació tarifària'],
     'Comerç i política exterior', 'Trade and External Policy'),
    (['sancion', 'restrictiv', 'mesures restrictives', 'restrictive measures', 'congelació d\'actius',
      'freeze', 'embargo', 'prohibició de viatge'],
     'Comerç i política exterior', 'Trade and External Policy'),
    (['acord d\'associació', 'acord de comerç', 'acord de lliure', 'trade agreement', 'association agreement',
      'free trade', 'partnership agreement', 'acord de cooperació', 'cooperation agreement',
      'acord de pesca', 'fisheries partnership', 'EPA', 'DCFTA'],
     'Comerç i política exterior', 'Trade and External Policy'),
    (['foreign', 'CFSP', 'PESC', 'third countr', 'tercer país', 'tercer pais', 'relacions exteriors',
      'external relations', 'neighbourhood', 'veïnatge', 'ACP', 'overseas', 'ultramar'],
     'Comerç i política exterior', 'Trade and External Policy'),
    (['import', 'export', 'trade', 'comerç', 'comercial'],
     'Comerç i política exterior', 'Trade and External Policy'),

    # --- Environment, energy, sustainability ---
    (['environment', 'emission', 'climate', 'carbon', 'waste', 'water', 'pollution', 'biodiversity',
      'natura 2000', 'habitat', 'medi ambient', 'residus', 'contaminació', 'biodiversitat',
      'carboni', 'clima', 'emissió', 'emissio', 'reciclatge', 'circular economy', 'economia circular',
      'chemical', 'químic', 'REACH', 'substàncies', 'CLP', 'classificació de substàncies'],
     'Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies'),
    (['energy', 'renewable', 'electricity', 'gas', 'nuclear', 'petroleum', 'fuel', 'energia',
      'renovable', 'electricitat', 'petroli', 'combustible', 'hidrogen', 'hydrogen', 'eòlic',
      'solar', 'fotovoltaic'],
     'Sostenibilitat i medi ambient', 'Sustainability and Environmental Policies'),

    # --- Digital ---
    (['digital', 'data', 'cyber', 'electronic', 'telecom', 'AI ', 'artificial intelligence', 'platform',
      'online', 'internet', 'dades', 'ciberseguretat', 'electrònic', 'telecomunicaci', 'plataforma',
      'intel·ligència artificial', 'semiconductor', 'xip', 'chip', 'roaming', 'e-commerce'],
     'Transformació digital', 'Digital Transformation'),

    # --- Economic, financial, market ---
    (['bank', 'credit', 'financial', 'insurance', 'securities', 'investment', 'capital', 'payment',
      'money laundering', 'prudential', 'banc', 'crèdit', 'financer', 'assegurança', 'valors',
      'inversió', 'blanqueig', 'prudencial', 'solvència', 'liquiditat'],
     'Polítiques econòmiques i de mercat', 'Core Economic and Market Policies'),
    (['competition', 'state aid', 'merger', 'antitrust', 'subsid', 'concentraci', 'competència',
      'ajut estatal', 'ajuda estatal', 'fusió', 'antimonopoli', 'subvenció', 'subvencio'],
     'Polítiques econòmiques i de mercat', 'Core Economic and Market Policies'),
    (['transport', 'aviation', 'railway', 'maritime', 'road', 'shipping', 'port', 'aviació',
      'ferroviari', 'marítim', 'carretera', 'portuari', 'aeroport', 'vehicle', 'automòbil'],
     'Polítiques econòmiques i de mercat', 'Core Economic and Market Policies'),
    (['consumer', 'consumidor', 'product safety', 'seguretat dels productes', 'market surveillance',
      'vigilància del mercat', 'CE marking', 'marcatge CE', 'standardisation', 'normalització'],
     'Polítiques econòmiques i de mercat', 'Core Economic and Market Policies'),
    (['intellectual property', 'propietat intel·lectual', 'patent', 'trademark', 'marca',
      'copyright', 'drets d\'autor', 'design right'],
     'Polítiques econòmiques i de mercat', 'Core Economic and Market Policies'),
    (['VAT', 'IVA', 'tax', 'impost', 'fiscal', 'excise', 'accisa', 'duty', 'taxation'],
     'Polítiques econòmiques i de mercat', 'Core Economic and Market Policies'),

    # --- Social, health, employment ---
    (['health', 'medicinal', 'pharmaceutical', 'medical device', 'patient', 'salut', 'medicament',
      'farmacèutic', 'dispositiu mèdic', 'pacient', 'drug', 'tobacco', 'tabac', 'alcohol',
      'cosmètic', 'cosmetic', 'sang', 'blood', 'teixit', 'tissue', 'organ'],
     'Polítiques socials', 'Social Policies'),
    (['worker', 'employment', 'labour', 'social', 'pension', 'equality', 'discrimination',
      'treballador', 'ocupació', 'laboral', 'pensió', 'igualtat', 'discriminació', 'disability',
      'discapacitat', 'accessibility', 'accessibilitat', 'education', 'educació', 'training',
      'formació', 'Erasmus', 'youth', 'joventut'],
     'Polítiques socials', 'Social Policies'),

    # --- Justice, home affairs ---
    (['migration', 'asylum', 'border', 'visa', 'Schengen', 'police', 'criminal', 'judicial',
      'Europol', 'Eurojust', 'migració', 'asil', 'frontera', 'policia', 'penal', 'judicial',
      'extradició', 'cooperation in criminal', 'cooperació penal', 'data protection',
      'protecció de dades', 'privacitat', 'privacy', 'GDPR', 'RGPD'],
     "Justícia i afers d'interior", 'Justice and Home Affairs'),

    # --- Institutional/procedural (NEW) ---
    (['tribunal', 'court of justice', 'general court', 'procediment', 'reglament de procediment',
      'rules of procedure', 'staff regulations', 'estatut dels funcionaris', 'interinstitucional',
      'interinstitutional', 'pressupost', 'budget', 'comitologia', 'comitology', 'OLAF',
      'defensor del poble', 'ombudsman', 'eurostat', 'statistics', 'estadística',
      'comitè de les regions', 'committee of the regions', 'comitè econòmic i social',
      'economic and social committee', 'cens', 'census', 'nomenament', 'appointment'],
     'Afers institucionals de la UE', 'EU Institutional Affairs'),
]

# Parent-law CELEX -> category mapping (for amendments that reference a known law)
PARENT_LAW_CATEGORIES = {
    '396/2005': 'Agricultura i recursos naturals',    # Pesticides MRLs
    '1107/2009': 'Agricultura i recursos naturals',   # Plant protection products
    '528/2012': 'Agricultura i recursos naturals',    # Biocidal products
    '540/2011': 'Agricultura i recursos naturals',    # Approved active substances
    '1333/2008': 'Agricultura i recursos naturals',   # Food additives
    '2015/2283': 'Agricultura i recursos naturals',   # Novel foods
    '2017/2470': 'Agricultura i recursos naturals',   # Novel foods list
    '1829/2003': 'Agricultura i recursos naturals',   # GM food/feed
    '1831/2003': 'Agricultura i recursos naturals',   # Feed additives
    '1223/2009': 'Polítiques socials',                # Cosmetics
    '2021/2115': 'Agricultura i recursos naturals',   # CAP Strategic Plans
    '2021/2116': 'Agricultura i recursos naturals',   # CAP financing
    '1308/2013': 'Agricultura i recursos naturals',   # CMO regulation
    '952/2013': 'Comerç i política exterior',         # Union Customs Code
    '2658/87': 'Comerç i política exterior',          # Combined Nomenclature
    '575/2013': 'Polítiques econòmiques i de mercat', # CRR
    '648/2012': 'Polítiques econòmiques i de mercat', # EMIR
    '600/2014': 'Polítiques econòmiques i de mercat', # MiFIR
    '2016/679': "Justícia i afers d'interior",        # GDPR
    '2022/2065': 'Transformació digital',             # DSA
    '2024/1689': 'Transformació digital',             # AI Act
}


# Granular subcategory detection (Catalan keywords from translated titles)
# First match wins. Order by specificity.
SUBCATEGORY_RULES = [
    # Agriculture & food
    (['pesticide', 'fitosanitari', 'substància activa', 'substancia activa', 'biocid', 'herbicid',
      'fungicid', 'plaguicid'], 'Pesticides i biocides'),
    (['vi ', 'vinya', 'vitícola', 'viticola', 'vinícola', 'vinicola', 'enològic'], 'Vi i viticultura'),
    (['pesca', 'pesquer', 'aqüicultura', 'atún', 'tuna', 'captura', 'quota de pesca', 'sardina',
      'bacallà', 'fishing', 'fisheries'], 'Pesca i aqüicultura'),
    (['additiu', 'pinso', 'feed additive', 'food additive', 'novel food', 'nou aliment', 'aroma'],
     'Additius alimentaris i pinsos'),
    (['denominació', 'denominacio', 'indicació geogràfica', 'indicacio geografica', ' dop', ' igp',
      ' tsg'], 'Indicacions geogràfiques'),
    (['orgànic', 'organic', 'ecològic', 'ecologic'], 'Agricultura ecològica'),
    (['salut animal', 'sanitat animal', 'veterinari', 'zoonos', 'epizoòtia', 'bovins', 'porcí',
      'oví', 'avícola', 'ramat'], 'Salut animal i veterinària'),
    (['planta ', 'vegetal', 'fitosanitat', 'llavor', 'seed'], 'Sanitat vegetal i llavors'),
    (['sucre', 'llet', 'cereals', 'fruita', 'hortalissa', 'carn ', 'oli d', 'oliva', 'mantega',
      'formatge', 'mel '], 'Productes agrícoles'),
    # Trade
    (['antidumping', 'antidúmping', 'countervailing', 'drets provisionals', 'drets definitius',
      'dret compensatori', 'mesura de salvaguarda'], 'Antidúmping i defensa comercial'),
    (['sancion', 'restrictiv', 'mesures restrictives', 'congelació', 'embargo',
      'prohibició de viatge'], 'Sancions i mesures restrictives'),
    (['duana', 'duaner', 'aranzel', 'tarif', 'nomenclatura combinada', 'contingent tarifari',
      'codi NC'], 'Duanes i aranzels'),
    # Finance
    (['banc', 'entitat de crèdit', 'entitat de credit', 'prudencial', 'solvència', 'solvencia',
      'liquiditat'], 'Sector bancari'),
    (['assegurança', 'asseguranca', 'reassegurança', 'reasseguranca'], 'Assegurances'),
    (['valors', 'inversió', 'investiment', 'mercat financer', 'criptoactiu', 'borsa'],
     'Mercats financers'),
    (['blanqueig', 'finançament del terrorisme', 'financament del terrorisme'], 'Antiblanqueig'),
    # Transport
    (['ferroviari', 'tren', 'ferrocarril', 'railway', 'rail '], 'Trens i ferrocarril'),
    (['aviació', 'aviacio', 'aeroport', 'aeronau', 'vol ', 'pilot', 'aeri'], 'Aviació'),
    (['vehicle', 'automòbil', 'automobil', 'cotxe', 'motor ', 'homologació de tipus'],
     'Cotxes i vehicles'),
    (['marítim', 'maritim', 'vaixell', 'navegació', 'navegacio', 'port ', 'portuari'],
     'Transport marítim'),
    # Energy / environment
    (['bateria', 'battery', 'pila '], 'Bateries'),
    (['químic', 'quimic', 'REACH', 'CLP', 'substàncies', 'substancies'], 'Substàncies químiques'),
    (['residus', 'reciclatge', 'waste', 'abocador', 'embalatge'], 'Residus i reciclatge'),
    (['emissió', 'emissio', "gasos d'efecte", 'CO2', 'carboni', 'canvi climàtic',
      'canvi climatic'], 'Emissions i clima'),
    # Digital
    (['ciberseguretat', 'cyber', 'seguretat de xarxes'], 'Ciberseguretat'),
    (['protecció de dades', 'proteccio de dades', 'privacitat', 'RGPD'], 'Protecció de dades'),
    (['intel·ligència artificial', 'intel.ligencia artificial'], 'Intel·ligència artificial'),
    # Social
    (['medicament', 'farmacèutic', 'farmaceutic', 'pharmaceutical'], 'Medicaments i farmàcia'),
    (['cosmètic', 'cosmetic'], 'Cosmètics'),
    (['esport', 'sport', 'dopatge', 'doping'], 'Esport'),
    (['tabac', 'tobacco', 'cigarret'], 'Tabac'),
]


def detect_subcategory(title: str) -> str:
    """Return the first matching subcategory, or None."""
    title_lower = title.lower()
    for keywords, sc in SUBCATEGORY_RULES:
        if any(kw.lower() in title_lower for kw in keywords):
            return sc
    return None


def classify_act(title: str) -> tuple:
    """Auto-classify an act by title keywords. Returns (category_ca, category_en).

    Strategy:
    1. Try parent-law detection (amendments referencing a known regulation)
    2. Try keyword matching against expanded rules
    3. Fall back to 'Altres actes' only if nothing matches
    """
    title_lower = title.lower()

    # Step 1: Parent-law detection for amendments
    # Look for patterns like "modifica el Reglament (UE) núm. 575/2013" or "Regulation (EU) No 396/2005"
    parent_refs = re.findall(r'(?:núm\.|No|n\.)\s*(\d+/\d{4})', title)
    if not parent_refs:
        parent_refs = re.findall(r'\((?:UE|EU|CE|EC)\)\s*(?:núm\.\s*)?(\d+/\d{4})', title)
    if not parent_refs:
        parent_refs = re.findall(r'(\d{3,4}/\d{4})', title)

    for ref in parent_refs:
        if ref in PARENT_LAW_CATEGORIES:
            cat_ca = PARENT_LAW_CATEGORIES[ref]
            cat_en = next((en for kws, ca, en in CATEGORY_RULES if ca == cat_ca), 'Other')
            return cat_ca, cat_en

    # Step 2: Keyword matching
    for keywords, cat_ca, cat_en in CATEGORY_RULES:
        if any(kw.lower() in title_lower for kw in keywords):
            return cat_ca, cat_en

    return 'Altres actes', 'Other acts'


def detect_doc_type(title: str) -> str:
    """Detect document type from title."""
    t = title.lower()
    if 'implementing regulation' in t or "reglament d'execucio" in t.lower():
        return 'implementing'
    if 'delegated regulation' in t or 'reglament delegat' in t.lower():
        return 'delegated'
    if 'directive' in t or 'directiva' in t.lower():
        return 'directive'
    if 'decision' in t or 'decisio' in t.lower():
        return 'decision'
    return 'regulation'


def audit_translation(celex: str) -> list:
    """Run audit checks on a translation. Returns list of issues."""
    f = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
    if not os.path.isfile(f):
        return ['File not found']

    with open(f, 'r') as fh:
        content = fh.read()

    problems = []

    if re.findall(r'Having regard', content, re.IGNORECASE):
        problems.append('Having regard')
    if re.findall(r'Whereas:', content):
        problems.append('Whereas:')
    if re.findall(r'd.implementaci', content, re.IGNORECASE):
        problems.append('d implementacio')

    titles = re.findall(r'<h3 class="article-title">(.*?)</h3>', content)
    bad_t = [t for t in titles if '{' not in t and not re.match(r'Article\s+\d', t)]
    if bad_t:
        problems.append(f'Bad titles: {len(bad_t)}')

    recitals = re.findall(r'class="recital">(.*?)(?:</p>|$)', content, re.DOTALL)
    has_recitals = len(recitals) > 0
    has_atenent = 'Atenent que' in content
    if has_recitals and not has_atenent:
        problems.append('Missing Atenent que')

    if re.findall(r'Please provide|I need the complete text', content):
        problems.append('Sonnet leak')

    return problems


def auto_fix(celex: str) -> int:
    """Apply auto-fixes to a translation. Returns number of fixes applied."""
    f = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
    with open(f, 'r') as fh:
        content = fh.read()

    original = content
    fixes = 0

    # Fix leading quotes in article titles
    new = re.sub(r'<h3 class="article-title">["\u0027]+\s*(Article)', r'<h3 class="article-title">\1', content)
    if new != content:
        fixes += 1
        content = new

    # Fix lowercase article titles
    def fix_lowercase(m):
        text = m.group(1).strip()
        text = re.sub(r"^[lL]'?\s*", '', text)
        text = text.replace('article', 'Article', 1)
        return f'<h3 class="article-title">{text}</h3>'

    new = re.sub(
        r'<h3 class="article-title">((?:l\'?\s*)?article\s+\d+[a-z ]*)</h3>',
        fix_lowercase, content, flags=re.IGNORECASE
    )
    if new != content:
        fixes += 1
        content = new

    # Add missing Atenent que header
    if '<p class="recitals-init">' not in content and '<p class="recital">' in content:
        content = content.replace(
            '<p class="recital">', '<p class="recitals-init">Atenent que:</p>\n<p class="recital">', 1
        )
        fixes += 1

    if content != original:
        with open(f, 'w') as fh:
            fh.write(content)

    return fixes


def import_to_db(celex: str, title_ca: str, articles: int, recitals: int, size: int, engine: str,
                 file_type: str = 'main', oj_ref: str = '', parent_celex: str = '', annex_label: str = ''):
    """Import translation metadata to database."""
    from core.database import SessionLocal
    from models.catalan_translation import CatalanTranslation

    cat_ca, cat_en = classify_act(title_ca)
    doc_type = detect_doc_type(title_ca)

    # Detect annex label from title
    if not annex_label and file_type == 'annex':
        label_match = re.search(r'(ANNEX\s+[IVXLCDM]+(?:\s+[A-Z])?)', title_ca, re.IGNORECASE)
        if not label_match:
            label_match = re.search(r'(ANNEX\s+\d+)', title_ca, re.IGNORECASE)
        annex_label = label_match.group(1) if label_match else 'ANNEX'

    # Detect subcategory
    subcategory = detect_subcategory(title_ca)

    db = SessionLocal()
    try:
        existing = db.query(CatalanTranslation).filter_by(celex=celex).first()
        if existing:
            existing.title_ca = title_ca
            existing.articles_count = articles
            existing.recitals_count = recitals
            existing.html_size_bytes = size
            existing.category = cat_ca
            existing.category_en = cat_en
            if subcategory:
                existing.subcategory = subcategory
            if oj_ref:
                existing.oj_reference = oj_ref
            if file_type:
                existing.file_type = file_type
            if parent_celex:
                existing.parent_celex = parent_celex
            if annex_label:
                existing.annex_label = annex_label
        else:
            db.add(CatalanTranslation(
                celex=celex, title_en=title_ca, title_ca=title_ca,
                short_name=celex, doc_type=doc_type,
                category=cat_ca, category_en=cat_en,
                subcategory=subcategory,
                oj_reference=oj_ref or None,
                file_type=file_type,
                parent_celex=parent_celex or None,
                annex_label=annex_label or None,
                articles_count=articles, recitals_count=recitals,
                html_size_bytes=size, engine=engine, source_format='formex',
                siteground_url=f'https://brubru.beresol.eu/legislacio-ue-catala/{celex}/',
            ))
        db.commit()
    finally:
        db.close()


def translate_one(xml_path: str, celex: str) -> bool:
    """Translate a single act (no deploy). Returns True if successful."""
    cmd = [
        'python3.12', TRANSLATE_SCRIPT,
        '--translate', xml_path,
        '--celex', celex,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f'    [ERROR] Translation failed: {result.stderr[-200:] if result.stderr else "unknown"}')
        return False
    return True


def get_ftp_connection():
    """Open a persistent FTP connection for batch deploy."""
    import ftplib
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    load_dotenv(env_path)

    host = os.environ['SITEGROUND_FTP_HOST']
    user = os.environ['SITEGROUND_FTP_USER']
    password = os.environ['SITEGROUND_FTP_PASS']
    port = int(os.environ.get('SITEGROUND_FTP_PORT', '21'))

    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=60)
    ftp.login(user, password)
    ftp.cwd('brubru.beresol.eu/public_html/legislacio-ue-catala')
    return ftp


def deploy_with_verification(ftp, celex: str, max_retries: int = 3) -> bool:
    """Deploy a single CELEX with verification and retry. Returns True if confirmed on server."""
    local_file = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
    if not os.path.isfile(local_file):
        print(f'    [FTP ERROR] No local file for {celex}')
        return False

    local_size = os.path.getsize(local_file)

    for attempt in range(max_retries):
        try:
            # Create dir if needed
            remote_dirs = set(ftp.nlst())
            if celex not in remote_dirs:
                try:
                    ftp.mkd(celex)
                except Exception:
                    pass  # Dir may already exist

            ftp.cwd(celex)
            with open(local_file, 'rb') as f:
                ftp.storbinary('STOR index.html', f)

            # Verify: check remote size
            remote_size = ftp.size('index.html')
            ftp.cwd('..')

            if remote_size == local_size:
                return True
            else:
                print(f'    [FTP WARN] Size mismatch for {celex} (local={local_size}, remote={remote_size}), retry {attempt+1}')
        except Exception as e:
            print(f'    [FTP RETRY {attempt+1}/{max_retries}] {celex}: {e}')
            try:
                ftp.cwd('/brubru.beresol.eu/public_html/legislacio-ue-catala')
            except Exception:
                # Connection lost -- caller must reconnect
                raise

            import time
            time.sleep(1)

    print(f'    [FTP FAILED] {celex} after {max_retries} attempts')
    return False


def main():
    parser = argparse.ArgumentParser(description='Batch Catalan Translation Pipeline')
    parser.add_argument('--count', type=int, default=10, help='Number of acts to translate (default: 10)')
    parser.add_argument('--min-size', type=int, default=0, help='Minimum file size in KB')
    parser.add_argument('--max-size', type=int, default=999999, help='Maximum file size in KB')
    parser.add_argument('--file-type', type=str, default='main', choices=['main', 'annex', 'all'],
                        help='File type to translate: main (default), annex, or all')
    parser.add_argument('--start-from', type=str, default='', help='Start from this CELEX')
    parser.add_argument('--dry-run', action='store_true', help='Show queue without translating')
    parser.add_argument('--no-deploy', action='store_true', help='Skip FTP deploy')
    args = parser.parse_args()

    # Try full queue first, fall back to old queue
    FULL_QUEUE = os.path.join(TRANSLATIONS_DIR, 'translation_queue_full.txt')
    queue_file = FULL_QUEUE if os.path.exists(FULL_QUEUE) else QUEUE_FILE
    if not os.path.exists(queue_file):
        print(f'[ERROR] Queue file not found: {queue_file}')
        sys.exit(1)

    # Load queue
    with open(queue_file, 'r') as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]

    # Get already translated
    already = set()
    if os.path.isdir(TRANSLATIONS_DIR):
        already = {d for d in os.listdir(TRANSLATIONS_DIR)
                   if os.path.isdir(os.path.join(TRANSLATIONS_DIR, d)) and not d.endswith('-softcatala')}

    # Filter queue
    queue = []
    started = not args.start_from
    for line in lines:
        parts = line.split('|')
        if len(parts) < 3:
            continue
        # New format: path|celex|size_kb|file_type|oj_ref|parent_celex
        # Old format: path|celex|size_kb
        xml_path = parts[0]
        celex = parts[1]
        size_kb = int(parts[2])
        file_type = parts[3] if len(parts) > 3 else 'main'
        oj_ref = parts[4] if len(parts) > 4 else ''
        parent_celex = parts[5] if len(parts) > 5 else ''

        if args.start_from and celex == args.start_from:
            started = True
        if not started:
            continue

        if celex in already:
            continue
        if size_kb < args.min_size or size_kb > args.max_size:
            continue
        # Filter by file type
        if args.file_type != 'all' and file_type != args.file_type:
            continue

        queue.append((xml_path, celex, size_kb, file_type, oj_ref, parent_celex))

    print(f'[INFO] Queue: {len(queue)} acts (filtered from {len(lines)} total, {len(already)} already done)')
    print(f'[INFO] Translating up to {args.count} acts, type={args.file_type}, size {args.min_size}-{args.max_size}KB')
    print()

    if args.dry_run:
        for i, (path, celex, size_kb, ft, oj, parent) in enumerate(queue[:args.count]):
            parent_str = f' -> {parent}' if parent else ''
            print(f'  [{i+1:>3}] {celex:20s} | {size_kb:>5}KB | {ft:5s} | {os.path.basename(path)}{parent_str}')
        print(f'\n[DRY RUN] Would translate {min(args.count, len(queue))} acts')
        return

    # Open persistent FTP connection for the whole batch
    ftp = None
    if not args.no_deploy:
        try:
            ftp = get_ftp_connection()
            print(f'[INFO] FTP connection opened')
        except Exception as e:
            print(f'[ERROR] FTP connection failed: {e}')
            sys.exit(1)

    # Translate
    translated = 0
    failed = 0
    deploy_failed = []
    start_time = time.time()

    for i, (xml_path, celex, size_kb, file_type, oj_ref, parent_celex) in enumerate(queue[:args.count]):
        print(f'\n{"="*60}')
        ft_label = f' [{file_type}]' if file_type == 'annex' else ''
        print(f'[{i+1}/{min(args.count, len(queue))}] {celex} ({size_kb}KB){ft_label}')
        print(f'{"="*60}')

        # Translate (no deploy)
        success = translate_one(xml_path, celex)
        if not success:
            failed += 1
            continue

        # Audit (runs BEFORE deploy so fixes are uploaded)
        issues = audit_translation(celex)
        if issues:
            print(f'  [AUDIT] Issues found: {", ".join(issues)}')
            fixes = auto_fix(celex)
            if fixes:
                print(f'  [FIX] Applied {fixes} auto-fixes')
                issues = audit_translation(celex)
                if issues:
                    print(f'  [WARN] Remaining issues after fix: {", ".join(issues)}')

        # Deploy with verification (AFTER audit/fix)
        if ftp is not None:
            deploy_ok = False
            try:
                deploy_ok = deploy_with_verification(ftp, celex)
            except Exception as e:
                # Connection lost, reconnect and retry
                print(f'  [FTP RECONNECT] {e}')
                try:
                    ftp.quit()
                except Exception:
                    pass
                ftp = get_ftp_connection()
                try:
                    deploy_ok = deploy_with_verification(ftp, celex)
                except Exception as e2:
                    print(f'  [FTP FATAL] {celex}: {e2}')

            if not deploy_ok:
                deploy_failed.append(celex)
                print(f'  [DEPLOY FAILED] {celex} -- NOT proceeding to DB import')
                failed += 1
                continue
            else:
                print(f'  [DEPLOY] {celex} verified on SiteGround')

        # Get metadata from HTML
        html_path = os.path.join(TRANSLATIONS_DIR, celex, 'index.html')
        with open(html_path, 'r') as fh:
            content = fh.read()

        title_match = re.search(r'<title>(.*?)</title>', content)
        title_ca = title_match.group(1).replace(' | Brubru', '').strip() if title_match else celex
        articles = len(re.findall(r'class="article-title"', content)) - 1
        recitals = len(re.findall(r'class="recital"', content))
        html_size = os.path.getsize(html_path)

        # Import to DB
        try:
            import_to_db(celex, title_ca, max(articles, 0), recitals, html_size, 'softcatala',
                         file_type=file_type, oj_ref=oj_ref, parent_celex=parent_celex)
            print(f'  [DB] Imported {celex}')
        except Exception as e:
            print(f'  [DB ERROR] {e}')

        translated += 1
        elapsed = time.time() - start_time
        rate = elapsed / translated if translated else 0
        remaining = (min(args.count, len(queue)) - i - 1) * rate
        print(f'  [OK] {celex} | {articles} arts | {recitals} recs | {html_size//1024}KB | {rate:.0f}s/act | ~{remaining/60:.0f}min left')

    # Close FTP connection
    if ftp is not None:
        try:
            ftp.quit()
        except Exception:
            pass

    elapsed = time.time() - start_time
    print(f'\n{"="*60}')
    print(f'[DONE] Translated: {translated}, Failed: {failed}, Time: {elapsed/60:.1f}min')
    print(f'[STATS] Rate: {elapsed/max(translated,1):.0f}s/act')

    if deploy_failed:
        print(f'\n[WARN] {len(deploy_failed)} deploy failures: {deploy_failed[:10]}')
        sys.exit(1)


if __name__ == '__main__':
    main()
