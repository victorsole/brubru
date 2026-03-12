---
name: business-plan
description: Reference skill for Brubru's business plan ecosystem. Lists all HTML and MD files, their purposes, URLs, and how to update them. Use when working on investor materials, strategy docs, or competitive analysis.
---

# Brubru Business Plan Ecosystem

## HTML Files (GitHub Pages)

All served from `https://victorsole.github.io/brubru/docs/business_plan/` (or local at `docs/business_plan/`).

| File | Purpose | URL slug |
|------|---------|----------|
| `brubru_business_plan.html` | Full business plan with 8 tabbed sections (Overview, Product, Market, GTM, Tech, Team, Financials, Roadmap). Password-gated. | `brubru_business_plan.html` |
| `strategy.html` | WAPU-first competitive emulation strategy. Phases A/B/C, Spaak analysis, dashboard metrics. | `strategy.html` |
| `competitive_learnings.html` | Competitive intelligence: Spaak, PolicyTracker, Eulogos, FiscalNote, etc. Observation vs Action platform comparison. | `competitive_learnings.html` |
| `investment_memo.html` | a16z-style investment memo (Troy Kirwin template). 10 sections: Team, Problem, Product, GTM, Business Model, Traction, Competitive Landscape, Vision, Next 12 Months, Key Risks. | `investment_memo.html` |

All 4 files are cross-linked via a `.bp-nav` navigation bar at the top.

## Shared Assets

| Asset | Path |
|-------|------|
| Logo | `docs/business_plan/brubru_mainlogo.png` |
| Fonts | `docs/business_plan/fonts/ACaslonPro-{Regular,Semibold,Bold}.otf` |
| PDF export | `docs/business_plan/brubru_business_plan.pdf` |

## Design System (mandatory for all HTML files)

- **Font**: Adobe Caslon Pro via `@font-face` (relative paths to `fonts/`)
- **Colours**: `#0693e3` (blue), `#059669` (green), `#9b51e0` (purple), `#d97706` (amber), `#dc2626` (red)
- **Neutrals**: `#111827` (text), `#6b7280` (secondary), `#9ca3af` (muted), `#e5e7eb` (border), `#f3f4f6` (bg-alt)
- **Logo**: `brubru_mainlogo.png` in header
- **Nav bar**: `.bp-nav` class with 4 links, active state on current page
- **MDI Icons**: loaded from CDN `@mdi/font@7.4.47`
- **Responsive**: 3 breakpoints (desktop >1024px, tablet 768-1024px, mobile <768px)

## Markdown Strategy Documents

| File | Purpose |
|------|---------|
| `docs/marketing/pricing_strategy.md` | Full pricing strategy with Stripe Product/Price IDs |
| `docs/business_plan/` (directory) | Contains all HTML files + assets |

## Key Data Points (keep updated)

- **Founder**: Victor Sol&eacute; (always with accent)
- **Company**: Beresol BV (Belgian entity)
- **North Star Metric**: WAPU (Weekly Active Paid Users)
- **WAPU targets**: 10 (Month 3), 25 (Month 6), 50 (Month 12)
- **Pricing**: Starter 39/mo, Advocate 59/mo, Professional 99/mo, EP Plan 49/mo
- **Knowledge base**: 58+ guides, 400+ keyword triggers, 35 organigrammes, 15+ data scrapers
- **AI stack**: Mistral Small (primary) + Claude Haiku 4.5 (knowledge queries) + GPT-4/Gemini fallbacks
- **Main competitor**: Spaak (Danish, VC-backed, 100+ PA teams, distribution-led)
- **Brubru advantage**: Feature depth (Amendator, Predictions, EU Law Comply, Tenderator, Document Generator)

## How to Update

1. Edit the HTML file directly (they are self-contained, no build step)
2. Ensure the `.bp-nav` links are consistent across all 4 files
3. After changes, push to main -- GitHub Pages auto-deploys
4. For the main business plan, also update the PDF export if content changed significantly
5. Always use `Sol&eacute;` in HTML for the founder's name
