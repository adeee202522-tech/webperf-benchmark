#!/usr/bin/env python3
import json, os, glob, csv
from tabulate import tabulate

files = glob.glob('./results/run_*.json')
if not files:
    print("No results found")
    exit(0)

print("Found result files:", [os.path.basename(f) for f in files])

all_results = []
for fpath in files:
    with open(fpath) as fh:
        data = json.load(fh)
        if isinstance(data, list):
            all_results.extend(data)
        elif isinstance(data, dict) and 'results' in data:
            all_results.extend(data['results'])

if not all_results:
    print("No valid results found")
    exit(0)

rows = []
for r in all_results:
    if not isinstance(r, dict):
        continue
    if r.get('status') != 'ok':
        continue
    lcp = r.get('lcp', 0)
    lcp_tag = 'OK' if lcp <= 2500 else ('WARN' if lcp <= 4000 else 'FAIL')
    cls = r.get('cls', 0)
    cls_tag = 'OK' if cls <= 0.1 else ('WARN' if cls <= 0.25 else 'FAIL')
    rows.append([
        r.get('url', '').replace('https://', ''),
        r.get('ttfb', 0),
        r.get('fcp', 0),
        f"{lcp} ({lcp_tag})",
        f"{cls:.4f} ({cls_tag})",
        r.get('load', 0),
        r.get('resourceCount', 0),
    ])

headers = ['URL', 'TTFB(ms)', 'FCP(ms)', 'LCP(ms)', 'CLS', 'Load(ms)', 'Resources']
print(f"\n## Web Performance Report\n")
print(f"**数据点数**: {len(all_results)}")
print()
print(tabulate(rows, headers=headers, tablefmt='grid'))
print()
print("LCP: OK<=2500ms WARN 2500-4000ms FAIL>4000ms")
print("CLS: OK<=0.1 WARN 0.1-0.25 FAIL>0.25")

with open('benchmark_summary.csv', 'w', newline='') as cf:
    w = csv.DictWriter(cf, fieldnames=['url', 'ttfb', 'fcp', 'lcp', 'cls', 'load', 'resourceCount', 'status'])
    w.writeheader()
    for r in all_results:
        if isinstance(r, dict) and r.get('status') == 'ok':
            w.writerow({k: r.get(k, '') for k in ['url', 'ttfb', 'fcp', 'lcp', 'cls', 'load', 'resourceCount', 'status']})
print("\nCSV saved: benchmark_summary.csv")