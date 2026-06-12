#!/usr/bin/env bash
# fetch_cloudflare_radar.sh
# 通过 Cloudflare Radar API 获取目标站点的全球性能数据
# 免费，无需申请（只要能访问 Cloudflare）

set -euo pipefail

# ===== 配置 =====
API_TOKEN="${CF_API_TOKEN:-}"  # 从环境变量读取，或去 https://dash.cloudflare.com/profile/api-tokens 创建
TARGETS=(
  "tsinghua.edu.cn"
  "sigs.tsinghua.edu.cn"
  "pku.edu.cn"
  "zju.edu.cn"
  "fudan.edu.cn"
)

OUTPUT_DIR="./data/cloudflare_radar"
mkdir -p "$OUTPUT_DIR"

# ===== 主循环 =====
for domain in "${TARGETS[@]}"; do
  echo "=== Fetching: $domain ==="

  # Speedtest 历史数据
  curl -s -G "https://api.cloudflare.com/client/v4/radar/speedtest/history" \
    --data-urlencode "domain=$domain" \
    --data-urlencode "dateRange=30d" \
    --data-urlencode "format=json" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Accept: application/json" \
    | jq . > "$OUTPUT_DIR/${domain}_speedtest.json"

  # AS 关联数据（运营商/网络信息）
  curl -s -G "https://api.cloudflare.com/client/v4/radar/rr/history" \
    --data-urlencode "domain=$domain" \
    --data-urlencode "dateRange=30d" \
    --data-urlencode "format=json" \
    -H "Authorization: Bearer $API_TOKEN" \
    -H "Accept: application/json" \
    | jq . > "$OUTPUT_DIR/${domain}_rr.json"

  echo "  Done: $domain"
done

echo ""
echo "=== 数据保存在: $OUTPUT_DIR ==="
echo "文件列表:"
ls -lh "$OUTPUT_DIR"