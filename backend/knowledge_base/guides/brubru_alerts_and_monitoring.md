# Brubru Alerts and Standing Monitoring: what exists, what does not

## QUICK FACTS
- Two mechanisms: **tracked files** (user picks the file) and **saved-search alerts** (user picks the words)
- Saved-search alerts: `user_alert_subscriptions`, managed via `/api/alerts/subscriptions`
- **Scopes that scan today (4): `eu_laws`, `texts_adopted`, `legislative_carriages`, `rss_entries`**
- **Scopes accepted but NOT scanned (3): `mep_amendments`, `parliamentary_questions`, `ep_resolutions`**
- **Delivery is in-product only.** The `delivery` field takes exactly `["chat_greeting", "meub_tile"]` -- there is no `"in-product"` value and no email value. Matches appear as a Chat greeting line, a My EU Bubble tile and the notification bell. **NO EMAIL.**
- **NOTHING RUNS ON A TIMER.** An alert scans only when somebody triggers it via `POST /api/alerts/run-now`. That endpoint is rate-limited to one call per minute; **that is a ceiling on manual calls, NOT a scanning frequency**. Never say alerts scan every minute, hourly or daily
- **No self-serve screen** to create a subscription yet: via the API, or the Brubru team sets it up
- Tracked files DO have a full UI: My Tracked Files (Els meus expedients en seguiment)
- Amendator DRAFTS and exports amendments; it CANNOT file or submit one to the Parliament
- News is a feed; it does NOT generate or export a report or PDF
- Chat cannot create a subscription, track a file or set an alert -- it says where the user clicks
- Council Regulation 1/1958 (EU language regime, Art. 342 TFEU, Council unanimity): **no procedure file exists**; it moves in the General Affairs Council, so watch My EU Calendar
- Never promise an email alert, an automatic sweep, or an amendment-level alert
- Never invent an illustrative procedure reference or a "suppose that" example with a made-up date
- Name all four working scopes, not just one

## The two mechanisms

**Tracked files -- "I know which file I care about."** The user adds specific procedures, Commission
documents, committee work, consultations or adopted texts to **My Tracked Files (My EU Bubble)**.
Use when the user names a file, dossier or procedure reference.

**Saved-search alerts -- "I do not know which file it will be yet."** The user gives a *phrase* and
Brubru scans the corpus for new matching rows. This is the right mechanism when the user watches for
a topic to *appear* somewhere it does not yet exist. Fields: `label`, `query_phrase` (`OR` supported),
`scopes`, `delivery`, `exclude_terms`, `language_codes`.

## Scopes: state this accurately, never guess

| Scope | Scans today | Covers |
|---|---|---|
| `eu_laws` | **Yes** | Adopted EU legislation |
| `texts_adopted` | **Yes** | EP texts adopted |
| `legislative_carriages` | **Yes** | Live procedure files |
| `rss_entries` | **Yes** | Institutional news feeds |
| `mep_amendments` | **No** | Accepted on the subscription, skipped by the runner |
| `parliamentary_questions` | **No** | Accepted on the subscription, skipped by the runner |
| `ep_resolutions` | **No** | Accepted on the subscription, skipped by the runner |

A user asking to be told when an MEP tables an amendment on their topic is asking for
`mep_amendments`, which is **not delivered**. Say so plainly, then offer the closest working thing --
a `legislative_carriages` alert on the same phrase, which catches the file moving even though it
misses the individual amendment -- and let the user decide.

## What Brubru cannot do (say so rather than improvise)

- Cannot send email alerts, reminders or digests.
- Cannot run a subscription on a schedule without someone triggering it.
- Cannot alert on an individual MEP amendment, parliamentary question or EP resolution.
- **Amendator cannot file or submit an amendment.** It drafts, edits and exports Akoma Ntoso XML;
  tabling is done by an MEP or political group through EP channels.
- **News does not generate or export a report or PDF.** It is a feed.
- Chat cannot act on the workspace. Never say "I have set this up for you".

## Answering a "monitor this for me" question well

1. Separate the two mechanisms and say which fits. Do not send a topic-watch to My Tracked Files.
2. Name the working scopes, and name the missing ones when the use case depends on them.
3. Do not invent the set-up path: there is no self-serve alert screen yet.
4. **Do not state a meeting date that is not in the retrieved calendar context.** Name the body or
   Council configuration and point at My EU Calendar instead.
5. **Check the file is trackable before telling the user to track it.** If Brubru holds no procedure
   file, say so and give the surface that does carry it.
6. In a non-English answer, use the localised tab names (Catalan: Els meus expedients en seguiment,
   El meu calendari UE, Actualitat, Interessos Polítics).

## Worked case: watching for language provisions

A user watching whether EU files acquire a linguistic-diversity dimension is a **saved-search** case,
not a tracked-file case: the files they care about mostly have no language content *yet*.

- **Works today:** a `legislative_carriages` + `texts_adopted` + `eu_laws` + `rss_entries` alert on a
  phrase such as `linguistic diversity OR minority languages OR regional languages OR ECRML`, plus
  tracked files on the specific media, education and equality dossiers.
- **Does not work today:** the amendment-level signal (`mep_amendments`) -- exactly the "an MEP tabled
  a language amendment" case. Be explicit that this is the gap.
- **Council Regulation 1/1958** -- the EU language regime, amendable only by unanimity in Council
  under Article 342 TFEU. The pending request to add Catalan, Basque and Galician has **not entered
  the legislative pipeline as a Commission proposal**, so Brubru holds **no procedure file** for it and
  it cannot be added to My Tracked Files. It is taken in the **General Affairs Council**, so the
  surface that carries it is **My EU Calendar**. Do not invent a procedure reference for it, and do
  not state a GAC date that was not retrieved.
- Files that DO exist and can be tracked: the Audiovisual Media Services Directive and its review,
  the European Media Freedom Act, Erasmus+ 2028-2034, and the equality and anti-racism dossiers.

## Related guides

| Guide | Why |
|---|---|
| `brubru_product_tour` | What each product does; Chat cannot write to the workspace |
| `brubru_meub_subtabs` | The 25 canonical sub-tab names, including the localised ones |
| `brubru_features` | The data sources behind the tabs |
| `monitoring_tips` | General EU monitoring methodology (non-Brubru tooling) |
