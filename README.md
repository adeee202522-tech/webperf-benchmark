# Web Performance Benchmark

中国学术机构网站海外性能基准测试

## 立即可用：3步开始

### Step 1: Cloudflare Radar API（今天就能调，无需申请）

```bash
# 1. 去 https://dash.cloudflare.com/profile/api-tokens 创建 Token
#    选择 "Create Custom Token"，只给 Radar API 读权限

# 2. 设置环境变量
export CF_API_TOKEN="your_token_here"

# 3. 运行脚本
cd scripts
chmod +x fetch_cloudflare_radar.sh
./fetch_cloudflare_radar.sh

# 输出: ./data/cloudflare_radar/*.json
```

### Step 2: GitHub Actions Lighthouse（今天就能启用，~10个地区）

```bash
# 1. 在 GitHub 创建空 repo
gh repo create webperf-benchmark --public

# 2. 复制 workflow 文件
cp -r .github /path/to/webperf-benchmark/
git init && git add .
git commit -m "init"
gh repo set-default
git push -u origin main
```

在 GitHub 网页上：**Actions → Lighthouse workflow → Run workflow**

GitHub Actions runner 地区（~10个）：
- us-west-1, us-west-2, us-east-1, us-east-2 (美国)
- europe-west, europe-north, europe-central (欧洲)
- southeast-asia, east-asia (亚太)
- southamerica-east-1 (南美)

### Step 3: 本地 HTTP 探测（当前服务器 → 目标站点的 TTFB）

```bash
python3 scripts/fetch_mlab_data.py --domain tsinghua.edu.cn
python3 scripts/fetch_mlab_data.py --domain sigs.tsinghua.edu.cn
```

## 目录结构

```
webperf-benchmark/
├── .github/
│   └── workflows/
│       └── lighthouse.yml      # GitHub Actions 多地区 Lighthouse
├── scripts/
│   ├── fetch_cloudflare_radar.sh  # Cloudflare Radar API
│   ├── fetch_mlab_data.py         # M-Lab + HTTP 探测
│   └── aggregate_results.py       # 汇总报告
├── data/                          # 测试结果（gitignore）
├── benchmark_results.csv          # 汇总 CSV
└── benchmark_report.md            # 汇总报告
```

## 覆盖地区说明

| 数据来源 | 地区数 | 说明 |
|---------|-------|------|
| GitHub Actions | ~10 | 免费，需 GitHub 账号 |
| Cloudflare Radar | ~300 | API 免费，但数据是聚合的，不是 raw |
| HTTP 探测 | 1 (当前) | 当前服务器出口 IP (209.9.115.16) |

**当前总覆盖：~300 个城市级别的聚合数据 + ~10 个精确测点 + 1 个当前服务器**

## 下一步（等 RIPE Atlas 审批后）

RIPE Atlas 审批通过后，可以：
1. 替换 GitHub Actions 为 RIPE Atlas probes（50+ 精确测点）
2. 数据更权威，更适合学术发表

## 学术发表注意事项

所有数据来源在论文中需注明：
- GitHub Actions runner 地区来源：GitHub, Inc.
- Cloudflare Radar 数据：Cloudflare, Inc.
- RIPE Atlas 数据：RIPE NCC（如果使用）

建议对比多个数据源，交叉验证结果，增强学术可信度。