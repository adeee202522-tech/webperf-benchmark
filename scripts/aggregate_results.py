#!/usr/bin/env python3
import json, os, glob, csv
from tabulate import tabulate
from collections import defaultdict

# 只处理本轮 run_id 的 artifacts（文件名包含 run_id）
CURRENT_RUN_ID = os.environ.get('GITHUB_RUN_ID', '')
print(f"Filtering for run_id: {CURRENT_RUN_ID}")

files = glob.glob('./results/run_*.json')
if not files:
    print("No results found")
    exit(0)

# 过滤：只取文件名时间戳 >= 某阈值（取当前时间前1小时内）
import time
ONE_HOUR_AGO = time.time() * 1000 - 3600 * 1000

valid_files = []
for f in files:
    ts = int(os.path.basename(f).replace('run_', '').replace('.json', ''))
    if ts > ONE_HOUR_AGO:
        valid_files.append((ts, f))

if not valid_files:
    print("No recent results (within 1 hour)")
    exit(0)

valid_files.sort(key=lambda x: -x[0])
print(f"Found {len(valid_files)} recent result files")

all_results = []
for ts, fpath in valid_files:
    with open(fpath) as fh:
        raw = json.load(fh)

    if isinstance(raw, list):
        all_results.extend(raw)
        continue

    target = raw.get('target', '?')

    # 新格式：raw['runs'] = 每次运行的详细结果（含不同 exit_ip）
    runs = raw.get('runs', [])
    for r in runs:
        if isinstance(r, dict) and r.get('status') == 'ok':
            r['target'] = target
            r['run_timestamp'] = ts
            all_results.append(r)

    # 旧格式 fallback
    if not runs:
        for r in raw.get('results', []):
            if isinstance(r, dict):
                all_results.append(r)

if not all_results:
    print("No valid results")
    exit(0)

# 按地区分组统计
print(f"\n=== 客户分布（{len(all_results)} 个数据点）===\n")
region_stats = defaultdict(list)
for r in all_results:
    region = r.get('region_detail', r.get('region', 'unknown'))
    region_stats[region].append(r)

print(f"{'地区/ISP':<35} {'次数':>4} {'TTFB均值':>8} {'LCP均值':>8} {'CLS均值':>8}")
print("-" * 70)
for region, rs in sorted(region_stats.items(), key=lambda x: -len(x[1])):
    ttfb_avg = sum(r.get('ttfb', 0) for r in rs) / len(rs)
    lcp_avg = sum(r.get('lcp', 0) for r in rs) / len(rs)
    cls_avg = sum(r.get('cls', 0) for r in rs) / len(rs)
    print(f"{region:<35} {len(rs):>4} {ttfb_avg:>7.0f}ms {lcp_avg:>7.0f}ms {cls_avg:>8.4f}")

print(f"\n=== 详细数据 ===\n")
rows = []
for r in all_results:
    lcp = r.get('lcp', 0)
    lcp_tag = 'OK' if lcp <= 2500 else ('WARN' if lcp <= 4000 else 'FAIL')
    cls = r.get('cls', 0)
    cls_tag = 'OK' if cls <= 0.1 else ('WARN' if cls <= 0.25 else 'FAIL')
    rows.append([
        r.get('target', '?'),
        r.get('region_detail', '?'),
        r.get('exit_ip', '?'),
        r.get('ttfb', 0),
        r.get('fcp', 0),
        f"{lcp} ({lcp_tag})",
        f"{cls:.4f} ({cls_tag})",
    ])

headers = ['目标', '地区', '出口IP', 'TTFB', 'FCP', 'LCP', 'CLS']
print(tabulate(rows, headers=headers, tablefmt='grid'))
print()
print("LCP: OK<=2500ms WARN 2500-4000ms FAIL>4000ms")
print("CLS: OK<=0.1 WARN 0.1-0.25 FAIL>0.25")

# 保存 CSV
with open('benchmark_summary.csv', 'w', newline='') as cf:
    w = csv.DictWriter(cf, fieldnames=['target', 'region_detail', 'exit_ip', 'ttfb', 'fcp', 'lcp', 'cls', 'status'])
    w.writeheader()
    for r in all_results:
        if isinstance(r, dict) and r.get('status') == 'ok':
            w.writerow({k: r.get(k, '') for k in ['target', 'region_detail', 'exit_ip', 'ttfb', 'fcp', 'lcp', 'cls', 'status']})
print(f"\nCSV saved: benchmark_summary.csv ({len(all_results)} rows)")