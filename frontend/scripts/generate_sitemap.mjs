/**
 * sitemap generator
 *
 * Walks dist/ for every directory with an index.html and every standalone
 * .html file, and walks data/legislacio-ue-catala/ for the Catalan acquis
 * (uploaded directly to SiteGround, not part of the Vite build).
 *
 * Emits THREE files in dist/:
 *   - sitemap.xml             sitemap index pointing at the two children below
 *   - sitemap-pages.xml       high-value pages (~60 URLs): deep-dives, guides,
 *                             marketing, app routes, Catalan landing, etc.
 *   - sitemap-legislacio.xml  Catalan act pages under /legislacio-ue-catala/<celex>/
 *
 * Splitting keeps the high-value pages fast to crawl + observable in GSC, while
 * the bulk Catalan corpus stays in its own sitemap (so we can detach or filter
 * it later without disturbing the main index).
 *
 * Replaces the hand-edited frontend/public/sitemap.xml. Runs as the last step
 * of `npm run build:prerender`, after pre-rendering and Vite build.
 *
 * Usage:  node scripts/generate_sitemap.mjs
 */

import { readdirSync, statSync, writeFileSync } from 'fs';
import { join, relative, dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(__dirname, '..', 'dist');
const DATA_CATALAN = resolve(__dirname, '..', '..', 'data', 'legislacio-ue-catala');
const SITE = 'https://brubru.beresol.eu';
const TODAY = new Date().toISOString().slice(0, 10);

const SKIP_DIRS = new Set(['assets', 'New-Yorker-Font']);
const SKIP_FILES = new Set(['_original_index.html']);

const ROUTE_META = {
  '/':                              { priority: 1.0, changefreq: 'weekly'  },
  '/about/':                        { priority: 0.8, changefreq: 'monthly' },
  '/api/':                          { priority: 0.9, changefreq: 'weekly'  },
  '/contact/':                      { priority: 0.7, changefreq: 'monthly' },
  '/login/':                        { priority: 0.5, changefreq: 'monthly' },
  '/signup/':                       { priority: 0.6, changefreq: 'monthly' },
  '/privacy/':                      { priority: 0.4, changefreq: 'yearly'  },
  '/terms/':                        { priority: 0.4, changefreq: 'yearly'  },
  '/cookies/':                      { priority: 0.3, changefreq: 'yearly'  },
  '/subprocessors/':                { priority: 0.4, changefreq: 'yearly'  },
  '/guides/':                       { priority: 0.9, changefreq: 'daily'   },
  '/data-architecture/':            { priority: 0.8, changefreq: 'monthly' },
  '/clientpitch/':                  { priority: 0.5, changefreq: 'monthly' },
  '/innoviris/':                    { priority: 0.4, changefreq: 'yearly'  },
  '/eu-inc/':                       { priority: 0.9, changefreq: 'weekly'  },
  '/industrial-accelerator-act/':   { priority: 0.9, changefreq: 'weekly'  },
  '/digital-networks-act/':         { priority: 0.9, changefreq: 'weekly'  },
  '/biotech-act/':                  { priority: 0.9, changefreq: 'weekly'  },
  '/csam-regulation/':              { priority: 0.9, changefreq: 'weekly'  },
  '/late-payments/':                { priority: 0.9, changefreq: 'weekly'  },
  '/pharma-laws/':                  { priority: 0.8, changefreq: 'weekly'  },
  '/legislacio-ue-catala/':         { priority: 0.9, changefreq: 'daily'   },
  '/main/':                         { priority: 0.9, changefreq: 'daily'   },
  '/my-eu-bubble/':                 { priority: 0.9, changefreq: 'daily'   },
  '/amendator/':                    { priority: 0.9, changefreq: 'daily'   },
  '/eulawcomply/':                  { priority: 0.8, changefreq: 'weekly'  },
  '/tenderator/':                   { priority: 0.8, changefreq: 'weekly'  },
};

const SPA_ROUTES = ['/main/', '/my-eu-bubble/', '/amendator/', '/eulawcomply/', '/tenderator/'];

const DEEP_DIVE_DIRS = [
  'eu-inc', 'industrial-accelerator-act', 'digital-networks-act',
  'biotech-act', 'csam-regulation', 'late-payments', 'pharma-laws',
];

function metaFor(urlPath) {
  if (ROUTE_META[urlPath]) return ROUTE_META[urlPath];
  if (urlPath.startsWith('/legislacio-ue-catala/')) {
    return { priority: 0.6, changefreq: 'monthly' };
  }
  const langMatch = urlPath.match(/^\/([^/]+)\/([a-z]{2})\.html$/);
  if (langMatch && DEEP_DIVE_DIRS.includes(langMatch[1])) {
    return { priority: 0.7, changefreq: 'weekly' };
  }
  if (urlPath.startsWith('/api/docs/')) {
    return { priority: 0.7, changefreq: 'monthly' };
  }
  if (urlPath.startsWith('/analytics/')) {
    return { priority: 0.6, changefreq: 'monthly' };
  }
  return { priority: 0.7, changefreq: 'monthly' };
}

function shouldSkipName(name) {
  if (name.startsWith('.')) return true;     // .htaccess, .DS_Store
  if (name.startsWith('_')) return true;     // _assets, _original_index.html, etc.
  if (name.includes(' ')) return true;       // macOS Finder duplicates ("foo 2.html")
  if (SKIP_DIRS.has(name)) return true;
  if (SKIP_FILES.has(name)) return true;
  return false;
}

function walkDir(root, urls) {
  let entries;
  try {
    entries = readdirSync(root, { withFileTypes: true });
  } catch {
    return urls;
  }
  for (const entry of entries) {
    if (shouldSkipName(entry.name)) continue;

    const full = join(root, entry.name);
    if (entry.isDirectory()) {
      const indexPath = join(full, 'index.html');
      try {
        if (statSync(indexPath).isFile()) {
          const rel = '/' + relative(DIST, full).split('/').join('/') + '/';
          urls.add(rel);
        }
      } catch { /* no index.html */ }
      walkDir(full, urls);
    } else if (entry.isFile() && entry.name.endsWith('.html')) {
      if (entry.name === 'index.html') continue;
      const rel = '/' + relative(DIST, full).split('/').join('/');
      urls.add(rel);
    }
  }
  return urls;
}

function walkCatalanData(urls) {
  let entries;
  try {
    entries = readdirSync(DATA_CATALAN, { withFileTypes: true });
  } catch (err) {
    console.log(`[sitemap] data/legislacio-ue-catala/ not found, skipping (${err.code || err.message})`);
    return 0;
  }
  let added = 0;
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (shouldSkipName(entry.name)) continue;
    const indexPath = join(DATA_CATALAN, entry.name, 'index.html');
    try {
      if (statSync(indexPath).isFile()) {
        urls.add(`/legislacio-ue-catala/${entry.name}/`);
        added++;
      }
    } catch { /* no index */ }
  }
  return added;
}

function buildUrlset(urlPaths) {
  const lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ];
  for (const url of urlPaths) {
    const m = metaFor(url);
    lines.push('  <url>');
    lines.push(`    <loc>${SITE}${url}</loc>`);
    lines.push(`    <lastmod>${TODAY}</lastmod>`);
    lines.push(`    <changefreq>${m.changefreq}</changefreq>`);
    lines.push(`    <priority>${m.priority.toFixed(1)}</priority>`);
    lines.push('  </url>');
  }
  lines.push('</urlset>');
  return lines.join('\n') + '\n';
}

function buildSitemapIndex(childFilenames) {
  const lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ];
  for (const name of childFilenames) {
    lines.push('  <sitemap>');
    lines.push(`    <loc>${SITE}/${name}</loc>`);
    lines.push(`    <lastmod>${TODAY}</lastmod>`);
    lines.push('  </sitemap>');
  }
  lines.push('</sitemapindex>');
  return lines.join('\n') + '\n';
}

function isCatalanAct(urlPath) {
  // /legislacio-ue-catala/<celex>/  (NOT the bare landing /legislacio-ue-catala/)
  return /^\/legislacio-ue-catala\/[^/]+\/$/.test(urlPath)
    && urlPath !== '/legislacio-ue-catala/';
}

function main() {
  const urls = new Set();
  urls.add('/');
  walkDir(DIST, urls);
  for (const r of SPA_ROUTES) urls.add(r);
  const catalanAdded = walkCatalanData(urls);

  const sorted = [...urls].sort();
  const pages = sorted.filter((u) => !isCatalanAct(u));
  const acts = sorted.filter((u) => isCatalanAct(u));

  writeFileSync(join(DIST, 'sitemap-pages.xml'), buildUrlset(pages), 'utf-8');
  writeFileSync(join(DIST, 'sitemap-legislacio.xml'), buildUrlset(acts), 'utf-8');
  writeFileSync(
    join(DIST, 'sitemap.xml'),
    buildSitemapIndex(['sitemap-pages.xml', 'sitemap-legislacio.xml']),
    'utf-8',
  );

  console.log(`[sitemap] Wrote sitemap.xml (index)`);
  console.log(`[sitemap]   sitemap-pages.xml: ${pages.length} URLs`);
  console.log(`[sitemap]   sitemap-legislacio.xml: ${acts.length} URLs`);
  console.log(`[sitemap]   total: ${sorted.length} URLs (+${catalanAdded} from data/legislacio-ue-catala/)`);
}

main();
