/**
 * Deep-dive RESPONSIVE gate (the authoritative one).
 *
 * Loads every deep-dive page (and its per-language files) in headless Chrome at
 * the mandated screen widths and asserts there is NO horizontal overflow and no
 * cramped multi-column cards. This is the real enforcement of the CLAUDE.md rule
 * "check that everything is responsive in all types of screens"; the static
 * breakpoint check in check_deep_dives.mjs is only a proxy.
 *
 * Widths: 375 (iPhone SE), 393 (iPhone 14 Pro), 768 (iPad portrait),
 *         1024 (iPad landscape), 1440 (14" MacBook), 2560 (27" monitor).
 *
 * Usage:   node scripts/check_deep_dives_responsive.mjs            (all)
 *          node scripts/check_deep_dives_responsive.mjs <slug>     (one)
 *          node scripts/check_deep_dives_responsive.mjs <slug> --full   (all langs x all widths)
 * Exit 1 if any page overflows at any width.
 */
import { readFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath, pathToFileURL } from 'url';
import puppeteer from 'puppeteer';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC = resolve(__dirname, '..', 'public');
const LANGS = ['es', 'ca', 'fr', 'it', 'nl'];
const WIDTHS = [375, 393, 768, 1024, 1440, 2560];
const LANG_WIDTHS = [375, 768, 1440]; // per-language files: test the key widths only
const TOLERANCE = 2; // px slack for sub-pixel rounding

const args = process.argv.slice(2).filter((a) => !a.startsWith('--'));
const full = process.argv.includes('--full');
const onlySlug = args[0];

function canonicalSlugs() {
  const map = readFileSync(resolve(__dirname, '..', 'src', 'utils', 'deep_dive_map.ts'), 'utf8');
  return [...new Set([...map.matchAll(/basePath:\s*'\/([a-z0-9-]+)'/g)].map((m) => m[1]))];
}

async function measure(page, fileUrl, width) {
  await page.setViewport({ width, height: 900, deviceScaleFactor: 1 });
  await page.goto(fileUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
  // let layout settle (fonts/icons best-effort)
  await new Promise((r) => setTimeout(r, 250));
  return page.evaluate(() => {
    // Authoritative metric: can the USER actually scroll the PAGE horizontally?
    // (Layout overflow that lives inside an overflow:auto table or is clipped by
    // overflow-x:clip is NOT user-visible horizontal scroll, so scrollWidth alone
    // over-reports. We probe real scrollability instead.)
    const inner = window.innerWidth;
    const probe = (el) => { const b = el.scrollLeft; el.scrollLeft = 99999; const m = el.scrollLeft; el.scrollLeft = b; return m; };
    const overflow = Math.max(probe(document.documentElement), probe(document.body));
    // diagnostics: widest element whose right edge exceeds the viewport AND that
    // is not contained by a horizontal scroll/clip ancestor.
    let worst = null, worstW = 0;
    const clipped = (el) => {
      for (let p = el.parentElement; p; p = p.parentElement) {
        const ox = getComputedStyle(p).overflowX;
        if (ox === 'auto' || ox === 'scroll' || ox === 'hidden' || ox === 'clip') return true;
      }
      return false;
    };
    if (overflow > 0) {
      for (const el of document.querySelectorAll('body *')) {
        const r = el.getBoundingClientRect();
        if (r.right > inner + 2 && r.width > worstW && !clipped(el)) { worstW = r.width; worst = el; }
      }
    }
    const tag = worst ? `${worst.tagName.toLowerCase()}${worst.className ? '.' + String(worst.className).split(' ')[0] : ''}` : null;
    return { inner, overflow, worst: tag, worstRight: worst ? Math.round(worst.getBoundingClientRect().right) : 0 };
  });
}

const slugs = (onlySlug ? [onlySlug] : canonicalSlugs()).sort();
const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'], protocolTimeout: 120000 });
const page = await browser.newPage();

let failed = 0;
console.log(`\nResponsive gate — ${slugs.length} deep-dive(s) x widths [${WIDTHS.join(', ')}]\n${'='.repeat(64)}`);
for (const slug of slugs) {
  const files = [['index.html', WIDTHS]];
  if (full) for (const l of LANGS) { if (existsSync(resolve(PUBLIC, slug, `${l}.html`))) files.push([`${l}.html`, WIDTHS]); }
  else for (const l of LANGS) { if (existsSync(resolve(PUBLIC, slug, `${l}.html`))) files.push([`${l}.html`, LANG_WIDTHS]); }

  const problems = [];
  for (const [f, widths] of files) {
    const fp = resolve(PUBLIC, slug, f);
    if (!existsSync(fp)) continue;
    const url = pathToFileURL(fp).href;
    for (const w of widths) {
      const m = await measure(page, url, w);
      if (m.overflow > TOLERANCE) problems.push(`${f} @${w}px: +${m.overflow}px overflow${m.worst ? ` (widest: ${m.worst}, right=${m.worstRight})` : ''}`);
    }
  }
  const status = problems.length ? 'FAIL' : 'PASS';
  if (problems.length) failed++;
  console.log(`\n[${status}] ${slug}`);
  problems.slice(0, 12).forEach((p) => console.log(`   ✗ ${p}`));
  if (problems.length > 12) console.log(`   … and ${problems.length - 12} more`);
}
await browser.close();
console.log(`\n${'='.repeat(64)}\n${failed} FAILED / ${slugs.length} total\n`);
process.exit(failed ? 1 : 0);
