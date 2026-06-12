/**
 * Deep-dive standard validator.
 *
 * Enforces the Brubru deep-dive standard:
 *   1. i18n integrity
 *        - single-file i18n (data-i18n + `const translations`): every data-i18n key
 *          must exist in ALL 5 language objects (es/ca/fr/it/nl). Missing key = drift.
 *        - separate per-language files (legacy): the structural skeleton of each
 *          language file must match index.html (same count of sections / timeline
 *          items / tables / rows). A mismatch = drift (the IAA-staleness class of bug).
 *   2. Responsiveness — every deep-dive HTML must carry the viewport meta and the
 *      mandated breakpoints (max-width: 1024 / 900 / 767). See CLAUDE.md responsive rule.
 *   3. Quality — 0 em-dashes, exactly one active timeline item, an "Updated" footer date.
 *
 * Usage:   node scripts/check_deep_dives.mjs            (validate all)
 *          node scripts/check_deep_dives.mjs <slug>     (validate one)
 * Exit code 1 if any deep-dive FAILS (so it can gate a deploy).
 */
import { readFileSync, readdirSync, existsSync, statSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PUBLIC = resolve(__dirname, '..', 'public');
const LANGS = ['es', 'ca', 'fr', 'it', 'nl'];
const onlySlug = process.argv[2];

// ---- helpers -------------------------------------------------------------
const read = (p) => readFileSync(p, 'utf8');
const count = (s, re) => (s.match(re) || []).length;

function isDeepDive(dir) {
  const idx = resolve(PUBLIC, dir, 'index.html');
  if (!existsSync(idx)) return false;
  const html = read(idx);
  return /class="timeline|procedure-file|class="section__title|data-i18n=/.test(html);
}

function detectPattern(dir) {
  const langFiles = LANGS.filter((l) => existsSync(resolve(PUBLIC, dir, `${l}.html`)));
  const idx = read(resolve(PUBLIC, dir, 'index.html'));
  if (/const\s+translations\s*=/.test(idx)) return { type: 'single-i18n', langFiles };
  if (langFiles.length >= 3) return { type: 'separate', langFiles };
  return { type: 'en-only', langFiles };
}

// Extract the `const translations = { ... }` object literal, brace-balanced,
// ignoring braces inside string literals. Returns the evaluated object or null.
function extractTranslations(html) {
  const m = /const\s+translations\s*=\s*\{/.exec(html);
  if (!m) return null;
  let i = m.index + m[0].length - 1; // at the opening {
  let depth = 0, q = null, esc = false;
  const start = i;
  for (; i < html.length; i++) {
    const c = html[i];
    if (esc) { esc = false; continue; }
    if (q) {
      if (c === '\\') esc = true;
      else if (c === q) q = null;
      continue;
    }
    if (c === '"' || c === "'" || c === '`') { q = c; continue; }
    if (c === '{') depth++;
    else if (c === '}') { depth--; if (depth === 0) { i++; break; } }
  }
  const objText = html.slice(start, i);
  try { return (0, eval)('(' + objText + ')'); } catch (e) { return { __error: e.message }; }
}

function dataI18nKeys(html) {
  const keys = new Set();
  const re = /data-i18n="([^"]+)"/g;
  let m;
  while ((m = re.exec(html))) keys.add(m[1]);
  return keys;
}

// structural skeleton signature for separate-file parity
function skeleton(html) {
  return {
    sections: count(html, /<section\b/g),
    timelineItems: count(html, /class="timeline__item(?!--active)/g) + count(html, /class="timeline__item timeline__item--active"/g),
    tables: count(html, /<table\b/g),
    rows: count(html, /<tr\b/g),
    headers: count(html, /class="section__title"/g),
  };
}

// Static responsiveness signal. Missing viewport = hard fail (page is not
// responsive at all). Missing a mandated breakpoint = warn only: it is a proxy
// (a 1-2 column page may legitimately not need the 900 breakpoint). The
// authoritative gate is the real overflow test in check_deep_dives_responsive.mjs.
function responsiveProblems(html) {
  const out = { fail: [], warn: [] };
  if (!/name="viewport"/.test(html)) out.fail.push('no viewport meta');
  const has = (lo, hi) => new RegExp(`@media[^{]*max-width:\\s*(${lo}|${hi})px`).test(html);
  if (!has(1024, 1023)) out.warn.push('no max-width:1024 breakpoint (verify via responsive test)');
  if (!has(900, 901)) out.warn.push('no max-width:900 breakpoint (verify via responsive test)');
  if (!has(767, 768)) out.warn.push('no max-width:767 breakpoint (verify via responsive test)');
  return out;
}

function activeTimelineCount(html) {
  // count the DIV (not the CSS selector ::before)
  return count(html, /class="timeline__item[^"]*timeline__item--active"/g) + count(html, /class="timeline__item active"/g);
}

// ---- per-deep-dive validation -------------------------------------------
function validate(dir) {
  const fail = [], warn = [];
  const idxPath = resolve(PUBLIC, dir, 'index.html');
  const idx = read(idxPath);
  const { type, langFiles } = detectPattern(dir);

  // responsiveness (EN + every lang file)
  const filesToCheck = ['index.html', ...langFiles.map((l) => `${l}.html`)];
  for (const f of filesToCheck) {
    const probs = responsiveProblems(read(resolve(PUBLIC, dir, f)));
    probs.fail.forEach((p) => fail.push(`responsive [${f}]: ${p}`));
    probs.warn.forEach((p) => warn.push(`responsive [${f}]: ${p}`));
  }

  // quality (EN)
  if (count(idx, /—/g) > 0) fail.push(`${count(idx, /—/g)} em-dash(es) in index.html`);
  const ac = activeTimelineCount(idx);
  if (/class="timeline"/.test(idx) && ac !== 1) warn.push(`index.html has ${ac} active timeline items (expected 1)`);
  if (!/Updated|Last updated|Actualizado|Actualitzat|Mis &agrave; jour|Aggiornato|Bijgewerkt/i.test(idx))
    warn.push('no "Updated <date>" marker in footer');

  if (type === 'single-i18n') {
    const t = extractTranslations(idx);
    if (!t) fail.push('could not locate translations object');
    else if (t.__error) fail.push(`translations object does not parse: ${t.__error}`);
    else {
      const keys = dataI18nKeys(idx);
      for (const l of LANGS) {
        if (!t[l]) { fail.push(`translations missing language object: ${l}`); continue; }
        const missing = [...keys].filter((k) => !(k in t[l]));
        if (missing.length) fail.push(`[${l}] missing ${missing.length} i18n keys: ${missing.slice(0, 8).join(', ')}${missing.length > 8 ? '…' : ''}`);
      }
    }
  } else if (type === 'separate') {
    const base = skeleton(idx);
    for (const l of langFiles) {
      const lh = read(resolve(PUBLIC, dir, `${l}.html`));
      const s = skeleton(lh);
      for (const k of Object.keys(base)) {
        if (s[k] !== base[k]) fail.push(`[${l}.html] structural drift: ${k}=${s[k]} but index.html=${base[k]}`);
      }
      if (count(lh, /—/g) > 0) fail.push(`[${l}.html] ${count(lh, /—/g)} em-dash(es)`);
    }
    if (langFiles.length < 5) warn.push(`only ${langFiles.length}/5 language files present`);
  } else {
    warn.push('EN-only deep-dive (no translations) — consider single-file i18n standard');
  }

  return { dir, type, langs: langFiles.length, fail, warn };
}

// ---- run -----------------------------------------------------------------
// Canonical deep-dive list = the basePath slugs registered in deep_dive_map.ts.
function canonicalSlugs() {
  try {
    const map = read(resolve(__dirname, '..', 'src', 'utils', 'deep_dive_map.ts'));
    const slugs = [...map.matchAll(/basePath:\s*'\/([a-z0-9-]+)'/g)].map((m) => m[1]);
    return [...new Set(slugs)];
  } catch { return null; }
}
const registry = canonicalSlugs();
const dirs = (onlySlug ? [onlySlug] : (registry || readdirSync(PUBLIC).filter(isDeepDive)))
  .filter((d) => { try { return statSync(resolve(PUBLIC, d)).isDirectory() && existsSync(resolve(PUBLIC, d, 'index.html')); } catch { return false; } })
  .sort();

let failed = 0;
console.log(`\nDeep-dive standard check — ${dirs.length} deep-dive(s)\n${'='.repeat(60)}`);
for (const d of dirs) {
  const r = validate(d);
  const status = r.fail.length ? 'FAIL' : (r.warn.length ? 'WARN' : 'PASS');
  if (r.fail.length) failed++;
  console.log(`\n[${status}] ${r.dir}  (${r.type}, ${r.langs} langs)`);
  r.fail.forEach((x) => console.log(`   ✗ ${x}`));
  r.warn.forEach((x) => console.log(`   • ${x}`));
}
console.log(`\n${'='.repeat(60)}\n${failed} FAILED / ${dirs.length} total\n`);
process.exit(failed ? 1 : 0);
