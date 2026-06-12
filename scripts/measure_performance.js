const { chromium } = require('/usr/local/lib/hermes-agent/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

// ===== 配置 =====
const TARGETS = [
  'https://www.tsinghua.edu.cn',
  'https://www.sigs.tsinghua.edu.cn',
  'https://www.pku.edu.cn',
  'https://www.zju.edu.cn',
  'https://www.fudan.edu.cn',
  // 可继续添加更多目标
];

const CHROME_PATH = '/root/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome';
const OUTPUT_DIR = '/private/hermes/webperf-benchmark/data';

// ===== 核心测量逻辑 =====
function measureSite(browser, url) {
  return new Promise(async (resolve, reject) => {
    const page = await browser.newPage();
    const pageErrors = [];

    page.on('pageerror', e => pageErrors.push(e.message));
    page.on('requestfailed', r => {
      if (!r.url().startsWith('data:')) {
        pageErrors.push(`Failed: ${r.url()} - ${r.failure()?.errorText}`);
      }
    });

    try {
      // 在页面初始化时埋入 PerformanceObserver
      await page.addInitScript(() => {
        window.__wpt = { lcp: 0, cls: 0, lcpEntries: [], clsEntries: [] };

        // LCP Observer
        new PerformanceObserver(list => {
          const entries = list.getEntries();
          const last = entries[entries.length - 1];
          if (last.startTime > window.__wpt.lcp) {
            window.__wpt.lcp = last.startTime;
          }
          window.__wpt.lcpEntries = entries.map(e => ({
            startTime: e.startTime,
            size: e.size,
            element: e.element?.tagName || 'N/A'
          }));
        }).observe({ type: 'largest-contentful-paint', buffered: true });

        // CLS Observer
        new PerformanceObserver(list => {
          for (const e of list.getEntries()) {
            if (!e.hadRecentInput) {
              window.__wpt.cls += e.value;
              window.__wpt.clsEntries.push(e);
            }
          }
        }).observe({ type: 'layout-shift', buffered: true });

        // TTFB Override - 监听每个响应
        window.__wpt.responses = [];
        const origFetch = window.fetch;
        // 使用 PerformanceObserve 监听 resource timing
        new PerformanceObserver(list => {
          for (const e of list.getEntries()) {
            if (e.entryType === 'resource' && e.initiatorType === 'navigation') {
              window.__wpt.navTiming = e;
            }
          }
        }).observe({ entryTypes: ['resource'] });
      });

      const startTime = Date.now();
      await page.goto(url, { waitUntil: 'load', timeout: 30000 });
      const navigationTime = Date.now() - startTime;

      // 等待 LCP 稳定（额外等 2 秒）
      await page.waitForTimeout(2000);

      const metrics = await page.evaluate(() => {
        const nav = performance.getEntriesByType('navigation')[0];
        const paints = performance.getEntriesByType('paint');
        const resources = performance.getEntriesByType('resource');
        const wpt = window.__wpt || {};

        // LCP: 尝试从 performance entries 获取
        const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
        const lcpVal = lcpEntries.length > 0
          ? Math.round(lcpEntries[lcpEntries.length - 1].startTime)
          : Math.round(wpt.lcp || 0);

        // CLS: 重新计算（有些条目可能已被 observer 消费）
        let totalCLS = wpt.cls || 0;
        const allLayoutShifts = performance.getEntriesByType('layout-shift');
        allLayoutShifts.forEach(ls => { if (!ls.hadRecentInput) totalCLS += ls.value; });
        totalCLS = Math.round(totalCLS * 10000) / 10000;

        // 资源统计
        const jsResources = resources.filter(r => r.initiatorType === 'script');
        const cssResources = resources.filter(r => r.initiatorType === 'css');
        const imgResources = resources.filter(r => r.initiatorType === 'img');

        return {
          // 核心 Web Vitals
          ttfb: nav ? Math.round(nav.responseStart - nav.requestStart) : 0,
          fcp: Math.round(paints.find(p => p.name === 'first-contentful-paint')?.startTime || 0),
          lcp: lcpVal,
          cls: totalCLS,
          // 加载时序
          load: nav ? Math.round(nav.loadEventEnd - nav.requestStart) : navigationTime,
          domContentLoaded: nav ? Math.round(nav.domContentLoadedEventEnd - nav.requestStart) : 0,
          domInteractive: nav ? Math.round(nav.domInteractive - nav.requestStart) : 0,
          // 网络数据
          transferSize: nav ? nav.transferSize : 0,
          resourceCount: resources.length,
          jsCount: jsResources.length,
          cssCount: cssResources.length,
          imgCount: imgResources.length,
          // 页面信息
          title: document.title,
          url: window.location.href,
        };
      });

      resolve({
        url,
        ...metrics,
        pageErrors: pageErrors.filter(e => !e.includes('data:')),
        navigationTime,
        status: 'ok'
      });

    } catch (e) {
      resolve({ url, status: 'error', error: e.message });
    }

    await page.close();
  });
}

// ===== 主程序 =====
async function main() {
  console.error('Starting browser...');
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--headless', '--disable-web-security']
  });

  console.error('Browser ready. Running measurements...');

  const results = [];
  for (const url of TARGETS) {
    process.stderr.write(`  Testing: ${url}\n`);
    const r = await measureSite(browser, url);
    results.push(r);
    console.log(JSON.stringify(r));
  }

  await browser.close();

  // 保存数据
  const timestamp = Date.now();
  const outPath = path.join(OUTPUT_DIR, `run_${timestamp}.json`);
  fs.writeFileSync(outPath, JSON.stringify({
    timestamp: new Date().toISOString(),
    region: 'HK',
    isp: 'PCCW Global',
    exit_ip: '209.9.115.16',
    results
  }, null, 2));

  process.stderr.write(`\n数据已保存: ${outPath}\n`);
}

main().catch(e => { console.error('Fatal:', e.message); process.exit(1); });