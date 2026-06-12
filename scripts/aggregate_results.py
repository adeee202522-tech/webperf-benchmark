#!/usr/bin/env python3
"""
aggregate_results.py
汇总所有测点数据，生成 benchmark 报告（CSV + Markdown）
"""

import json
import csv
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def parse_lighthouse_json(path: Path) -> dict:
    """解析 Lighthouse JSON 报告"""
    try:
        with open(path) as f:
            data = json.load(f)
    except Exception as e:
        return {"error": str(e)}

    audits = data.get("audits", {})
    cats = data.get("categories", {})

    return {
        "url": data.get("finalUrl", path.stem),
        "timestamp": data.get("fetchTime", ""),
        # 性能指标
        "performance_score": round(cats.get("performance", {}).get("score", 0) * 100, 1) if cats.get("performance") else None,
        "ttfb_ms": audits.get("server-response-time", {}).get("numericValue", 0),
        "fcp_ms": audits.get("first-contentful-paint", {}).get("numericValue", 0),
        "lcp_ms": audits.get("largest-contentful-paint", {}).get("numericValue", 0),
        "cls": audits.get("cumulative-layout-shift", {}).get("numericValue", 0),
        "tbt_ms": audits.get("total-blocking-time", {}).get("numericValue", 0),
        "si_ms": audits.get("speed-index", {}).get("numericValue", 0),
        # 请求数
        "requests": audits.get("diagnostics", {}).get("details", {}).get("items", [{}])[0].get("numRequests", 0),
        "total_size_kb": audits.get("diagnostics", {}).get("details", {}).get("items", [{}])[0].get("totalPageWeightBytes", 0) / 1024,
        # 可用性
        "status": "success" if not data.get("runWarnings") else "warning",
    }


def parse_http_probe(path: Path) -> dict:
    """解析 HTTP 探测结果"""
    try:
        with open(path) as f:
            data = json.load(f)
        return {
            "url": data.get("url", path.stem),
            "ttfb_ms": data.get("ttfb_ms", 0),
            "status": data.get("status", "?"),
            "content_length": data.get("content_length", "?"),
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    data_dir = Path("./data")
    results = []

    # 扫描所有 Lighthouse JSON 文件
    for lhr in data_dir.rglob("lhr-*.json"):
        r = parse_lighthouse_json(lhr)
        r["source"] = "lighthouse"
        r["region"] = extract_region(lhr.name)
        results.append(r)

    # 扫描 HTTP 探测结果
    for probe in data_dir.rglob("*_http_probe.json"):
        r = parse_http_probe(probe)
        r["source"] = "http_probe"
        results.append(r)

    # 扫描 Cloudflare Radar 数据
    for radar in data_dir.rglob("*_speedtest.json"):
        try:
            with open(radar) as f:
                data = json.load(f)
            # Cloudflare Radar 格式解析（根据实际返回调整）
            r = {
                "url": radar.stem.replace("_speedtest", ""),
                "source": "cloudflare_radar",
                "timestamp": datetime.now().isoformat(),
                "raw_data": data,
            }
            results.append(r)
        except:
            pass

    # 输出 CSV
    csv_path = Path("./benchmark_results.csv")
    if results:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"CSV 保存到: {csv_path}")

    # 输出 Markdown 摘要
    md_path = Path("./benchmark_report.md")
    with open(md_path, "w") as f:
        f.write(f"# Web Performance Benchmark Report\n\n")
        f.write(f"生成时间: {datetime.now().isoformat()}\n\n")
        f.write(f"## 测试目标\n\n")
        targets = set(r.get("url", "") for r in results if not r.get("error"))
        for t in sorted(targets):
            f.write(f"- {t}\n")
        f.write(f"\n## 测试数据统计\n\n")
        f.write(f"| 指标 | 值 |\n|---|---|\n")
        f.write(f"| 总测点数 | {len(results)} |\n")
        f.write(f"| 数据来源 | {', '.join(sorted(set(r.get('source','') for r in results if r.get('source'))))} |\n\n")

        # Lighthouse 性能汇总
        lighthouse_results = [r for r in results if r.get("source") == "lighthouse"]
        if lighthouse_results:
            avg_ttfb = sum(r.get("ttfb_ms", 0) for r in lighthouse_results) / len(lighthouse_results)
            avg_fcp = sum(r.get("fcp_ms", 0) for r in lighthouse_results) / len(lighthouse_results)
            avg_lcp = sum(r.get("lcp_ms", 0) for r in lighthouse_results) / len(lighthouse_results)
            avg_score = sum(r.get("performance_score", 0) for r in lighthouse_results if r.get("performance_score")) / len(lighthouse_results)
            f.write(f"## Lighthouse 性能汇总\n\n")
            f.write(f"| 指标 | 平均值 |\n|---|---|\n")
            f.write(f"| Performance Score | {avg_score:.1f}/100 |\n")
            f.write(f"| TTFB | {avg_ttfb:.0f}ms |\n")
            f.write(f"| FCP | {avg_fcp:.0f}ms |\n")
            f.write(f"| LCP | {avg_lcp:.0f}ms |\n\n")

    print(f"报告保存到: {md_path}")
    print(f"\n共汇总 {len(results)} 条测试数据")


def extract_region(filename: str) -> str:
    """从文件名提取 region 标识"""
    # 例如: lhr-east-asia-southeast-asia-xxx.json
    parts = filename.split("-")
    if len(parts) >= 3:
        return "-".join(parts[1:-2])  # 去掉 lhr- 前缀和 hash 后缀
    return filename


if __name__ == "__main__":
    main()