#!/usr/bin/env python3
import csv
import sys
import argparse

PREFIXES = [
    'commission regulation',
    'council regulation',
    'annex',
    'council directive',
    'corrigendum',
]

def normalize_title(t: str) -> str:
    if t is None:
        return ''
    s = t.strip().lstrip('"\'\u201c\u201d').strip()
    return s

def should_exclude(title: str) -> bool:
    s = normalize_title(title).lower()
    for p in PREFIXES:
        if s.startswith(p):
            return True
    return False

def run(input_csv: str, output_csv: str) -> None:
    total = 0
    kept = 0
    with open(input_csv, newline='', encoding='utf-8') as f_in, \
         open(output_csv, 'w', newline='', encoding='utf-8') as f_out:
        rdr = csv.DictReader(f_in)
        # Input columns: file_path, type_of_law, title, year, policy_area
        fieldnames = ['type_of_law', 'title', 'year', 'policy_area']
        w = csv.DictWriter(f_out, fieldnames=fieldnames)
        w.writeheader()
        for row in rdr:
            total += 1
            title = row.get('title', '')
            if should_exclude(title):
                continue
            w.writerow({
                'type_of_law': row.get('type_of_law', ''),
                'title': normalize_title(title),
                'year': row.get('year', ''),
                'policy_area': row.get('policy_area', ''),
            })
            kept += 1
    print(f"Processed: {total}, kept: {kept}, removed: {total - kept}")

def main():
    ap = argparse.ArgumentParser(description='Post-process reg/dir CSV: drop path column and exclude certain title prefixes.')
    ap.add_argument('--input', required=True)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    run(args.input, args.output)

if __name__ == '__main__':
    main()

