# EU Interinstitutional Style Guide -- the binding drafting rulebook

## QUICK FACTS
- Topic: EU Interinstitutional Style Guide -- binding drafting and formatting standard for all EU institutions
- Publisher: Publications Office of the European Union
- Official URL: https://style-guide.europa.eu/
- English section: https://style-guide.europa.eu/en/home
- Coverage: 24 official EU languages (one language-specific chapter per language)
- Maintained by: Interinstitutional Style Committee (Publications Office + representatives of all major institutions)
- Binding for: European Commission, European Parliament, Council of the EU, Court of Justice, and all other EU bodies producing official publications and legal acts
- Structure: Four numbered Parts + Annexes (Part One: Official Journal; Part Two: General Publications; Part Three: Conventions common to all languages; Part Four: Language-specific conventions; Annexes)
- Citation rule (critical): Regulation (EU) 2024/1689 -- EU identifier in parentheses before the year/number; NEVER "Regulation 2024/1689/EU"
- Date format in English: DD Month YYYY with no ordinal suffix and no comma (example: 13 June 2024)
- Currency in legal texts: EUR (spelled out), not the symbol alone; € symbol is permitted in general publications
- Member State order in English texts: alphabetical by English name; in French texts: French alphabetical order; protocol order applies specifically to rotating Council Presidency listings
- Catalan (CA): not an official EU language, so no CA chapter exists; Brubru follows Softcatala terminology and EUR-Lex CA translation conventions as the nearest approximation
- Periodic updates: issued by the Publications Office; institutions must implement immediately on publication

The EU Interinstitutional Style Guide is the single authoritative reference for how EU institutions write, format, and cite documents. Brubru applies it to every brief, deep-dive, slide, email, and daily brief it produces. Non-compliance in a Brubru output is a quality defect, not a style choice.

See also: `finding_and_citing_eu_law.md`, `celex_number_format.md`, `eli_european_legislation_identifier.md`, `official_journal_explained.md`, `multilingual_content_law.md`

---

## What the Style Guide is and why it is binding

The EU Interinstitutional Style Guide (often abbreviated IISG) is the house-style manual agreed between all major EU institutions for producing official texts, legal acts, and publications. It was originally developed by the Publications Office and is updated through the Interinstitutional Style Committee, which brings together editors and terminologists from the Commission, Parliament, Council, Court of Justice, Court of Auditors, and other bodies.

The guide is "interinstitutional" in the most literal sense: each institution formally adopted it as its internal standard. A Commission regulation, a Parliament legislative resolution, a Council implementing decision, and a European Central Bank opinion must all follow the same citation formats, the same date conventions, and the same typographic rules for the official language versions. This creates consistency across the Official Journal, which publishes all binding EU law.

For Brubru, the IISG has a second, practical significance. Brubru ships content in six languages (EN, FR, NL, ES, CA, IT). When Brubru cites a regulation, writes a date, quotes an institutional name, or lists Member States, it must match what the institutions themselves would write. Deviation signals to professional users -- MEP assistants, Commission officials, policy consultants -- that Brubru is not a serious research tool. Compliance is therefore a product-quality requirement, not an optional editorial preference.

---

## Structure of the Style Guide

The guide is divided into four numbered Parts and a set of Annexes.

**Part One -- Official Journal**
Covers the structure of legal acts published in the OJ, including titles, headings, recitals, articles, annexes, and footnotes within acts. It specifies how preambles are formatted, how enacting terms are worded ("THE EUROPEAN PARLIAMENT AND THE COUNCIL OF THE EUROPEAN UNION,"), and how citations within a legal act refer to prior legislation. This part is most relevant to Brubru's Amendator feature and to any Brubru output that reproduces or quotes from a legal act.

**Part Two -- General Publications**
Covers documents other than legal acts: reports, studies, working papers, communication documents, and publications produced by the institutions. It addresses document identifiers (ISBN, ISSN, DOI), cover formatting, copyright pages, and bibliographic references. Relevant to Brubru deep-dives and position-paper templates.

**Part Three -- Conventions Common to All Languages**
The most universally applicable part. It covers:
- Abbreviations and symbols (including currency symbols and country codes)
- Typographic conventions (quotation marks, spacing, use of capitals)
- Numbers, dates, and times
- Country names, language names, and currency names (the standard lists for EU-27)
- Ordering of Member State names (protocol order for formal listings)
- References to EU legal acts (the citation format rules critical for Brubru)

**Part Four -- Language-specific conventions**
One chapter per official EU language (currently 24). Each chapter gives the house rules for that language: spelling conventions, punctuation anomalies, capitalisation standards, use of hyphens, and any rules that diverge from general typographic practice in that language. For example, the English chapter mandates British spelling throughout (analyse not analyze, colour not color, behaviour not behavior); the French chapter addresses the use of "français inclusif" for new acts; the Dutch chapter governs spacing and hyphenation for compound words.

**Annexes**
Reference tables: country codes (ISO 3166-1 alpha-2 used by the EU), currency codes (ISO 4217), language codes, official names of EU institutions in all 24 languages, and abbreviations for legislative procedure identifiers.

---

## Key rules Brubru applies

### Citing EU legal acts

The single most frequently misapplied rule is the citation format for EU acts. The correct form places the EU identifier (or EURATOM, CFSP, etc.) in parentheses immediately after the instrument type and before the year/number pair:

Correct: Regulation (EU) 2024/1689
Correct: Directive (EU) 2022/2555
Correct: Decision (EU, Euratom) 2021/1163
Incorrect: Regulation 2024/1689/EU
Incorrect: EU Regulation 2024/1689
Incorrect: Regulation EU 2024/1689

On first mention in a document, the full title is used:
"Regulation (EU) 2024/1689 of the European Parliament and of the Council of 13 June 2024 laying down harmonised rules on artificial intelligence"

On subsequent mentions, a short form is acceptable:
"Regulation (EU) 2024/1689" or the established acronym in parentheses, for example "the AI Act" if introduced at first mention.

Council regulations adopted before the Lisbon Treaty (in force 1 December 2009) carry no EU/EC/EEC identifier in the same position; they use older formats such as "Council Regulation (EC) No 1/2003" (note: "No" before the number, pre-Lisbon style). Post-Lisbon acts drop "No" entirely.

For the machine-readable CELEX identifier that underlies every EU act, see `celex_number_format.md`. For the ELI permalink format used on EUR-Lex, see `eli_european_legislation_identifier.md`.

### Date format

In English-language EU texts, dates follow the form: day (numeral) + month (written out in full) + year (four digits). No ordinal suffix; no comma between month and year.

Correct: 13 June 2024
Correct: 1 January 2025
Incorrect: 13th June 2024
Incorrect: June 13, 2024
Incorrect: 13/06/2024 (acceptable only in tables and data fields, never in running text)

In French texts: "13 juin 2024" (lower-case month name, which is the French convention; the IISG overrides any tendency to capitalise month names in French running text).

In Spanish texts: "13 de junio de 2024" (day + de + month lower-case + de + year).

In Italian texts: "13 giugno 2024".

In Dutch texts: "13 juni 2024".

Brubru applies the English date format across all EN-language outputs regardless of the national conventions of the subject matter being discussed.

### Currency format

In legal texts and formal publications: use the ISO 4217 code EUR in tables and financial figures, not the € symbol alone. Running text in general publications may use the symbol.

Correct in a legal act: "an amount of EUR 50 000" (note: EU convention uses a space as the thousands separator, not a comma; this applies across all EU languages)
Correct in a brief: "EUR 50 000" or "50,000 euros" (the latter in less formal contexts)
Incorrect: "€50,000" as the sole form in a formal Brubru deep-dive table
Incorrect: "50.000 EUR" (the full stop as a thousands separator is the continental European convention, not the EU's own standard in English)

### Protocol order and Member State names

"Protocol order" refers to the rotation sequence of the Council Presidency (fixed six-monthly cycle). Separately, the IISG specifies how to list all EU-27 Member States in formal texts: in English-language documents, Member States are listed alphabetically by their English name.

Current EU-27 in English alphabetical order:
Belgium, Bulgaria, Croatia, Czechia (not Czech Republic in EU texts post-2016), Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, the Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden.

Note: "Czechia" is the official short-form English name as recognised by the Publications Office since 2016. "Czech Republic" is still found in older texts but should not be used in new Brubru outputs.

In French texts: the order is French alphabetical. In formal Council documents the French alphabetical order is traditionally used for institutional reasons related to the Treaties being authenticated in French.

---

## Language-specific anomalies relevant to Brubru

**English (EN)**
The IISG mandates British English throughout. The Publications Office's house rules follow UK conventions: "-ise" not "-ize" (organise, harmonise, analyse), "colour" not "color", "behaviour" not "behavior". Quotation marks use single marks for the first level in running text and double for quotations within quotations. The IISG also mandates the serial comma (the Oxford comma) in lists of three or more items in English EU texts: "the Parliament, the Council, and the Commission".

**French (FR)**
The IISG French chapter addresses the use of "français inclusif" (gender-neutral inclusive writing) in new official acts, specifically adopting a specific set of rules agreed by the institutions for how to handle gender in French legal language. Brubru applies standard formal French for its EU brief and deep-dive outputs and avoids gender-neutral neologisms that have not been formally adopted in the language versions of EU legislation, as those would read as non-institutional.

**Dutch (NL)**
Dutch EU texts follow the "Groene Boekje" (the authoritative Dutch spelling reference) as supplemented by the IISG NL chapter. Compound words and hyphenation in Dutch differ from general Dutch journalistic practice; the institutional form is more conservative. Brubru uses standard formal NL.

**Spanish (ES)**
The IISG ES chapter follows the Real Academia Española conventions with specific institutional overrides for EU terminology. Currency and number formatting in Spanish EU texts matches the EU standard (space as thousands separator) rather than the Spanish typographic convention (full stop as thousands separator).

**Italian (IT)**
Standard formal Italian with EU institutional overrides. No ordinal suffixes in dates.

**Catalan (CA)**
Catalan is not an official EU language and therefore has no chapter in the IISG. Brubru's Catalan outputs draw on three sources: (1) the Softcatala NMT glossary and terminology for EU texts; (2) EUR-Lex's unofficial Catalan translations, which follow the terminology of the Generalitat de Catalunya's TERMCAT database; (3) Brubru's own Catalan style rules documented in `memory/catalan_translation.md`. For date formatting, Brubru uses the Catalan convention: "13 de juny de 2024". For currency, "EUR" is used in formal contexts and "euros" in running text, following Spanish-language EU practice as the closest institutional model. Catalan output must carry accents: sóc, perquè, política, Brussel·les, regulació.

---

## How Brubru applies the Style Guide

Brubru surfaces the IISG in three ways.

**Content generation.** When the Brubru document generator or AI chat produces text that cites EU acts, writes dates, lists Member States, or formats financial figures, it applies the rules above. The system prompt for the Brubru chat AI explicitly instructs it to follow EU citation format. Any output that reads "Regulation 2024/1689/EU" or "June 13th, 2024" or lists Member States in non-standard order is a regression.

**Deep-dives and briefs.** Every Brubru deep-dive, daily brief, and LinkedIn post is reviewed against the citation rules before publication. The `/daily-brief` workflow includes a copy-check step specifically for institutional codes and citation format. The rule "no institutional codes in hero text" (plain-language aliases such as 'AI Act' rather than the CELEX number or the full citation in a headline) is a complementary constraint, not a contradiction of IISG: the IISG governs formal citation in document body text; Brubru's marketing rule governs what appears in subject lines and slide titles for a non-specialist audience.

**Amendator.** The Amendator feature works directly with legislative text formatted in Akoma Ntoso XML, the machine-readable standard for EU legislative acts. IISG Part One governs the textual conventions inside those acts; Akoma Ntoso governs the XML structure. When Brubru proposes an amendment, the amended text must follow IISG Part One formatting for the relevant article, paragraph, or recital being changed.

---

## Key resources

| Resource | URL | What it covers |
|----------|-----|----------------|
| IISG homepage | https://style-guide.europa.eu/ | Full guide, all 24 languages, search function |
| IISG English section | https://style-guide.europa.eu/en/home | Part Four (EN) and Parts One through Three in English navigation |
| Publications Office | https://op.europa.eu/ | Publisher; source of updates and errata |
| EUR-Lex legal acts | https://eur-lex.europa.eu/ | Acts formatted under IISG Part One (see also `finding_and_citing_eu_law.md`) |
| ELI permalink structure | See `eli_european_legislation_identifier.md` | Machine-readable act references |
| CELEX numbering | See `celex_number_format.md` | Unique act identifiers in the Cellar database |
| Official Journal explained | See `official_journal_explained.md` | Where IISG-formatted acts are published |
| Multilingual content law | See `multilingual_content_law.md` | Legal basis for 24-language equal authenticity |
