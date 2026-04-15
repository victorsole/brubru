/**
 * Post-build pre-rendering script
 *
 * Boots a local server from dist/, visits each public route with Puppeteer,
 * captures the rendered HTML, and writes it back so crawlers see real content
 * instead of an empty <div id="root"></div>.
 *
 * Also updates sitemap.xml lastmod dates to the current build date.
 *
 * Usage:  node scripts/prerender.mjs
 * Called by:  npm run build:prerender
 */

import { readFileSync, writeFileSync, mkdirSync, readdirSync, copyFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import puppeteer from 'puppeteer';
import sirv from 'sirv';
import { createServer } from 'http';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DIST = resolve(__dirname, '..', 'dist');
const SITE_URL = 'https://brubru.beresol.eu';
const OG_IMAGE = `${SITE_URL}/assets/brubru_og_image.png`;

const ROUTES = [
  { path: '/', title: 'Brubru - AI Companion for EU Advocacy', description: 'AI-powered strategic advocacy assistant for EU policy professionals. Analyse legislation, draft amendments, and navigate EU institutional processes.' },
  { path: '/login', title: 'Login - Brubru', description: 'Sign in to Brubru, your AI companion for EU policy advocacy.' },
  { path: '/signup', title: 'Sign Up - Brubru', description: 'Create your Brubru account and start navigating EU policy with AI.' },
  { path: '/about', title: 'About - Brubru', description: 'Learn about Brubru, the AI-powered platform helping EU policy professionals with legislative analysis, amendments, and advocacy.' },
  { path: '/contact', title: 'Contact - Brubru', description: 'Get in touch with the Brubru team at Beresol.' },
  { path: '/privacy', title: 'Privacy Policy - Brubru', description: 'Brubru privacy policy. How we handle your data.' },
  { path: '/terms', title: 'Terms of Service - Brubru', description: 'Brubru terms of service and conditions of use.' },
  { path: '/cookies', title: 'Cookie Policy - Brubru', description: 'Brubru cookie policy and tracking information.' },
  { path: '/subprocessors', title: 'Subprocessors - Brubru', description: 'List of third-party subprocessors used by Brubru.' },
  { path: '/api', title: 'Brubru API - The EU, structured.', description: 'Brubru Data Provider API. REST + MCP access to 28,500+ EU laws, 1,200+ legislative procedures, live consultation feedback, commissioner agendas, and legal-text intelligence. Professional subscription.' },
];

async function prerender() {
  // Save original index.html (the SPA shell with JS entry point)
  const originalIndex = resolve(DIST, 'index.html');
  const backupIndex = resolve(DIST, '_original_index.html');
  copyFileSync(originalIndex, backupIndex);

  // Start a local static server from dist/ (serves the original, unmodified files)
  const handler = sirv(DIST, { single: true });
  const server = createServer(handler);
  await new Promise((res) => server.listen(0, res));
  const port = server.address().port;
  const origin = `http://localhost:${port}`;
  console.log(`[prerender] Serving dist/ on ${origin}`);

  const browser = await puppeteer.launch({ headless: true });

  // Collect all rendered HTML in memory first, write to disk only after all routes are done
  const results = [];

  for (const route of ROUTES) {
    const url = `${origin}${route.path}`;
    console.log(`[prerender] Rendering ${route.path} ...`);

    const page = await browser.newPage();

    // Silence console noise from failed API/Supabase requests
    page.on('pageerror', () => {});
    page.on('console', () => {});

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });

    // Wait for React to render content (with fallback)
    try {
      await page.waitForFunction(
        () => document.getElementById('root')?.innerHTML?.trim().length > 0,
        { timeout: 5000 }
      );
    } catch {
      console.log(`[prerender]   (content check timed out, capturing current state)`);
    }
    // Extra settle time for animations/transitions
    await new Promise((r) => setTimeout(r, 1000));

    // Inject per-route <title>, <meta description>, canonical, OG and Twitter tags
    const canonicalUrl = route.path === '/' ? SITE_URL + '/' : SITE_URL + route.path;
    await page.evaluate((meta) => {
      document.title = meta.title;

      // Helper: set or create a meta tag
      function setMeta(attr, attrVal, content) {
        let el = document.querySelector(`meta[${attr}="${attrVal}"]`);
        if (el) {
          el.setAttribute('content', content);
        } else {
          el = document.createElement('meta');
          el.setAttribute(attr, attrVal);
          el.setAttribute('content', content);
          document.head.appendChild(el);
        }
      }

      // Standard meta
      setMeta('name', 'description', meta.description);

      // Canonical URL
      let canonical = document.querySelector('link[rel="canonical"]');
      if (canonical) {
        canonical.setAttribute('href', meta.canonicalUrl);
      } else {
        canonical = document.createElement('link');
        canonical.setAttribute('rel', 'canonical');
        canonical.setAttribute('href', meta.canonicalUrl);
        document.head.appendChild(canonical);
      }

      // Open Graph
      setMeta('property', 'og:title', meta.title);
      setMeta('property', 'og:description', meta.description);
      setMeta('property', 'og:url', meta.canonicalUrl);
      setMeta('property', 'og:image', meta.ogImage);
      setMeta('property', 'og:type', 'website');
      setMeta('property', 'og:site_name', 'Brubru');
      setMeta('property', 'og:locale', 'en_GB');

      // Twitter Card
      setMeta('name', 'twitter:card', 'summary_large_image');
      setMeta('name', 'twitter:title', meta.title);
      setMeta('name', 'twitter:description', meta.description);
      setMeta('name', 'twitter:image', meta.ogImage);
    }, { ...route, canonicalUrl, ogImage: OG_IMAGE });

    const html = await page.content();
    const rootContent = await page.evaluate(() => {
      const el = document.getElementById('root');
      return el ? el.innerHTML.trim().length : 0;
    });

    await page.close();

    results.push({ route, html, hasContent: rootContent > 0 });
    console.log(`[prerender]   captured (${rootContent > 0 ? rootContent + ' chars' : 'empty'})`);
  }

  await browser.close();
  server.close();

  // Find the JS entry file name (Vite hashes it)
  const assets = readdirSync(resolve(DIST, 'assets'));
  const jsEntry = assets.find((f) => f.startsWith('index-') && f.endsWith('.js'));
  const cssEntry = assets.find((f) => f.startsWith('index-') && f.endsWith('.css'));

  // Write pre-rendered files to disk
  for (const { route, html, hasContent } of results) {
    if (!hasContent) {
      console.log(`[prerender] Skipping ${route.path} (no content rendered)`);
      continue;
    }

    // For sub-routes, write to route/index.html
    // These are served directly by Apache when the crawler visits /about -> /about/index.html
    if (route.path === '/') {
      // Root: keep the script tag so the SPA still works
      writeFileSync(originalIndex, html, 'utf-8');
      // Ensure the JS entry is present
      if (jsEntry && !html.includes(jsEntry)) {
        const patched = html.replace(
          '</body>',
          `    <script type="module" crossorigin src="/assets/${jsEntry}"></script>\n  </body>`
        );
        writeFileSync(originalIndex, patched, 'utf-8');
      }
    } else {
      const dir = resolve(DIST, route.path.slice(1));
      mkdirSync(dir, { recursive: true });
      // Sub-route files: include the JS entry so users landing directly on these pages
      // can still get the full SPA experience
      let output = html;
      if (jsEntry && !html.includes(jsEntry)) {
        output = html.replace(
          '</body>',
          `    <script type="module" crossorigin src="/assets/${jsEntry}"></script>\n  </body>`
        );
      }
      writeFileSync(resolve(dir, 'index.html'), output, 'utf-8');
    }

    console.log(`[prerender] Wrote ${route.path === '/' ? 'index.html' : route.path.slice(1) + '/index.html'}`);
  }

  // Auto-update sitemap.xml lastmod dates to today's build date
  const sitemapPath = resolve(DIST, 'sitemap.xml');
  try {
    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
    let sitemap = readFileSync(sitemapPath, 'utf-8');
    sitemap = sitemap.replace(/<lastmod>\d{4}-\d{2}-\d{2}<\/lastmod>/g, `<lastmod>${today}</lastmod>`);
    writeFileSync(sitemapPath, sitemap, 'utf-8');
    console.log(`[prerender] Updated sitemap.xml lastmod dates to ${today}`);
  } catch (err) {
    console.log(`[prerender] Warning: could not update sitemap.xml: ${err.message}`);
  }

  // Clean up backup
  try {
    const { unlinkSync } = await import('fs');
    unlinkSync(backupIndex);
  } catch { /* no-op */ }

  const rendered = results.filter((r) => r.hasContent).length;
  const skipped = results.filter((r) => !r.hasContent).length;
  console.log(`[prerender] Done. Rendered: ${rendered}, Skipped (empty): ${skipped}`);
}

prerender().catch((err) => {
  console.error('[prerender] Failed:', err);
  process.exit(1);
});
