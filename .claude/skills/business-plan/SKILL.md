---
name: business-plan
description: Reference skill for Brubru's business plan ecosystem. Lists all HTML and MD files, their purposes, URLs, and how to update them. Use when working on investor materials, strategy docs, or competitive analysis.
allowed-tools: ["Read", "Edit", "Write", "Bash", "Glob", "Grep", "WebFetch"]
---

# Brubru Business Plan Ecosystem

## HTML files (GitHub Pages)

All served from `https://victorsole.github.io/brubru/docs/business_plan/` (or local at `docs/business_plan/`).

| File | Purpose | Sections |
|------|---------|----------|
| `brubru_business_plan.html` | Full business plan. Password-gated, 10 tabbed sections. ~260 KB. | Overview, Product, Market, GTM, Technology, Team, Financials, Roadmap, AI Comparison, Daily Training |
| `strategy.html` | WAPU-first competitive emulation strategy. ~39 KB. | Phases A/B/C, Spaak analysis, dashboard metrics |
| `competitive_learnings.html` | Competitive intelligence. ~64 KB. | Spaak, PolicyTracker, Eulogos, FiscalNote. Observation vs Action platform comparison |
| `investment_memo.html` | a16z-style investment memo (Troy Kirwin template). ~31 KB. | Team, Problem, Product, GTM, Business Model, Traction, Competitive Landscape, Vision, Next 12 Months, Key Risks |

All 4 files are cross-linked via a `.bp-nav` navigation bar at the top.

## Print HTML and PDF generation

| File | Purpose |
|------|---------|
| `brubru_business_plan_print.html` | Print-optimised HTML for PDF generation. Separate from the interactive version. ~56 KB. |
| `brubru_business_plan.pdf` | PDF generated from print HTML via Puppeteer. ~1.1 MB. |

### PDF generation command

Run from `frontend/` directory (where `node_modules/puppeteer` lives):

```bash
cd frontend && node -e "
const puppeteer = require('puppeteer');
(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('file:///Users/victorsole/Documents/GitHub/brubru/docs/business_plan/brubru_business_plan_print.html', { waitUntil: 'networkidle0', timeout: 30000 });
  await page.pdf({
    path: '/Users/victorsole/Documents/GitHub/brubru/docs/business_plan/brubru_business_plan.pdf',
    format: 'A4',
    printBackground: true,
    margin: { top: '18mm', bottom: '20mm', left: '20mm', right: '20mm' }
  });
  await browser.close();
  console.log('PDF generated');
})();
"
```

**Important**: Use `require()` (CJS), not ESM imports. Puppeteer must be run from `frontend/` where node_modules exists.

## Shared assets

| Asset | Path |
|-------|------|
| Logo | `docs/business_plan/brubru_mainlogo.png` |
| Fonts | `docs/business_plan/fonts/ACaslonPro-{Regular,Semibold,Bold}.otf` |
| AI logos | `docs/business_plan/chatgpt.png`, `docs/business_plan/claude.png` |
| PDF export | `docs/business_plan/brubru_business_plan.pdf` |

## Design system (mandatory for all HTML files)

| Element | Requirement |
|---------|-------------|
| **Font** | Adobe Caslon Pro via `@font-face` (relative paths to `fonts/`) |
| **Colours** | `#0693e3` (blue), `#059669` (green), `#9b51e0` (purple), `#d97706` (amber), `#dc2626` (red) |
| **Neutrals** | `#111827` (text), `#6b7280` (secondary), `#9ca3af` (muted), `#e5e7eb` (border), `#f3f4f6` (bg-alt) |
| **Logo** | `brubru_mainlogo.png` in header |
| **Nav bar** | `.bp-nav` class with 4 links, active state on current page |
| **Icons** | MDI Font from CDN `@mdi/font@7.4.47` |
| **Responsive** | 3 breakpoints: desktop >1024px, tablet 768-1024px, mobile <768px |

## Content rules (CRITICAL)

These rules apply to ALL business plan HTML and print files:

| Rule | Detail |
|------|--------|
| **No em-dashes** | Never use `--` or `&mdash;`. Use colons, commas, or restructure the sentence. |
| **Sentence case headings** | All h2 and h3 headings use sentence case, not Title Case. E.g. "Financial projections" not "Financial Projections". |
| **Founder name** | Always `Victor Sol&eacute;` (with accent). Never "Sole" without accent. |
| **Beresol references** | Always bold + linked: `<a href="https://beresol.eu" target="_blank" style="color: inherit; text-decoration: none; border-bottom: 1px solid currentColor;"><strong>Beresol BV</strong></a>` |
| **6 languages** | Brubru supports EN, FR, NL, ES, CA, IT. Never claim "23 EU languages". |
| **No emojis** | Use MDI icons or text, never emojis. |
| **British English** | analyse, colour, behaviour, etc. |

## Print HTML specific rules

The print HTML (`brubru_business_plan_print.html`) is a **separate file** from the interactive version. Changes to one do NOT propagate to the other.

| Rule | Detail |
|------|--------|
| **Page breaks** | `h2.pb` forces page break before. `.no-break` prevents page break inside. |
| **KPI strips** | `.kpi-strip` is a 4-column grid. Keep `padding: 7px 6px`, `font-size: 14pt` for values. |
| **Bar charts** | `.bar-chart` height is 105px. Max bar height should be ~82px to avoid overflow. |
| **Donut charts** | 80px diameter, 50px hole. Font: 8pt value, 5.5pt label. |
| **Content must fit** | KPI strip + bar chart + donut must all fit on one A4 page. If adding content, compact or split with `page-break-before: always`. |
| **Two-column layouts** | `.two-col` (1fr 1fr), `.two-col--41` (2fr 1fr), `.two-col--14` (1fr 2fr). |

## Key data points (keep updated)

| Metric | Value | Notes |
|--------|-------|-------|
| Founder | Victor Sol&eacute; | Belgian/Spanish, 17 years in Brussels |
| Company | Beresol BV | Belgian entity |
| North Star | WAPU (Weekly Active Paid Users) | Primary metric |
| WAPU targets | 10 (M3), 25 (M6), 50 (M12) | Phase A/B/C |
| Pricing | Starter 39, Advocate 59, Professional 99, EP 49 | EUR/month |
| Users | 57 registered users | As of 13 Mar 2026 |
| Brief subscribers | 82 | Daily brief email |
| Trainers | 11 Daily Training section users | |
| Knowledge guides | 67 | Backend knowledge base |
| EU data points | 3,400+ | Legislation, procedures, events |
| EU data sources | 30+ | Institutional scrapers |
| News portals | 44 | Scraped daily |
| AI stack | Mistral Small + Claude Haiku 4.5 + GPT-4 + Gemini | 4-tier fallback |
| Languages | 6 (EN, FR, NL, ES, CA, IT) | Never claim 23 |
| Main competitor | Spaak | Danish, VC-backed, distribution-led |
| Brubru advantage | Feature depth | Amendator, Predictions, EU Law Comply, Tenderator |

## How to update

1. Edit the HTML file directly (self-contained, no build step)
2. Ensure `.bp-nav` links are consistent across all 4 files
3. Push to main for GitHub Pages auto-deployment
4. If content changed significantly in the main business plan, also update print HTML and regenerate PDF
5. Always update BOTH the interactive HTML and the print HTML (they are separate files)
6. After regenerating PDF, verify the layout visually (especially financials page)
7. Use `git add -f` for files in `docs/` if they are gitignored

## Markdown source documents

| File | Purpose |
|------|---------|
| `docs/business_plan/brubru_business_plan.md` | Markdown source of business plan |
| `docs/business_plan/financial_model.md` | Financial projections |
| `docs/business_plan/competitive_benchmarking.md` | Benchmarking data |
| `docs/business_plan/competitive_learnings.md` | Competitive analysis markdown |
| `docs/marketing/pricing_strategy.md` | Full pricing strategy with Stripe IDs |
| `docs/marketing/vc_interview_strategy.md` | VC pitch preparation |

## Investor outreach

- **a16z contacts**: Jason Cui (jcui@a16z.com), Olivia Moore (omoore@a16z.com)
- **Pitch day**: 18 March 2026
- **BrubruBel**: Innoviris partnership proposal for Belgian public procurement (see `docs/applications/innoviris/`)
