#!/usr/bin/env python3
import csv
import argparse

def to_int_year(y: str) -> int:
    try:
        return int(y)
    except Exception:
        return 9999

def sort_by_year(input_csv: str, output_csv: str) -> None:
    with open(input_csv, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: (to_int_year(r.get('year','')), r.get('policy_area',''), r.get('type_of_law',''), r.get('title','')))
    with open(output_csv, 'w', newline='', encoding='utf-8') as out:
        w = csv.DictWriter(out, fieldnames=['type_of_law','title','year','policy_area'])
        w.writeheader()
        w.writerows(rows)

def sort_by_policy_then_year(input_csv: str, output_csv: str) -> None:
    with open(input_csv, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    # Drop rows without a policy area
    rows = [r for r in rows if r.get('policy_area', '').strip()]
    rows.sort(key=lambda r: (r.get('policy_area',''), to_int_year(r.get('year','')), r.get('type_of_law',''), r.get('title','')))
    with open(output_csv, 'w', newline='', encoding='utf-8') as out:
        w = csv.DictWriter(out, fieldnames=['type_of_law','title','year','policy_area'])
        w.writeheader()
        w.writerows(rows)

def main():
    ap = argparse.ArgumentParser(description='Sort reg/dir CSV by year or by policy area then year.')
    ap.add_argument('--input', required=True)
    ap.add_argument('--by-year', required=True)
    ap.add_argument('--by-policy', required=True)
    args = ap.parse_args()
    sort_by_year(args.input, args.by_year)
    sort_by_policy_then_year(args.input, args.by_policy)
    print('Wrote:', args.by_year)
    print('Wrote:', args.by_policy)

if __name__ == '__main__':
    main()
