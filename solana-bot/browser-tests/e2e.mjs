import assert from 'node:assert/strict';
import { constants as fsConstants } from 'node:fs';
import { access, mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright-core';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(HERE, '..');
const STARTUP_TIMEOUT_MS = 15_000;

function wait(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function executable(candidate) {
  if (!candidate) return false;
  try {
    await access(candidate, fsConstants.X_OK);
    return true;
  } catch {
    return false;
  }
}

async function findBrowser() {
  const candidates = [
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    process.env.CHROME_BIN,
    process.env.CHROMIUM_BIN,
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/opt/google/chrome/chrome',
    '/opt/google/chrome/google-chrome',
    '/tmp/chromium',
    '/dev/shm/web-chrome136/chrome-headless-shell-linux64/chrome-headless-shell',
  ];
  for (const candidate of candidates) {
    if (await executable(candidate)) return candidate;
  }
  throw new Error(
    'No system Chromium executable found. Set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH.',
  );
}

function collect(stream, onChunk = () => {}) {
  let output = '';
  stream.setEncoding('utf8');
  stream.on('data', chunk => {
    output += chunk;
    onChunk(chunk);
  });
  return () => output;
}

async function startServer(dbPath) {
  const python = process.env.PYTHON || process.env.PYTHON_BIN || 'python3';
  const child = spawn(
    python,
    [path.join(APP_ROOT, 'replay_web.py'), '--port', '0', '--db', dbPath],
    { cwd: APP_ROOT, env: process.env, stdio: ['ignore', 'pipe', 'pipe'] },
  );

  let resolveUrl;
  let rejectUrl;
  const urlPromise = new Promise((resolve, reject) => {
    resolveUrl = resolve;
    rejectUrl = reject;
  });
  const stdout = collect(child.stdout, chunk => {
    const match = chunk.match(/Replay workbench:\s+(http:\/\/127\.0\.0\.1:\d+)/);
    if (match) resolveUrl(match[1]);
  });
  const stderr = collect(child.stderr);
  child.once('error', rejectUrl);
  child.once('exit', (code, signal) => {
    rejectUrl(
      new Error(
        `replay_web.py exited before startup (code=${code}, signal=${signal})\n${stderr()}`,
      ),
    );
  });

  const timeout = wait(STARTUP_TIMEOUT_MS).then(() => {
    throw new Error(`Timed out starting replay_web.py\n${stdout()}\n${stderr()}`);
  });
  const url = await Promise.race([urlPromise, timeout]);
  const response = await fetch(`${url}/api/health`);
  assert.equal(response.status, 200, 'health endpoint should be ready');
  assert.deepEqual(await response.json(), { ok: true, mode: 'offline-paper' });
  return { child, url, stdout, stderr };
}

async function stopServer(server) {
  if (!server?.child || server.child.exitCode !== null) return;
  server.child.kill('SIGTERM');
  await Promise.race([
    new Promise(resolve => server.child.once('exit', resolve)),
    wait(3_000).then(() => {
      if (server.child.exitCode === null) server.child.kill('SIGKILL');
    }),
  ]);
}

function observePage(page, errors) {
  page.on('console', message => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`);
  });
  page.on('pageerror', error => errors.push(`pageerror: ${error.message}`));
}

async function expectCanvasPainted(page, selector) {
  const state = await page.locator(selector).evaluate(canvas => {
    const context = canvas.getContext('2d');
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let painted = 0;
    for (let index = 3; index < pixels.length; index += 4) {
      if (pixels[index] !== 0) painted += 1;
    }
    return {
      width: canvas.width,
      height: canvas.height,
      cssWidth: canvas.clientWidth,
      cssHeight: canvas.clientHeight,
      painted,
    };
  });
  assert.ok(state.width > 0 && state.height > 0, `${selector} must have a bitmap`);
  assert.ok(state.cssWidth > 0 && state.cssHeight > 0, `${selector} must be visible`);
  assert.ok(state.painted > 100, `${selector} should contain rendered chart pixels`);
}

async function submitReplay(page) {
  const responsePromise = page.waitForResponse(
    response =>
      response.url().endsWith('/api/runs') &&
      response.request().method() === 'POST',
  );
  await page.locator('#run-button').click();
  const response = await responsePromise;
  assert.equal(response.status(), 201, 'replay POST should succeed');
  const result = await response.json();
  await assert.doesNotReject(() =>
    page.locator('#status').waitFor({ state: 'visible', timeout: 10_000 }),
  );
  await page.waitForFunction(() => !document.querySelector('#run-button').disabled);
  return result;
}

async function run() {
  const temp = await mkdtemp(path.join(tmpdir(), 'solana-replay-browser-'));
  const dbPath = path.join(temp, 'browser-runs.sqlite3');
  let server;
  let browser;
  const browserErrors = [];

  try {
    server = await startServer(dbPath);
    const executablePath = await findBrowser();
    browser = await chromium.launch({
      executablePath,
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const context = await browser.newContext({
      viewport: { width: 1440, height: 1000 },
      acceptDownloads: true,
    });
    const page = await context.newPage();
    observePage(page, browserErrors);

    // Brand-new temporary database must render the truthful empty state.
    await page.goto(server.url, { waitUntil: 'networkidle' });
    await assert.doesNotReject(() => page.locator('#empty').waitFor({ state: 'visible' }));
    assert.match(await page.locator('#empty').innerText(), /paper replay, never/i);
    assert.equal(await page.locator('#result-content').isHidden(), true);
    assert.equal(await page.locator('#download').isHidden(), true);
    assert.match(await page.locator('#history').innerText(), /No saved runs yet/i);

    // Run the bundled source through the real HTTP server, engine, and SQLite store.
    const demo = await submitReplay(page);
    assert.equal(demo.source, 'bundled_synthetic_fixture');
    assert.equal(demo.mode, 'offline-paper');
    assert.equal(demo.bars, 75);
    assert.ok(demo.fills > 0);
    assert.ok(demo.ledger.length > 0);
    await page.locator('#result-content').waitFor({ state: 'visible' });
    assert.match(await page.locator('#provenance').innerText(), /SYNTHETIC FIXTURE.*OFFLINE PAPER/);
    assert.match(await page.locator('#bars').innerText(), /75 bars/);
    assert.match(await page.locator('#fill-count').innerText(), /paper fills/);
    assert.equal(await page.locator('#ledger tr').count(), demo.ledger.length);
    for (const metric of ['#equity', '#return', '#drawdown', '#fees']) {
      assert.notEqual((await page.locator(metric).innerText()).trim(), '—');
    }
    await expectCanvasPainted(page, '#equity-chart');
    await expectCanvasPainted(page, '#rsi-chart');

    // Change a material strategy parameter and prove the saved result records it.
    await page.locator('input[name="name"]').fill('Five-period synthetic replay');
    await page.locator('input[name="period"]').fill('5');
    await page.locator('input[name="fees"]').fill('25');
    const parameterized = await submitReplay(page);
    assert.equal(parameterized.parameters.period, 5);
    assert.equal(parameterized.parameters.fee_bps, 25);
    assert.equal(parameterized.name, 'Five-period synthetic replay');
    assert.equal(await page.locator('#history button').count(), 2);

    // Upload an actual in-memory CSV using the browser file input.
    const csv = [
      'timestamp,price',
      'u0,100',
      'u1,90',
      'u2,80',
      'u3,70',
      'u4,100',
      'u5,120',
      'u6,95',
      'u7,75',
      'u8,110',
    ].join('\n');
    await page.locator('#source').selectOption('csv');
    await page.locator('#csv-input').waitFor({ state: 'visible' });
    await page.locator('#csv-file').setInputFiles({
      name: 'user-prices.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from(csv),
    });
    await page.locator('input[name="name"]').fill('Uploaded price bars');
    await page.locator('input[name="period"]').fill('1');
    const uploaded = await submitReplay(page);
    assert.equal(uploaded.source, 'user_csv_unverified');
    assert.equal(uploaded.bars, 9);
    assert.equal(uploaded.name, 'Uploaded price bars');
    assert.match(await page.locator('#provenance').innerText(), /USER CSV.*PROVENANCE UNVERIFIED.*OFFLINE PAPER/);
    assert.equal(await page.locator('#ledger tr').count(), uploaded.ledger.length);

    // Export must be a real attachment whose JSON matches the active persisted run.
    const downloadPromise = page.waitForEvent('download');
    await page.locator('#download').click();
    const download = await downloadPromise;
    assert.equal(download.suggestedFilename(), 'paper-replay.json');
    const downloadedPath = path.join(temp, 'paper-replay.json');
    await download.saveAs(downloadedPath);
    const exported = JSON.parse(await readFile(downloadedPath, 'utf8'));
    assert.equal(exported.id, uploaded.id);
    assert.equal(exported.source, 'user_csv_unverified');
    assert.deepEqual(exported.ledger, uploaded.ledger);

    // A full navigation must recover history and automatically reload the newest result.
    await page.reload({ waitUntil: 'networkidle' });
    await page.locator('#result-content').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#run-name').innerText(), 'Uploaded price bars');
    assert.equal(await page.locator('#history button').count(), 3);
    assert.match(await page.locator('#history button').first().innerText(), /Uploaded price bars/);
    assert.equal(await page.locator('#source').inputValue(), 'csv');

    // Older history entries must remain loadable after the navigation.
    await page.locator('#history button').nth(2).click();
    await page.waitForFunction(() => document.querySelector('#run-name').textContent === 'Synthetic RSI replay');
    assert.match(await page.locator('#provenance').innerText(), /SYNTHETIC FIXTURE/);

    // Mobile layout uses one column and keeps the page itself free of horizontal overflow.
    await page.setViewportSize({ width: 390, height: 844 });
    await page.reload({ waitUntil: 'networkidle' });
    const mobile = await page.evaluate(() => {
      const layout = document.querySelector('.layout');
      const body = document.body;
      const root = document.documentElement;
      return {
        columns: getComputedStyle(layout).gridTemplateColumns.split(' ').filter(Boolean).length,
        viewportWidth: root.clientWidth,
        bodyWidth: body.scrollWidth,
        rootWidth: root.scrollWidth,
        tableScrollsInside: document.querySelector('.table-wrap').scrollWidth >=
          document.querySelector('.table-wrap').clientWidth,
      };
    });
    assert.equal(mobile.columns, 1, 'mobile layout should collapse to one column');
    assert.ok(mobile.bodyWidth <= mobile.viewportWidth, 'body must not overflow horizontally');
    assert.ok(mobile.rootWidth <= mobile.viewportWidth, 'document must not overflow horizontally');
    assert.equal(mobile.tableScrollsInside, true, 'ledger should stay inside its scroll container');
    await expectCanvasPainted(page, '#equity-chart');
    await expectCanvasPainted(page, '#rsi-chart');

    assert.deepEqual(browserErrors, [], `browser emitted errors:\n${browserErrors.join('\n')}`);
    await context.close();
    console.log(
      `BROWSER_E2E_OK initial=empty synthetic=${demo.bars}-bars parameters=changed ` +
      `csv=${uploaded.bars}-bars history=3 export=json mobile=no-overflow errors=0`,
    );
  } finally {
    await browser?.close().catch(() => {});
    await stopServer(server);
    if (server?.child && server.child.exitCode && server.child.exitCode !== 0) {
      console.error(server.stderr());
    }
    await rm(temp, { recursive: true, force: true });
  }
}

run().catch(error => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
