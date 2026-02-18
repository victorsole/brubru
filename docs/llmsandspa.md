Summary: GEO Optimisation (llms.txt + SPA Pre-rendering + SEO Meta)

  1. llms.txt

  A markdown file at the site root that describes the site to LLM crawlers (standard from llmstxt.org).

  Files created:
  - frontend/public/llms.txt -- site description, features, pricing, tech stack, key pages
  - Root llms.txt -- copy for the repo root

  Wiring:
  - frontend/index.html -- added <link rel="alternate" type="text/plain" href="/llms.txt" title="LLMs.txt">
  - frontend/public/robots.txt -- added Llmstxt: https://brubru.beresol.eu/llms.txt

  Template for Beresol: Write a markdown file describing the site. Include company name, what it does, key pages with URLs, pricing if applicable, and contact
  info. Keep it under ~2KB. Link it from <head> and robots.txt.

  ---
  2. SPA Pre-rendering

  Post-build step that renders public pages to static HTML using Puppeteer so AI crawlers see real content.

  Dependencies (devDependencies):

  npm install --save-dev puppeteer sirv


  Files:

  ┌───────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │         File          │                                              What it does                                              │
  ├───────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ scripts/prerender.mjs │ Boots sirv from dist/, visits each route with Puppeteer, captures HTML, writes dist/{route}/index.html │
  ├───────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ src/main.tsx          │ Conditional hydration -- hydrateRoot if pre-rendered content exists, createRoot otherwise              │
  ├───────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ public/robots.txt     │ Explicit Allow for GPTBot, ClaudeBot, PerplexityBot, Google-Extended                                   │
  ├───────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ package.json          │ Added "build:prerender": "tsc -b && vite build && node scripts/prerender.mjs"                          │
  └───────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  How main.tsx changes:
  // Before
  createRoot(document.getElementById('root')!).render(<App />);

  // After
  const root = document.getElementById('root')!;
  if (root.innerHTML.trim().length > 0) {
    hydrateRoot(root, <App />);
  } else {
    createRoot(root).render(<App />);
  }

  How prerender.mjs works:
  1. Saves original dist/index.html as backup
  2. Starts sirv serving dist/ on a random port
  3. For each route: opens Puppeteer page, navigates, waits for #root to have content
  4. Injects per-route <title>, <meta description>, canonical URL, OG tags, and Twitter Card tags
  5. After all routes captured in memory, writes each to dist/{route}/index.html
  6. Preserves the <script type="module"> tag in all files so the SPA still works for real users
  7. Auto-updates sitemap.xml lastmod dates to the current build date

  Key gotchas solved:
  - Don't overwrite dist/index.html mid-render (breaks subsequent routes since sirv serves it as SPA fallback)
  - Don't block Supabase/API requests (auth state won't resolve, pages stay empty)
  - Use networkidle2 not networkidle0 (more lenient for failed network requests)
  - Use a try/catch on the content wait with fallback (some pages may timeout)
  - Skip routes with no content rather than writing empty files

  robots.txt additions:

  User-agent: GPTBot
  Allow: /
  Disallow: /auth/
  Disallow: /admin

  User-agent: ClaudeBot
  Allow: /
  Disallow: /auth/
  Disallow: /admin


  (Same for PerplexityBot and Google-Extended)

  Build & deploy:

  npm run build              # normal SPA build (no pre-rendering)
  npm run build:prerender    # build + pre-render (use for production)


  The dist/ folder then has about/index.html, privacy/index.html, etc. Apache/Nginx serves these directly via DirectoryIndex.

  ---
  3. Open Graph + Twitter Card Meta Tags (February 2026)

  Every pre-rendered page gets per-route OG and Twitter meta tags for link previews on social media, Slack, WhatsApp, etc.

  Base tags in index.html (fallback for non-pre-rendered routes):

  <!-- Open Graph -->
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="Brubru" />
  <meta property="og:title" content="Brubru - AI Companion for EU Advocacy" />
  <meta property="og:description" content="AI-powered strategic advocacy assistant..." />
  <meta property="og:url" content="https://brubru.beresol.eu/" />
  <meta property="og:image" content="https://brubru.beresol.eu/assets/brubru_og_image.png" />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:locale" content="en_GB" />
  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="Brubru - AI Companion for EU Advocacy" />
  <meta name="twitter:description" content="AI-powered strategic advocacy assistant..." />
  <meta name="twitter:image" content="https://brubru.beresol.eu/assets/brubru_og_image.png" />

  Per-route overrides: The prerender script injects per-route og:title, og:description, og:url,
  twitter:title, twitter:description, and canonical URL using page.evaluate(). The og:image stays
  the same across all pages (brubru_og_image.png -- 1200x630px, logo on white with blue accent bar).

  ---
  4. Canonical URLs (February 2026)

  Prevents duplicate content issues between / and /index.html.

  - Base tag in index.html: <link rel="canonical" href="https://brubru.beresol.eu/" />
  - Prerender script updates the canonical href per route (e.g. /about -> https://brubru.beresol.eu/about)

  ---
  5. JSON-LD Structured Data (February 2026)

  Rich schema markup in index.html for Google rich results and AI answer engines. Uses @graph with three entities:

  Organization (Beresol BV):
  - name, url, logo, contactPoint (email: hello@beresol.eu)

  WebSite (Brubru):
  - name, url, publisher -> Organization, inLanguage: en-GB

  SoftwareApplication (Brubru):
  - applicationCategory: BusinessApplication
  - operatingSystem: Web
  - 3 Offer nodes: White (free), Yellow (EUR 79/month), Blue (EUR 599/month)

  Validation: Paste the page URL into https://search.google.com/test/rich-results to verify.

  ---
  6. Sitemap (February 2026)

  File: frontend/public/sitemap.xml

  Contains all public pages, analytics pages, and authenticated app routes.
  The analytics page /analytics/eu_law_linguistics.html is included (priority 0.6, monthly).

  Lastmod automation: The prerender script auto-updates all <lastmod> dates in sitemap.xml
  to the current build date (YYYY-MM-DD) after pre-rendering. No need to manually update dates.

  ---
  Still TODO:

  - Google Search Console: Verify site ownership and submit sitemap.xml (manual step)
  - Bing Webmaster Tools: Same for Bing (manual step)
