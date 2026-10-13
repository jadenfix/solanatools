import assert from 'node:assert/strict';
import { constants as fsConstants } from 'node:fs';
import { access, mkdir, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { chromium } from 'playwright-core';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const APP_ROOT = path.resolve(HERE, '..');
const OUTPUT = path.resolve(process.argv[2] || path.join(APP_ROOT, 'docs', 'demo'));

const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

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
    '/dev/shm/web-chrome136/chrome-headless-shell-linux64/chrome-headless-shell',
  ];
  for (const candidate of candidates) if (await executable(candidate)) return candidate;
  throw new Error('No Chromium executable found; set PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH.');
}

async function startServer(dbPath) {
  const child = spawn(
    process.env.PYTHON || 'python3',
    [path.join(APP_ROOT, 'replay_web.py'), '--port', '0', '--db', dbPath],
    { cwd: APP_ROOT, stdio: ['ignore', 'pipe', 'pipe'] },
  );
  let stdout = '';
  let stderr = '';
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stderr.on('data', chunk => { stderr += chunk; });
  const url = await Promise.race([
    new Promise((resolve, reject) => {
      child.stdout.on('data', chunk => {
        stdout += chunk;
        const match = stdout.match(/Replay workbench:\s+(http:\/\/127\.0\.0\.1:\d+)/);
        if (match) resolve(match[1]);
      });
      child.once('error', reject);
      child.once('exit', code => reject(new Error(`Server exited ${code}: ${stderr}`)));
    }),
    wait(15_000).then(() => { throw new Error(`Server startup timed out: ${stderr}`); }),
  ]);
  return { child, url };
}

async function stopServer(server) {
  if (!server || server.child.exitCode !== null) return;
  server.child.kill('SIGTERM');
  await Promise.race([
    new Promise(resolve => server.child.once('exit', resolve)),
    wait(3_000).then(() => server.child.kill('SIGKILL')),
  ]);
}

async function smoothScroll(page, top) {
  await page.evaluate(target => window.scrollTo({ top: target, behavior: 'smooth' }), top);
  await wait(1_300);
}

async function submit(page) {
  const response = page.waitForResponse(item =>
    item.url().endsWith('/api/runs') && item.request().method() === 'POST');
  await page.locator('#run-button').click();
  assert.equal((await response).status(), 201);
  await page.waitForFunction(() => !document.querySelector('#run-button').disabled);
}

async function capture() {
  await mkdir(OUTPUT, { recursive: true });
  const temporary = await mkdtemp(path.join(tmpdir(), 'solana-replay-capture-'));
  let server;
  let browser;
  try {
    server = await startServer(path.join(temporary, 'capture.sqlite3'));
    browser = await chromium.launch({
      executablePath: await findBrowser(),
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const context = await browser.newContext({
      viewport: { width: 960, height: 540 },
      recordVideo: { dir: temporary, size: { width: 960, height: 540 } },
      acceptDownloads: true,
    });
    const page = await context.newPage();
    const errors = [];
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
    page.on('pageerror', error => errors.push(error.message));

    await page.goto(server.url, { waitUntil: 'networkidle' });
    await wait(1_600);
    await page.locator('input[name="name"]').fill('Verified synthetic replay');
    await submit(page);
    await page.locator('#result-content').waitFor({ state: 'visible' });
    await wait(2_000);
    await page.screenshot({ path: path.join(OUTPUT, 'poster.png') });

    await smoothScroll(page, 390);
    await wait(1_700);
    await smoothScroll(page, 690);
    await wait(1_700);
    await smoothScroll(page, 0);

    await page.locator('input[name="name"]').fill('Fee sensitivity · synthetic');
    await page.locator('input[name="period"]').fill('5');
    await page.locator('input[name="fees"]').fill('25');
    await submit(page);
    await wait(1_800);
    await smoothScroll(page, 390);
    await wait(1_300);

    await smoothScroll(page, 0);
    await page.locator('#source').selectOption('csv');
    await page.locator('#csv-file').setInputFiles({
      name: 'fixture-prices.csv',
      mimeType: 'text/csv',
      buffer: Buffer.from('timestamp,price\nu0,100\nu1,90\nu2,80\nu3,70\nu4,100\nu5,120\nu6,95\nu7,75\nu8,110\n'),
    });
    await page.locator('input[name="name"]').fill('Uploaded fixture bars');
    await page.locator('input[name="period"]').fill('1');
    await submit(page);
    await wait(1_800);
    await smoothScroll(page, 690);
    await wait(1_500);
    await smoothScroll(page, 980);
    await wait(1_400);

    assert.deepEqual(errors, []);
    const video = page.video();
    await context.close();
    await video.saveAs(path.join(OUTPUT, 'capture.webm'));
    console.log('CAPTURE_OK synthetic=75-bars parameter-change=true csv=9-bars errors=0');
  } finally {
    await browser?.close().catch(() => {});
    await stopServer(server);
    await rm(temporary, { recursive: true, force: true });
  }
}

capture().catch(error => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
