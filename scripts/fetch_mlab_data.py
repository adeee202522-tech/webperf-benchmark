#!/usr/bin/env python3
"""
fetch_mlab_data.py
通过 M-Lab (Measurement Lab) NDT 数据分析目标站点的网络性能
M-Lab 提供全球网络速度测量数据

使用方法:
  python3 fetch_mlab_data.py --domain tsinghua.edu.cn --days 30
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# M-Lab BigQuery 公开数据集查询
# 这是只读公开查询，不需要 M-Lab 账号

MLAB_BQ_PROJECT = "measurement-lab"
MLAB_BQ_DATASET = "ndt"
MLAB_BQ_TABLE = "ndt_uploader"

TARGETS = [
    "tsinghua.edu.cn",
    "sigs.tsinghua.edu.cn",
    "pku.edu.cn",
    "zju.edu.cn",
    "fudan.edu.cn",
]

def query_mlab_speedtest(domain: str, days: int = 30) -> dict:
    """
    查询 M-Lab NDT 数据（网络速度测试结果）
    注意：这是全球用户测速数据，不是专门针对某个网站的
    M-Lab 主要测互联网带宽，不是网站性能
    这里用于获取"中国到全球"的网络基线
    """
    bq_sql = f"""
    SELECT
      date,
      a_country AS client_country,
      a_city AS client_city,
      download_speed_mbps_median,
      upload_speed_mbps_median,
      min_rtt_ms,
      COUNT(*) AS test_count
    FROM (
      SELECT
        DATE(submit_time) AS date,
        web100_log_entry.connection_spec.remote_address,
        remote_ip AS a_ip,
        country AS a_country,
        city AS a_city,
        download_speed_mbps_median,
        upload_speed_mbps_median,
        min_rtt_ms
      FROM `{MLAB_BQ_PROJECT}.{MLAB_BQ_DATASET}.{MLAB_BQ_TABLE}`
      WHERE
        DATE(submit_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
        AND (remote_ip LIKE '202.%%' OR remote_ip LIKE '218.%%' OR remote_ip LIKE '58.%%')
    )
    GROUP BY date, a_country, a_city, download_speed_mbps_median, upload_speed_mbps_median, min_rtt_ms
    ORDER BY test_count DESC
    LIMIT 100
    """

    cmd = [
        "bq", "query",
        "--project_id", MLAB_BQ_PROJECT,
        "--use_legacy_sql=false",
        "--format=json",
        bq_sql
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return {"status": "ok", "data": json.loads(result.stdout)}
        else:
            return {"status": "error", "message": result.stderr}
    except FileNotFoundError:
        return {"status": "error", "message": "bq CLI not found. Install: gcloud components install bq"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def fetch_via_http(url: str) -> dict:
    """
    使用 curl 通过 HTTP HEAD 测量基本连接指标
    """
    import urllib.request
    import time

    try:
        start = time.time()
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "WebPerf-Benchmark/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            ttfb = (time.time() - start) * 1000
            return {
                "url": url,
                "status": resp.status,
                "ttfb_ms": round(ttfb, 2),
                "headers": dict(resp.headers),
                "content_length": resp.headers.get("Content-Length"),
            }
    except Exception as e:
        return {"url": url, "status": "error", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description="M-Lab 数据获取 + HTTP 探测")
    parser.add_argument("--domain", default="tsinghua.edu.cn", help="目标域名")
    parser.add_argument("--days", type=int, default=30, help="查询天数")
    parser.add_argument("--output", default="./data/mlab", help="输出目录")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== M-Lab 数据查询: {args.domain} (过去 {args.days} 天) ===")

    # 1. NDT 速度数据（需要 bq CLI，可能需要认证）
    result = query_mlab_speedtest(args.domain, args.days)
    print(f"NDT 查询: {result['status']}")
    if result['status'] == 'ok':
        out_file = output_dir / f"{args.domain}_ndt.json"
        with open(out_file, "w") as f:
            json.dump(result['data'], f, indent=2)
        print(f"  保存到: {out_file}")
    else:
        print(f"  注意: {result.get('message', '未知错误')}")
        print("  (M-Lab BigQuery 可能需要 GCP 认证，跳过)")

    # 2. HTTP 基本探测（不需认证）
    print("\n=== HTTP 探测（无需认证）===")
    urls_to_test = [
        f"https://www.{args.domain}",
        f"https://{args.domain}",
        f"http://www.{args.domain}",
        f"http://{args.domain}",
    ]

    http_results = []
    for url in urls_to_test:
        r = fetch_via_http(url)
        http_results.append(r)
        print(f"  {r.get('url', url)}: {r.get('status', '?')} | TTFB: {r.get('ttfb_ms', '?')}ms")

    out_file = output_dir / f"{args.domain}_http_probe.json"
    with open(out_file, "w") as f:
        json.dump(http_results, f, indent=2)
    print(f"\nHTTP 探测结果保存到: {out_file}")


if __name__ == "__main__":
    main()