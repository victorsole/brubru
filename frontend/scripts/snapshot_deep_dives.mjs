/**
 * Deep-dive language snapshotter.
 *
 * The deep-dive STANDARD is single-file i18n: one index.html with data-i18n keys
 * and a `const translations` object (es/ca/fr/it/nl). That gives one source of
 * truth (cannot drift) but the translated text lives in JS, invisible to crawlers
 * and AI bots that do not run JS.
 *
 * This script closes that gap: for every single-file-i18n deep-dive in dist/, it
 * loads the page, calls setLang(<lang>) for each language, and writes a static
 * dist/{slug}/{lang}.html with the translated DOM baked in + <html lang> + an
 * hreflang block. These are BUILD ARTIFACTS (regenerated every build from the one
 * source) so they can never drift — the IAA/EU-Inc class of bug is impossible.
 *
 * Separate-file deep-dives (legacy) already have static {lang}.html and are skipped.
 *
 * Usage:  node scripts/snapshot_deep_dives.mjs           (operates on dist/)
 * Called by: npm run build:prerender (after prerender)
 */
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import puppeteer from 'puppeteer';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(__dirname, '..', 'dist');
const SITE = 'https://brubru.beresol.eu';
const LANGS = ['es', 'ca', 'fr', 'it', 'nl'];

function singleI18nDeepDives() {
  const out = [];
  for (const d of readdirSync(DIST)) {
    const idx = resolve(DIST, d, 'index.html');
    try { if (!statSync(resolve(DIST, d)).isDirectory() || !existsSync(idx)) continue; } catch { continue; }
    const html = readFileSync(idx, 'utf8');
    if (/const\s+translations\s*=/.test(html) && /data-i18n=/.test(html)) out.push(d);
  }
  return out;
}

function hreflangBlock(slug) {
  const alt = (lang, file) => `<link rel="alternate" hreflang="${lang}" href="${SITE}/${slug}/${file}">`;
  return [
    alt('en', ''),
    ...LANGS.map((l) => alt(l, `${l}.html`)),
    `<link rel="alternate" hreflang="x-default" href="${SITE}/${slug}/">`,
  ].join('\n  ');
}

const slugs = singleI18nDeepDives();
if (!slugs.length) { console.log('[snapshot] no single-file-i18n deep-dives in dist/ — nothing to do'); process.exit(0); }

const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'], protocolTimeout: 120000 });
const page = await browser.newPage();
let written = 0;
console.log(`[snapshot] ${slugs.length} single-file-i18n deep-dive(s): ${slugs.join(', ')}`);
for (const slug of slugs) {
  const url = pathToFileURL(resolve(DIST, slug, 'index.html')).href;
  for (const lang of LANGS) {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    const ok = await page.evaluate((l) => {
      if (typeof setLang !== 'function') return false;
      setLang(l);
      document.documentElement.setAttribute('lang', l);
      return true;
    }, lang);
    if (!ok) { console.log(`   [skip] ${slug}: no setLang()`); break; }
    let html = await page.evaluate(() => '<!DOCTYPE html>\n' + document.documentElement.outerHTML);
    // inject hreflang + self-canonical just before </head>
    const head = `  <link rel="canonical" href="${SITE}/${slug}/${lang}.html">\n  ${hreflangBlock(slug)}\n</head>`;
    html = html.replace('</head>', head);
    writeFileSync(resolve(DIST, slug, `${lang}.html`), html, 'utf8');
    written++;
  }
}
await browser.close();
console.log(`[snapshot] wrote ${written} language snapshot(s)\n`);
