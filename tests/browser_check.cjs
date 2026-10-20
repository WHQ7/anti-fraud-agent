// Optional real-browser layout check. Requires Playwright + Edge. No model calls.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');

(async () => {
  const artifacts = process.env.FRAUD_ARTIFACTS_DIR || path.join(os.tmpdir(), 'anti-fraud-refined-console-preview');
  fs.mkdirSync(artifacts, { recursive: true });
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  async function navigate(name) {
    await page.getByRole('link', { name: new RegExp(name) }).click();
  }
  try {
    // A fresh browser context does not touch the user's open session or records.
    await page.goto('http://127.0.0.1:8503', { waitUntil: 'domcontentloaded' });
    await page.getByRole('heading', { name: /安全总览/, level: 1 }).waitFor({ timeout: 25000 });
    await page.getByRole('button', { name: /新建检测/ }).waitFor();
    await page.getByRole('heading', { name: '信息来源分布', exact: true }).waitFor();
    assert.equal(await page.getByAltText(/消息核验示意插画/).count(), 0);
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(artifacts, 'home-empty.png'), fullPage: true });
    const metricBoxes = await page.getByTestId('stMetric').evaluateAll(nodes => nodes.map(node => ({x: node.getBoundingClientRect().x, y: node.getBoundingClientRect().y})));
    assert.equal(metricBoxes.length, 6);
    assert(metricBoxes.every(box => Math.abs(box.y - metricBoxes[0].y) < 3), 'The original six summary cards must remain on one desktop row');
    await page.getByText('分析设置与隐私', { exact: true }).click();
    await page.getByText('默认分析方式', { exact: true }).waitFor();
    await page.getByText('分析设置与隐私', { exact: true }).click();
    await page.getByRole('button', { name: /加载演示记录/ }).click();
    await page.getByText(/演示数据/).waitFor();
    assert.equal(await page.getByText(/当前为虚构演示数据/).count(), 0);
    await page.getByRole('heading', { name: '最新检测记录', exact: true }).waitFor();
    await page.waitForTimeout(500); // Let the native canvas grid finish painting.
    await page.screenshot({ path: path.join(artifacts, 'overview-desktop.png'), fullPage: true });
    await navigate('检测策略调整');
    await page.getByRole('heading', { name: /检测策略调整/, level: 1 }).waitFor();
    await page.getByRole('button', { name: /保存并应用到本次会话/ }).click();
    await page.getByText(/策略已应用到本次会话/).waitFor();
    await page.screenshot({ path: path.join(artifacts, 'policy-desktop.png'), fullPage: true });
    await navigate('检测记录查询');
    await page.getByRole('heading', { name: /检测记录查询/, level: 1 }).waitFor();
    await page.screenshot({ path: path.join(artifacts, 'records-desktop.png'), fullPage: true });
    await navigate('智能检测');
    await page.getByRole('heading', { name: /智能检测/, level: 1 }).waitFor();
    await page.getByRole('textbox', { name: '待分析内容', exact: true }).fill('请先缴纳入职保证金，10分钟内完成。');
    await page.getByRole('button', { name: /开始分析/ }).click();
    await page.getByText('高风险', { exact: true }).first().waitFor();
    await page.getByRole('button', { name: /下载文本报告/ }).waitFor();
    await page.screenshot({ path: path.join(artifacts, 'detection-desktop.png'), fullPage: true });
    await navigate('安全统计报表');
    await page.getByRole('heading', { name: /安全统计报表/, level: 1 }).waitFor();
    await page.getByRole('button', { name: /导出本次统计明细 CSV/ }).waitFor();
    await navigate('Agent 执行日志');
    await page.getByRole('heading', { name: /Agent 执行日志/, level: 1 }).waitFor();
    await page.getByText(/check_text_rules/).first().waitFor();
    await page.screenshot({ path: path.join(artifacts, 'logs-desktop.png'), fullPage: true });
    await navigate('智能检测');
    await page.getByRole('heading', { name: /智能检测/, level: 1 }).waitFor();
    const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const mobilePage = await mobileContext.newPage();
    await mobilePage.goto('http://127.0.0.1:8503', { waitUntil: 'domcontentloaded' });
    await mobilePage.getByRole('heading', { name: /安全总览/, level: 1 }).waitFor();
    await mobilePage.getByRole('button', { name: /新建检测/ }).waitFor();
    await mobilePage.waitForTimeout(500);
    await mobilePage.screenshot({ path: path.join(artifacts, 'overview-mobile.png'), fullPage: true });
    assert.equal(await mobilePage.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    const headingBox = await mobilePage.getByRole('heading', { name: /安全总览/, level: 1 }).boundingBox();
    assert(headingBox && headingBox.x >= 0 && headingBox.x < 390, 'Mobile content must be visible, not covered by an expanded sidebar');
    await mobilePage.getByRole('button', { name: /新建检测/ }).click();
    await mobilePage.getByRole('heading', { name: /智能检测/, level: 1 }).waitFor();
    await mobilePage.getByRole('textbox', { name: '待分析内容', exact: true }).fill('请先缴纳入职保证金。');
    await mobilePage.getByRole('button', { name: /开始分析/ }).click();
    await mobilePage.getByRole('button', { name: /下载文本报告/ }).waitFor();
    assert.equal(await mobilePage.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1), false);
    await mobilePage.screenshot({ path: path.join(artifacts, 'detection-mobile.png'), fullPage: true });
    await mobileContext.close();
    assert.deepEqual(errors, []);
    console.log('PASS: original sidebar console, six-card desktop row, privacy settings, demo separation, policies, records, analysis, statistics, logs and mobile without overflow.');
    console.log('Screenshots: ' + artifacts);
  } catch (error) {
    await page.screenshot({ path: path.join(artifacts, 'check-failure.png'), fullPage: true });
    throw error;
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
