#!/usr/bin/env python3
"""
Generate static charts (SVG/PNG if available) and a JSON snapshot from the
two curated CSVs:

  - docs/LEG_2025-11_reg_dir_classification.by_year.csv
  - docs/LEG_2025-11_reg_dir_classification.by_policy_area.csv

Outputs:
  - frontend/public/analytics/eu_law_by_year.svg
  - frontend/public/analytics/eu_law_by_policy_area.svg
  - frontend/public/analytics/eu_law_heatmap.svg
  - If matplotlib is available, also write .png variants for each
  - backend/knowledge_base/analytics/eu_law_snapshot.json
  - frontend/public/analytics/eu_law_snapshot.json

Designed to run locally every few months, with no network access.
Falls back to a lightweight SVG renderer when matplotlib is unavailable.
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict, OrderedDict
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Helpers: CSV loading and aggregation
# ---------------------------------------------------------------------------

def read_csv(path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, newline='', encoding='utf-8') as f:
        rdr = csv.DictReader(f)
        for r in rdr:
            rows.append(r)
    return rows


def to_int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except Exception:
        return default


def aggregate_by_year(rows: List[Dict[str, str]]) -> Tuple[List[int], Dict[int, Dict[str, int]]]:
    years_set = set()
    by_year: Dict[int, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        y = to_int(r.get('year', ''), default=0)
        if y <= 0:
            continue
        t = (r.get('type_of_law') or '').strip() or 'Unknown'
        years_set.add(y)
        by_year[y][t] += 1
    years = sorted(years_set)
    return years, by_year


def aggregate_by_policy_area(rows: List[Dict[str, str]]) -> Tuple[List[str], Dict[str, Dict[str, int]]]:
    areas_set = set()
    by_area: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in rows:
        area = (r.get('policy_area') or '').strip()
        if not area:
            continue
        t = (r.get('type_of_law') or '').strip() or 'Unknown'
        areas_set.add(area)
        by_area[area][t] += 1
    areas = sorted(areas_set)
    return areas, by_area


def aggregate_heatmap(rows: List[Dict[str, str]]) -> Tuple[List[str], List[int], Dict[Tuple[str, int], int]]:
    # Using policy-area CSV to build (area, year) counts
    areas_set = set()
    years_set = set()
    counts: Dict[Tuple[str, int], int] = defaultdict(int)
    for r in rows:
        area = (r.get('policy_area') or '').strip()
        y = to_int(r.get('year', ''), 0)
        if not area or y <= 0:
            continue
        areas_set.add(area)
        years_set.add(y)
        counts[(area, y)] += 1
    areas = sorted(areas_set)
    years = sorted(years_set)
    return areas, years, counts


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# ---------------------------------------------------------------------------
# Matplotlib renderer (if available)
# ---------------------------------------------------------------------------

def try_import_matplotlib():
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        return matplotlib, plt, np
    except Exception:
        return None, None, None


def plot_with_matplotlib(
    out_dir_public: str,
    years: List[int],
    by_year: Dict[int, Dict[str, int]],
    areas: List[str],
    by_area: Dict[str, Dict[str, int]],
    hm_areas: List[str],
    hm_years: List[int],
    hm_counts: Dict[Tuple[str, int], int],
):
    _, plt, np = try_import_matplotlib()
    if plt is None:
        return False

    # Colors
    c_reg = '#2E86AB'
    c_dir = '#F39C12'

    # By Year (stacked)
    fig, ax = plt.subplots(figsize=(12, 6))
    regs = np.array([by_year.get(y, {}).get('Regulation', 0) for y in years])
    dirs = np.array([by_year.get(y, {}).get('Directive', 0) for y in years])
    ax.bar(years, regs, color=c_reg, label='Regulation')
    ax.bar(years, dirs, bottom=regs, color=c_dir, label='Directive')
    totals = regs + dirs
    ax.plot(years, totals, color='#555555', linewidth=1.5, label='Total')
    for x, t in zip(years, totals):
        ax.text(x, t + max(1, totals.max()*0.01), str(int(t)), ha='center', va='bottom', fontsize=8)
    ax.set_title('EU Law by Year (Regulation vs Directive)')
    ax.set_xlabel('Year')
    ax.set_ylabel('Count')
    ax.legend()
    ax.grid(axis='y', alpha=0.2)
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir_public, 'eu_law_by_year.svg'))
    fig.savefig(os.path.join(out_dir_public, 'eu_law_by_year.png'), dpi=180)
    plt.close(fig)

    # By Policy Area (horizontal stacked)
    fig, ax = plt.subplots(figsize=(12, max(6, len(areas) * 0.25)))
    regs_a = np.array([by_area.get(a, {}).get('Regulation', 0) for a in areas])
    dirs_a = np.array([by_area.get(a, {}).get('Directive', 0) for a in areas])
    y = np.arange(len(areas))
    ax.barh(y, regs_a, color=c_reg, label='Regulation')
    ax.barh(y, dirs_a, left=regs_a, color=c_dir, label='Directive')
    for yi, r, d in zip(y, regs_a, dirs_a):
        total = int(r + d)
        ax.text(r + d + max(0.5, (r+d)*0.01), yi, str(total), va='center', fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(areas)
    ax.set_xlabel('Count')
    ax.set_title('EU Law by Policy Area (All Areas)')
    ax.legend()
    ax.grid(axis='x', alpha=0.2)
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir_public, 'eu_law_by_policy_area.svg'))
    fig.savefig(os.path.join(out_dir_public, 'eu_law_by_policy_area.png'), dpi=200)
    plt.close(fig)

    # Heatmap (policy area x year)
    fig, ax = plt.subplots(figsize=(12, max(6, len(hm_areas) * 0.25)))
    mat = np.zeros((len(hm_areas), len(hm_years)))
    for i, a in enumerate(hm_areas):
        for j, y in enumerate(hm_years):
            mat[i, j] = hm_counts.get((a, y), 0)
    im = ax.imshow(mat, aspect='auto', cmap='viridis', origin='lower')
    ax.set_xticks(np.arange(len(hm_years)))
    ax.set_xticklabels(hm_years, rotation=45, ha='right', fontsize=8)
    ax.set_yticks(np.arange(len(hm_areas)))
    ax.set_yticklabels(hm_areas, fontsize=8)
    ax.set_title('EU Law Heatmap (Policy Area × Year)')
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label('Count')
    plt.tight_layout()
    fig.savefig(os.path.join(out_dir_public, 'eu_law_heatmap.svg'))
    fig.savefig(os.path.join(out_dir_public, 'eu_law_heatmap.png'), dpi=200)
    plt.close(fig)

    return True


# ---------------------------------------------------------------------------
# Lightweight SVG renderer (fallback)
# ---------------------------------------------------------------------------

def _viridis_rgb(v: float) -> str:
    # Approximate viridis with a simple gradient between dark blue -> green -> yellow
    v = max(0.0, min(1.0, v))
    if v < 0.5:
        t = v / 0.5
        r, g, b = 68*(1-t) + 33*t, 1*(1-t) + 145*t, 84*(1-t) + 140*t
    else:
        t = (v - 0.5) / 0.5
        r, g, b = 33*(1-t) + 253*t, 145*(1-t) + 231*t, 140*(1-t) + 37*t
    return f'rgb({int(r)},{int(g)},{int(b)})'


def svg_rect(x, y, w, h, fill, stroke='none'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" />\n'


def svg_text(x, y, text, size=10, anchor='start'):  # anchor: start|middle|end
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-family="DejaVu Sans, Arial, sans-serif">{text}</text>\n'


def write_svg_by_year(path: str, years: List[int], by_year: Dict[int, Dict[str, int]]):
    W, H = 1200, 600
    ml, mr, mt, mb = 80, 20, 30, 60
    inner_w, inner_h = W-ml-mr, H-mt-mb
    reg_color, dir_color = '#2E86AB', '#F39C12'

    totals = [by_year.get(y, {}).get('Regulation', 0) + by_year.get(y, {}).get('Directive', 0) for y in years]
    y_max = max(1, max(totals))
    bar_gap = 4
    bar_w = max(4, int(inner_w / max(1, len(years)) - bar_gap))

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">\n']
    out.append(svg_text(ml, mt-10, 'EU Law by Year (Regulation vs Directive)', size=14))
    # Axes
    out.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{H-mb}" stroke="#333"/>\n')
    out.append(f'<line x1="{ml}" y1="{H-mb}" x2="{W-mr}" y2="{H-mb}" stroke="#333"/>\n')

    # Y ticks
    for k in range(0, 6):
        val = int(y_max * k / 5)
        y = H-mb - (val/y_max)*inner_h
        out.append(f'<line x1="{ml}" y1="{y}" x2="{W-mr}" y2="{y}" stroke="#ddd"/>\n')
        out.append(svg_text(ml-8, y+4, str(val), size=9, anchor='end'))

    # Bars
    x = ml
    for yv in years:
        reg = by_year.get(yv, {}).get('Regulation', 0)
        direc = by_year.get(yv, {}).get('Directive', 0)
        tot = reg + direc
        bh_tot = (tot/y_max)*inner_h
        bh_reg = (reg/y_max)*inner_h
        x0 = x + (bar_gap/2)
        # Regulation (bottom)
        out.append(svg_rect(x0, H-mb - bh_reg, bar_w, bh_reg, reg_color))
        # Directive (stacked)
        out.append(svg_rect(x0, H-mb - bh_tot, bar_w, bh_tot - bh_reg, dir_color))
        # Year label
        out.append(svg_text(x0 + bar_w/2, H-mb + 14, str(yv), size=9, anchor='middle'))
        # Total label
        out.append(svg_text(x0 + bar_w/2, H-mb - bh_tot - 4, str(int(tot)), size=8, anchor='middle'))
        x += bar_w + bar_gap

    # Legend
    lx, ly = W-mr-220, mt+10
    out.append(svg_rect(lx, ly, 12, 12, reg_color))
    out.append(svg_text(lx+18, ly+11, 'Regulation', size=10))
    out.append(svg_rect(lx, ly+20, 12, 12, dir_color))
    out.append(svg_text(lx+18, ly+31, 'Directive', size=10))

    out.append('</svg>\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(out))


def write_svg_by_policy_area(path: str, areas: List[str], by_area: Dict[str, Dict[str, int]]):
    # Dynamic height based on number of areas
    H = max(400, 24*len(areas) + 80)
    W = 1200
    ml, mr, mt, mb = 220, 30, 30, 40
    inner_w, inner_h = W-ml-mr, H-mt-mb
    reg_color, dir_color = '#2E86AB', '#F39C12'

    totals = [by_area.get(a, {}).get('Regulation', 0) + by_area.get(a, {}).get('Directive', 0) for a in areas]
    x_max = max(1, max(totals))

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">\n']
    out.append(svg_text(ml, mt-10, 'EU Law by Policy Area (All Areas)', size=14))
    # Axes
    out.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{H-mb}" stroke="#333"/>\n')
    out.append(f'<line x1="{ml}" y1="{H-mb}" x2="{W-mr}" y2="{H-mb}" stroke="#333"/>\n')

    # X ticks
    for k in range(0, 6):
        val = int(x_max * k / 5)
        x = ml + (val/x_max)*inner_w
        out.append(f'<line x1="{x}" y1="{mt}" x2="{x}" y2="{H-mb}" stroke="#eee"/>\n')
        out.append(svg_text(x, H-mb+16, str(val), size=9, anchor='middle'))

    # Bars
    row_h = inner_h/len(areas)
    bar_h = max(6, row_h*0.6)
    for i, area in enumerate(areas):
        y = mt + i*row_h + (row_h-bar_h)/2
        reg = by_area.get(area, {}).get('Regulation', 0)
        direc = by_area.get(area, {}).get('Directive', 0)
        total = reg + direc
        w_reg = (reg/x_max)*inner_w
        w_dir = (direc/x_max)*inner_w
        # Labels (area name)
        out.append(svg_text(ml-10, y+bar_h*0.75, area, size=10, anchor='end'))
        # Bars
        out.append(svg_rect(ml, y, w_reg, bar_h, reg_color))
        out.append(svg_rect(ml + w_reg, y, w_dir, bar_h, dir_color))
        # Value label
        out.append(svg_text(ml + w_reg + w_dir + 6, y+bar_h*0.75, str(int(total)), size=10))

    # Legend
    lx, ly = W-mr-220, mt+10
    out.append(svg_rect(lx, ly, 12, 12, reg_color))
    out.append(svg_text(lx+18, ly+11, 'Regulation', size=10))
    out.append(svg_rect(lx, ly+20, 12, 12, dir_color))
    out.append(svg_text(lx+18, ly+31, 'Directive', size=10))

    out.append('</svg>\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(out))


def write_svg_heatmap(path: str, areas: List[str], years: List[int], counts: Dict[Tuple[str, int], int]):
    cell_w, cell_h = 24, 16
    ml, mr, mt, mb = 220, 40, 40, 60
    W = ml + mr + cell_w*len(years)
    H = mt + mb + cell_h*len(areas)

    # Compute max value for normalization
    vmax = 0
    for a in areas:
        for y in years:
            vmax = max(vmax, counts.get((a, y), 0))
    vmax = max(1, vmax)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">\n']
    out.append(svg_text(ml, mt-16, 'EU Law Heatmap (Policy Area × Year)', size=14))

    # Axes/grid
    # Y labels
    for i, area in enumerate(areas):
        y = mt + i*cell_h + cell_h*0.7
        out.append(svg_text(ml-10, y, area, size=10, anchor='end'))

    # X labels
    for j, year in enumerate(years):
        x = ml + j*cell_w + cell_w/2
        out.append(svg_text(x, H-mb+14, str(year), size=9, anchor='middle'))

    # Cells
    for i, area in enumerate(areas):
        for j, year in enumerate(years):
            v = counts.get((area, year), 0)
            color = _viridis_rgb(v / vmax)
            x = ml + j*cell_w
            y = mt + i*cell_h
            out.append(svg_rect(x, y, cell_w-1, cell_h-1, color))

    # Simple colorbar
    cb_x, cb_y, cb_w, cb_h = W - 24, mt, 12, cell_h*len(areas)
    for k in range(0, 101):
        yy = cb_y + (1 - k/100.0)*cb_h
        out.append(svg_rect(cb_x, yy, cb_w, cb_h/100.0 + 1, _viridis_rgb(k/100.0), stroke='none'))
    out.append(svg_text(cb_x-4, cb_y+10, str(vmax), size=9, anchor='end'))
    out.append(svg_text(cb_x-4, cb_y+cb_h, '0', size=9, anchor='end'))

    out.append('</svg>\n')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(''.join(out))


# ---------------------------------------------------------------------------
# Snapshot JSON
# ---------------------------------------------------------------------------

def build_snapshot(years: List[int], by_year: Dict[int, Dict[str, int]], areas: List[str], by_area: Dict[str, Dict[str, int]]):
    totals_by_type = defaultdict(int)
    for y in years:
        for t, c in by_year.get(y, {}).items():
            totals_by_type[t] += c
    per_year = OrderedDict()
    for y in years:
        reg = by_year.get(y, {}).get('Regulation', 0)
        direc = by_year.get(y, {}).get('Directive', 0)
        per_year[str(y)] = {'Regulation': reg, 'Directive': direc, 'total': reg+direc}
    per_area = OrderedDict()
    for a in areas:
        reg = by_area.get(a, {}).get('Regulation', 0)
        direc = by_area.get(a, {}).get('Directive', 0)
        per_area[a] = {'Regulation': reg, 'Directive': direc, 'total': reg+direc}
    snapshot = {
        'totals_by_type': dict(totals_by_type),
        'years': years,
        'per_year': per_year,
        'policy_areas': areas,
        'per_policy_area': per_area,
        'min_year': years[0] if years else None,
        'max_year': years[-1] if years else None,
    }
    return snapshot


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    by_year_csv = 'docs/LEG_2025-11_reg_dir_classification.by_year.csv'
    by_area_csv = 'docs/LEG_2025-11_reg_dir_classification.by_policy_area.csv'

    if not os.path.exists(by_year_csv) or not os.path.exists(by_area_csv):
        print('Missing input CSV(s). Ensure the two classification CSVs exist.', file=sys.stderr)
        sys.exit(1)

    rows_year = read_csv(by_year_csv)
    rows_area = read_csv(by_area_csv)

    years, by_year = aggregate_by_year(rows_year)
    areas, by_area = aggregate_by_policy_area(rows_area)
    hm_areas, hm_years, hm_counts = aggregate_heatmap(rows_area)

    # Output dirs
    out_public = 'frontend/public/analytics'
    out_kb = 'backend/knowledge_base/analytics'
    ensure_dir(out_public)
    ensure_dir(out_kb)

    # Try matplotlib first
    ok = plot_with_matplotlib(out_public, years, by_year, areas, by_area, hm_areas, hm_years, hm_counts)
    if not ok:
        # Write minimal but clean SVGs
        write_svg_by_year(os.path.join(out_public, 'eu_law_by_year.svg'), years, by_year)
        write_svg_by_policy_area(os.path.join(out_public, 'eu_law_by_policy_area.svg'), areas, by_area)
        write_svg_heatmap(os.path.join(out_public, 'eu_law_heatmap.svg'), hm_areas, hm_years, hm_counts)

    # Snapshot JSON
    snapshot = build_snapshot(years, by_year, areas, by_area)
    snap_json = json.dumps(snapshot, indent=2)
    with open(os.path.join(out_kb, 'eu_law_snapshot.json'), 'w', encoding='utf-8') as f:
        f.write(snap_json)
    # Also copy under public for the frontend to fetch without a new API
    with open(os.path.join(out_public, 'eu_law_snapshot.json'), 'w', encoding='utf-8') as f:
        f.write(snap_json)

    print('Charts and snapshot generated successfully.')


if __name__ == '__main__':
    main()

