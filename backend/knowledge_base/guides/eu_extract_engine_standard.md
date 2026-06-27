# Brubru EU Extract Standard: Issues & Fixes for the EU Web Estate

## QUICK FACTS
- What it is: Brubru's field-tested standard for extracting structured data from the EU institutional web estate, plus the catalogue of issues we hit and the fixes we shipped.
- Scope of the analysis: 8,544 distinct EU URLs mined from Brubru's API source docs, across 232 domains.
- Platform types (8): ECL (Europa Component Library), Drupal/OpenEuropa, WordPress, Microsoft Power Pages/Dynamics, Jalios JCMS, SharePoint, SPA+search-backend, bespoke.
- Anti-bot walls (7): JS-WAF, Anubis proof-of-work, Cloudflare cooldown, 403/UA blocks, cookie handshakes, broken-TLS, JS-faceted search.
- Estate reachability: 87% return HTTP 200; Drupal (4,068) + ECL (2,808) are ~80% of the estate.
- Headline quality results after fixes: 0 mojibake titles estate-wide, near-zero junk titles, server-rendered date coverage solid (many pages 0%->100%).
- The 5-datapoint contract every item must carry: public_url, body_txt, body_html, document_date, creation_date (plus title, summary, source_kind).
- Engine code: backend/services/extract/ (classifier, fetcher, handlers, article, engine) + backend/services/classify/ (eurovoc_classifier). Endpoint: GET /api/v2/extract.
- Full developer reference: docs/api/extract_engine_issues.md.

## Overview

Brubru runs ONE config-driven "extract engine": give it any EU institutional listing URL
(news, events, publications) and it returns clean, structured, EuroVoc-tagged items,
whichever of the 8 platforms the page is built on. This guide is the practical companion
to that engine: it explains how the EU estate is built, the problems extraction hits in
the real world, and how each was fixed. It exists so the engine's behaviour is
explainable and so the lessons are reusable (the "Brubru scraper standard").

## Platform taxonomy: what you are fetching

The EU estate runs on a small number of platforms. Recognising which one a page uses is
half the battle, because each has a known card structure and fetch strategy:

- ECL (Europa Component Library): the DG sites under *.ec.europa.eu. Cards are
  `.ecl-content-item`; usually fetchable with a plain HTTP request.
- Drupal / OpenEuropa: most agencies (EMA, ECHA, EASA, ACER). Cards are `.views-row`,
  `.node`, `.field--name-*`. Mostly requests; some need a browser.
- WordPress: the Joint Undertakings (Fusion for Energy, rail, clean hydrogen). `article`
  elements; requests.
- Microsoft Power Pages / Dynamics: chips-ju and some JUs. A JavaScript data-grid
  (`powerappsportal`, `xrm-attribute-value`) that renders ~12s after load; needs a
  browser with a render-settle wait.
- Jalios JCMS: the Court of Justice (curia). `/jcms/` paths; browser.
- SharePoint: the Court of Auditors (ECA); browser.
- SPA + search backend: EUIPO, EUR-Lex search. An empty shell filled by XHR; browser.
- Bespoke: a long tail handled by a generic content-anchor fallback.

## Anti-bot walls

The fetcher escalates: plain request -> headless browser -> cooldown retry, with
TLS-relaxed and render-settle modes. Genuinely hard walls remain (EUDA 403, FRA Anubis
proof-of-work), which Brubru does not try to defeat.

## Issues & fixes (the catalogue)

- Mojibake ("Europeâ€™s"): plain requests defaulted an undeclared charset to Latin-1, but
  EU pages are UTF-8. Fixed by honouring the page's real encoding. Result: 0 mojibake
  across the whole estate.
- Navigation / CTA junk as items ("Subscribe", "Read more", "Registration"): a central
  junk-title filter now runs at every item-build site.
- Proper-noun / acronym pollution in subject tags ("Chips JU" -> "jute"): a confidence
  gate keeps a tag only when several top matches agree on a EuroVoc domain or the score
  margin is clear. No tags beats wrong tags.
- Organisation / treaty NAMES as subjects ("Pacific Islands Forum", "EAEC Treaty"):
  filtered out using EuroVoc's own domain structure (the organisations and institutions
  microthesauri), while keeping geography and legal subjects.
- Power Pages returns nothing: the data-grid renders seconds late; a render-settle wait
  (poll until content stops growing and no spinner shows) plus a permissive card reader
  for its heading+"Click here" layout recover the items (chips-ju Publications 0 -> 6).
- Thin-title classification: a listing title is too little signal, so an opt-in deep mode
  fetches each article's detail page and tags on the full body.
- Dates near-zero: the date parser missed ordinals ("24th June"), US order and numeric
  formats; rewritten to handle all of them, preferring real date elements. For sites that
  only show the date on the article page (eige, easa), an opt-in date-completion fetches
  the detail page to recover it (eige 0% -> 88%, easa 0% -> 100%).
- Forms extracted as items: filter/search forms and date-pickers are stripped before
  card selection.

## Residual limitations (honest)

- Hard anti-bot walls (EUDA, FRA) stay blocked.
- A few EU bodies (EUISS, "Conference on Disarmament") are filed by EuroVoc under topic
  domains, so they can survive the organisation-name filter on security/defence text.
- A small class of fully-JS sites (enisa) hide the date in a non-machine-extractable form
  (relative or image), unrecoverable even when rendered.

## How to answer user questions with this guide

- If asked "can Brubru scrape <EU site>?": identify the platform from the taxonomy above,
  state the fetch strategy, and note any anti-bot wall.
- If asked about data quality (dates, encoding, duplicate or junk items): cite the
  relevant issue and its fix; be honest about the residual limitations.
- If asked about the methodology: the engine is tested against golden URLs per platform
  and an estate-wide concurrent scan; every new bug becomes a regression fixture.
- Never claim the engine defeats anti-bot walls it does not (EUDA, FRA).
