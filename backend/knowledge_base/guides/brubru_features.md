# Brubru Features & Data Sources

## QUICK FACTS
- Topic: Brubru platform features and EU institutional data sources
- Data sources: OEIL (Legislative Observatory), EUR-Lex (Official Journal), Legislative Train Schedule, EPRS (Research Service)
- Key features: My EU Bubble (the cockpit, 25 sub-tabs), Amendator (amendment editor with Akoma Ntoso XML), Chat, EU Law Comply, Tenderator, API
- For what each product and sub-tab does, see brubru_product_tour and brubru_meub_subtabs; this guide covers the data sources behind them
- Procedure reference format: YYYY/NNNN(XXX) -- e.g. 2024/0176(COD)
- CELEX format: SYYYY[T]NNNN -- e.g. 32024R1689 (AI Act)
- Common procedure types: COD (ordinary legislative), CNS (consultation), APP (consent), INI (own-initiative), RSP (resolution), BUD (budgetary)
- Sync frequency: Daily automatic updates; Professional tier can trigger manual syncs
- Monitoring tip: Track 5-10 key files strategically rather than dozens
- Sub-tabs in My Tracked Files: Legislative Train, Committee Work, Texts Adopted, Commission Docs

Brubru automatically syncs data from official EU sources to help you track legislation, draft amendments, and stay informed about EU policy developments.

## Data Sources

Brubru pulls data from these official EU institutional sources:

### OEIL (Legislative Observatory)

The European Parliament's procedure database. Brubru syncs:

- **Latest procedures** - New legislative files (COD, CNS, INI, RSP, DEA, BUD)
- **Commission documents** - COM and SWD proposals
- **Committee reports** - Reports tabled by EP committees

**What you get:**
- Procedure reference (e.g., 2024/0176(COD))
- Title and status
- Lead committee assignment
- Rapporteur and shadow rapporteurs
- Key events timeline
- Upcoming forecasts (votes, trilogues)
- Links to all related documents

**Sync frequency:** Daily automatic updates, or trigger manually in My EU Bubble.

### EUR-Lex

The Official Journal of the European Union. Brubru syncs:

- **Parliament & Council legislation** - Adopted regulations, directives, decisions
- **Commission proposals** - Legislative proposals with CELEX numbers
- **Official Journal entries** - L series (legislation) and C series (information)

**What you get:**
- CELEX numbers for precise document identification
- Document type classification (Regulation, Directive, Decision)
- Direct links to EUR-Lex for full text access
- Document relationships (amendments, repeals, implementations)

### Legislative Train Schedule

The European Commission's priority tracker for the 2024-2029 term. Shows:

- 7 EC priority "trains" with legislative files
- Status tracking: Announced, Tabled, Blocked, Close to Adoption, Adopted, Withdrawn
- Package groupings by policy area
- Cross-references to OEIL and EUR-Lex

### EPRS (European Parliament Research Service)

Think tank briefings and research. Brubru matches:

- "EU Legislation in Progress" explainer briefings to your tracked files
- "At a Glance" summaries
- In-depth studies and analyses

## My EU Bubble Features

### Legislative Trains Tab

Browse all legislative files from the Commission's priorities:

- Filter by status (Announced, Tabled, Adopted, etc.)
- Filter by committee (LIBE, ITRE, ENVI, etc.)
- Search by title or procedure reference
- Click any file for full details

### My Tracked Files Tab

Your personal watchlist of legislative files:

- Track any procedure from OEIL, EUR-Lex, or Legislative Train
- See status changes at a glance
- View your amendments linked to each file
- Load tracked files directly into Amendator

### Legislative Updates Widget

Real-time updates on your tracked files:

- Status changes (e.g., file moved from Tabled to Close to Adoption)
- New documents published
- Upcoming votes and deadlines
- Committee meeting announcements

## Amendator Features

### Load from Tracked Files

Open Amendator and select from your tracked files:

1. Click "Load from Tracked Files"
2. Select a legislative file
3. Brubru fetches the EUR-Lex document using CELEX numbers
4. Start drafting amendments immediately

### Legislative Context Banner

When working on a tracked file, see:

- Current status in the legislative process
- Lead committee and rapporteur
- Upcoming deadlines
- Link to OEIL for full procedure details

### AI-Assisted Drafting

The AI assistant knows about:

- The specific legislative file you're working on
- Related EU legislation and policy context
- Amendment drafting conventions
- EP Rules of Procedure requirements

## How to Track a Legislative File

### From My EU Bubble

1. Go to My EU Bubble > Legislative Trains
2. Find the file you want to track
3. Click the "Track" button
4. The file appears in your "My Tracked Files" tab

### From OEIL (any procedure)

1. Go to My EU Bubble > My Tracked Files
2. Click "Add from OEIL"
3. Enter the procedure reference (e.g., 2024/0176(COD))
4. Brubru fetches full details and adds it to your list

### Automatic Sync

Brubru automatically syncs new procedures from OEIL and EUR-Lex:

- New legislative procedures added daily
- Status updates when files progress
- New documents linked as they're published

Blue tier subscribers can trigger manual syncs for immediate updates.

## Understanding Procedure References

### OEIL Format

Format: `YYYY/NNNN(XXX)`

- YYYY = Year
- NNNN = Sequence number
- XXX = Procedure type

**Common types:**
- COD = Ordinary legislative procedure (codecision)
- CNS = Consultation procedure
- APP = Consent procedure
- INI = Own-initiative report
- RSP = Resolution
- BUD = Budgetary procedure

**Example:** `2024/0176(COD)` = Ordinary legislative procedure started in 2024

### CELEX Format

Format: `SYYYY[T]NNNN`

- S = Sector (3 = legislation, 5 = preparatory acts)
- YYYY = Year
- T = Type (R = Regulation, L = Directive, D = Decision, PC = Proposal)
- NNNN = Number

**Examples:**
- `32024R1689` = Regulation 1689 of 2024 (AI Act)
- `52024PC0176` = Commission proposal 176 of 2024

## Tips for Effective Monitoring

1. **Track strategically** - Focus on 5-10 key files rather than dozens
2. **Check daily** - Use the Legislative Updates widget for quick scans
3. **Set up notifications** - Enable alerts for status changes on critical files
4. **Use Amendator integration** - Draft amendments directly from tracked files
5. **Ask Brubru** - The chat assistant knows about your tracked files and can help you understand developments

## Asking Brubru About Legislation

The Brubru chatbot can answer questions about legislative files in the database. Try asking:

**Recent legislation:**
- "What new legislation was added this week?"
- "Show me the latest EU procedures"
- "What recent updates are there?"

**Source-specific queries:**
- "What files came from OEIL?"
- "Show me EUR-Lex legislation"
- "What's in the Legislative Observatory?"

**Topic searches:**
- "Find legislation about digital markets"
- "What's happening with the AI Act?"
- "Show me environmental directives"

**Status queries:**
- "Which files are blocked?"
- "What legislation is close to adoption?"
- "Show me tabled proposals"

The chatbot will show:
- File title and current status
- Source (Legislative Train, OEIL, or EUR-Lex)
- OEIL procedure reference (e.g., 2024/0176(COD))
- CELEX numbers for EUR-Lex documents
- Lead committee assignment
- When the file was added to Brubru

## Data Quality Notes

- OEIL data is official and authoritative for EP procedures
- EUR-Lex provides the definitive legal text
- Legislative Train reflects Commission priorities (not all EU procedures)
- EPRS briefings are matched by title similarity (verify matches manually)
- Sync happens daily; for breaking developments, check official sources directly
