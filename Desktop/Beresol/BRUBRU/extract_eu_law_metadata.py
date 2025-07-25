import os
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm
import re
from collections import Counter
import csv

# 1) Configure paths
input_folder = '/Users/victorsole/Desktop/Beresol/BRUBRU/EU Law'
output_csv = '/Users/victorsole/Desktop/Beresol/BRUBRU/eu_laws.csv'

# 2) Prepare data structures
rows = []  # collect all records
counts = Counter({
    'Delegated Act': 0,
    'Implementing Act': 0,
    'Recommendation': 0,
    'Commission Directive': 0,
    'Commission Regulation': 0,
    'Commission Implementing Regulation': 0,
    'Commission Delegated Regulation': 0,
    'Council Regulation': 0,
    'Council Decision': 0,
    'Commission Implementing Decision': 0,
    'Regulation': 0,
    'Directive': 0,
    'Decision': 0,
    'Other': 0
})

# 3) Helpers
# 3.1) Clean CELEX code
def clean_celex(raw: str) -> str:
    """
    Turn any URL / meta content / filename into a plain CELEX code,
    e.g. 32003M3035.
    """
    if not raw:
        return ""
    m = re.search(r'CELEX:([0-9A-Z]+)', raw, re.I)
    if m:
        return m.group(1)
    return os.path.splitext(os.path.basename(raw))[0]

# 3.2) Extract human-readable title
def extract_title(soup: BeautifulSoup) -> str:
    """
    Extract a human-readable title using multiple fallbacks:
      1) <meta name="DCTERMS.title"> or <meta name="DC.title">
      2) <div class="eli-main-title"> block
      3) <meta name="DC.description">
      4) <p class="doc-ti">
      5) <h1> or <h2>
      6) <p class="ti">
      7) <title>
    """
    # 3.1.1) Official meta title
    mt = soup.find("meta", attrs={"name": "DCTERMS.title"}) or soup.find("meta", attrs={"name": "DC.title"})
    if mt and mt.get("content"):
        return mt["content"].strip()

    # 3.1.2) ELI main-title block
    eli = soup.find("div", class_="eli-main-title")
    if eli:
        parts = eli.find_all("p", class_="oj-doc-ti")
        text = " ".join(p.get_text(strip=True) for p in parts)
        if text:
            return text

    # 3.1.3) DC.description meta
    desc = soup.find("meta", attrs={"name": "DC.description"})
    if desc and desc.get("content"):
        return desc["content"].strip()

    # 3.1.4) <p class="doc-ti">
    doc_ti = soup.find("p", class_="doc-ti")
    if doc_ti:
        return doc_ti.get_text(strip=True)

    # 3.1.5) Headings
    heading = soup.find("h1") or soup.find("h2")  # Ensure this line is properly closed
    if heading:
        return heading.get_text(strip=True)

    # 3.1.6) Very old OJ dumps
    p_ti = soup.find("p", class_="ti")
    if p_ti:
        return p_ti.get_text(strip=True)

    # 3.1.7) Fallback browser title tag
    tt = soup.find("title")
    return tt.get_text(strip=True) if tt else ""

# 6) Loop through HTML files
for filename in tqdm(os.listdir(input_folder), desc="Processing files"):
    if not filename.lower().endswith('.html'):
        continue
    filepath = os.path.join(input_folder, filename)
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f, 'html.parser')

        # 6.1) CELEX extraction
        meta_celex = soup.find('meta', attrs={'name': 'DC.identifier'}) or soup.find('meta', attrs={'name': 'DCTERMS.identifier'})
        raw_celex = meta_celex['content'].strip() if meta_celex and meta_celex.get('content') else filename
        celex = clean_celex(raw_celex)

        # 6.2) Title extraction
        title = extract_title(soup)
        if not title:
            title = 'Untitled'

        # 6.3) Type classification
        tl = title.lower()
        if 'delegated act' in tl:
            act_type = 'Delegated Act'
        elif 'implementing act' in tl:
            act_type = 'Implementing Act'
        elif 'recommendation' in tl:
            act_type = 'Recommendation'
        elif 'commission directive' in tl:
            act_type = 'Commission Directive'
        elif 'commission regulation' in tl:
            act_type = 'Commission Regulation'
        elif 'commission implementing regulation' in tl:
            act_type = 'Commission Implementing Regulation'
        elif 'commission delegated regulation' in tl:
            act_type = 'Commission Delegated Regulation'
        elif 'council regulation' in tl:
            act_type = 'Council Regulation'
        elif 'council decision' in tl:
            act_type = 'Council Decision'
        elif 'commission implementing decision' in tl:
            act_type = 'Commission Implementing Decision'
        elif 'regulation' in tl:
            act_type = 'Regulation'
        elif 'directive' in tl:
            act_type = 'Directive'
        elif 'decision' in tl:
            act_type = 'Decision'
        elif re.match(r'\d{4}R', celex):
            act_type = 'Regulation'
        elif re.match(r'\d{4}L', celex):
            act_type = 'Directive'
        elif re.match(r'\d{4}D', celex):
            act_type = 'Decision'
        else:
            act_type = 'Other'

        counts[act_type] += 1
        rows.append({'CELEX': celex, 'Title': title, 'Type': act_type})
    except Exception as e:
        print(f"⚠️ Skipping {filename}: {e}")
        rows.append({'CELEX': filename, 'Title': f"[ERROR: {e.__class__.__name__}]", 'Type': 'Other'})

# 7) Save results
print("Counts by type:")
for t, c in counts.items():
    print(f"{t}: {c}")

df = pd.DataFrame(rows)
df.to_csv(output_csv, index=False)
print(f"Saved {len(rows)} records to {output_csv}")
