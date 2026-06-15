// Headless smoke test for the Archive feature UI.
// Usage: node scripts/archive_smoke.mjs <route> <toggleText>
//   e.g. node scripts/archive_smoke.mjs /my-eu-bubble?tab=my_files Archived
// Requires: dev server on :5173, local backend on :8000, /tmp/archive_auth.json.
import puppeteer from 'puppeteer';
import fs from 'fs';

const ROUTE = process.argv[2] || '/my-eu-bubble?tab=my_files';
const BASE = 'http://localhost:5173';
const auth = fs.readFileSync('/tmp/archive_auth.json', 'utf8').trim();
const WIDTHS = [375, 393, 768, 1024, 1440, 2560];

const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(String(e)));
page.on('console', (m) => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

// Seed auth before the app boots.
await page.goto(BASE, { waitUntil: 'domcontentloaded' });
await page.evaluate((a) => localStorage.setItem('brubru-auth', a), auth);

await page.goto(BASE + ROUTE, { waitUntil: 'domcontentloaded', timeout: 45000 });
await new Promise((r) => setTimeout(r, 5000)); // let lists fetch (tabs keep network busy)

// 1. Archive toggle present?
const hasToggle = await page.evaluate(() =>
  !!document.querySelector('.archive-toggle'));
// 2. Archive buttons present on cards?
const archiveBtns = await page.evaluate(() =>
  document.querySelectorAll('.archive-btn').length);

// 3. Click the "Archived" side of the toggle, ensure no crash + list reloads.
let toggled = false;
if (hasToggle) {
  toggled = await page.evaluate(() => {
    const btns = document.querySelectorAll('.archive-toggle button');
    const archivedBtn = btns[btns.length - 1];
    if (archivedBtn) { archivedBtn.click(); return true; }
    return false;
  });
  await new Promise((r) => setTimeout(r, 2500));
}

// 4. Horizontal-overflow check across breakpoints.
const overflow = {};
for (const w of WIDTHS) {
  await page.setViewport({ width: w, height: 900 });
  await new Promise((r) => setTimeout(r, 250));
  overflow[w] = await page.evaluate(() =>
    document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
}

console.log(JSON.stringify({
  route: ROUTE, hasToggle, archiveBtns, toggled,
  horizontalOverflow: overflow,
  errors: errors.slice(0, 5),
}, null, 2));

await browser.close();
const anyOverflow = Object.values(overflow).some(Boolean);
process.exit(!hasToggle || anyOverflow || errors.length ? 1 : 0);
