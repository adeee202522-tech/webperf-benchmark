const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

// ===== 从环境变量读取目标 =====
const TARGET_URL = process.env.TARGET_URL;
const TARGET_NAME = process.env.TARGET_NAME || 'unknown';
const OUTPUT_DIR = path.join(process.cwd(), 'data');

// ===== 核心测量逻辑 =====
async function measureSite(browser, url) {
  const page = await browser.newPage();
  const pageErrors = [];

  page.on('pageerror', e => pageErrors.push(e.message));
  page.on('requestfailed', r => {
    if (!r.url().startsWith('data:')) {
      pageErrors.push(`Failed: ${r.url()} - ${r.failure()?.errorText}`);
    }
  });

  try {
    await page.addInitScript(() => {
      window.__wpt = { lcp: 0, cls: 0 };

      new PerformanceObserver(list => {
        const entries = list.getEntries();
        const last = entries[entries.length - 1];
        if (last.startTime > window.__wpt.lcp) {
          window.__wpt.lcp = last.startTime;
        }
      }).observe({ type: 'largest-contentful-paint', buffered: true });

      new PerformanceObserver(list => {
        for (const e of list.getEntries()) {
          if (!e.hadRecentInput) {
            window.__wpt.cls += e.value;
          }
        }
      }).observe({ type: 'layout-shift', buffered: true });
    });

    const startTime = Date.now();
    await page.goto(url, { waitUntil: 'load', timeout: 30000 });
    const navigationTime = Date.now() - startTime;

    await page.waitForTimeout(2000);

    const metrics = await page.evaluate(() => {
      const nav = performance.getEntriesByType('navigation')[0];
      const paints = performance.getEntriesByType('paint');
      const resources = performance.getEntriesByType('resource');
      const wpt = window.__wpt || {};

      const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
      const lcpVal = lcpEntries.length > 0
        ? Math.round(lcpEntries[lcpEntries.length - 1].startTime)
        : Math.round(wpt.lcp || 0);

      let totalCLS = wpt.cls || 0;
      const allLayoutShifts = performance.getEntriesByType('layout-shift');
      allLayoutShifts.forEach(ls => { if (!ls.hadRecentInput) totalCLS += ls.value; });
      totalCLS = Math.round(totalCLS * 10000) / 10000;

      return {
        ttfb: nav ? Math.round(nav.responseStart - nav.requestStart) : 0,
        fcp: Math.round(paints.find(p => p.name === 'first-contentful-paint')?.startTime || 0),
        lcp: lcpVal,
        cls: totalCLS,
        load: nav ? Math.round(nav.loadEventEnd - nav.requestStart) : navigationTime,
        domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd - nav.requestStart) : 0,
        domInteractive: nav ? Math.round(nav.domInteractive - nav.requestStart) : 0,
        transferSize: nav ? nav.transferSize : 0,
        resourceCount: resources.length,
        title: document.title,
        url: window.location.href,
      };
    });

    return {
      url,
      name: TARGET_NAME,
      ...metrics,
      pageErrors: pageErrors.filter(e => !e.includes('data:')),
      navigationTime,
      status: 'ok'
    };

  } catch (e) {
    return { url, name: TARGET_NAME, status: 'error', error: e.message };
  } finally {
    await page.close();
  }
}

// ===== 检测出口 IP 和地理位置 =====
async function detectExitInfo() {
  try {
    // 查询公网出口 IP
    const ipRes = await fetch('https://ifconfig.me/ip', { timeout: 5000 });
    const ip = await ipRes.text().then(t => t.trim());

    // 查询 IP 地理位置
    const geoRes = await fetch(`http://ip-api.com/json/${ip}?fields=status,country,countryCode,city,regionName,isp,query`, { timeout: 5000 });
    const geo = await geoRes.json();

    if (geo.status === 'success') {
      return {
        exit_ip: ip,
        region: `${geo.country} / ${geo.city} (${geo.isp})`,
        country_code: geo.countryCode,
        city: geo.city,
        isp: geo.isp
      };
    }
    return { exit_ip: ip, region: `IP: ${ip}`, country_code: '', city: '', isp: '' };
  } catch (e) {
    return { exit_ip: 'unknown', region: 'unknown', country_code: '', city: '', isp: '' };
  }
}

// ===== 主程序 =====
async function main() {
  if (!TARGET_URL) {
    console.error('ERROR: TARGET_URL not set');
    process.exit(1);
  }

  // 检测出口 IP 和地理位置
  const exitInfo = await detectExitInfo();
  console.error(`Exit IP: ${exitInfo.exit_ip}, Region: ${exitInfo.region}`);

  // 确保输出目录存在
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }

  const RUNS = parseInt(process.env.NUM_RUNS || '3');  // 每次运行跑3次，捕获不同出口IP
  console.error(`Starting browser for ${TARGET_NAME} (${RUNS} runs)...`);
  const browser = await chromium.launch({
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-web-security']
  });

  const allResults = [];
  for (let i = 0; i < RUNS; i++) {
    console.error(`Run ${i+1}/${RUNS}: Running measurement...`);
    const result = await measureSite(browser, TARGET_URL);
    // 每次运行后重新检测出口IP（可能换节点）
    const exitInfo = await detectExitInfo();
    result.exit_ip = exitInfo.exit_ip;
    result.region_detail = exitInfo.region;
    allResults.push(result);
    console.error(`  Run ${i+1}: IP=${exitInfo.exit_ip}, LCP=${result.lcp}ms`);
  }
  await browser.close();

  // 取最后一次结果作为主结果
  const result = allResults[allResults.length - 1];

  // 输出 JSON 行供 GitHub Actions 捕获
  console.log(JSON.stringify(result));

  // 保存数据
  const timestamp = Date.now();
  const outPath = path.join(OUTPUT_DIR, `run_${timestamp}.json`);
  // 保存所有轮次的结果
  const combined = {
    timestamp: new Date().toISOString(),
    target: TARGET_NAME,
    url: TARGET_URL,
    num_runs: RUNS,
    runs: allResults  // 每个元素含 exit_ip, region_detail
  };
  fs.writeFileSync(outPath, JSON.stringify(combined, null, 2));
  console.error(`All ${RUNS} runs saved`);

  console.error(`Data saved: ${outPath}`);
}

main().catch(e => { console.error('Fatal:', e.message); process.exit(1); });