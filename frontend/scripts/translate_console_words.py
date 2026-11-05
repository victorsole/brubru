#!/usr/bin/env python3.12
"""Translate what the API Console shows about each route into its five other languages.

The route's summary, its first sentence and its full description are written in English on the API. This writes, per
language, frontend/public/api/console_words/<lang>.json (summary and first sentence, read when the page opens) and
<lang>_full.json (the full description, read when a person opens "About this route"). Each route carries a key made from the
English text: when a description changes the key no longer matches and the console shows English for that route until this
is run again, so a stale translation is never shown as current.

Every segment passes a gate against its source: code, numbers, addresses and Markdown must all survive, the text must have
stopped being English, and the EU's official terms must be used. A segment that fails is retried, then left out, and that
route stays in English: the run says how many.

    python3.12 frontend/scripts/translate_console_words.py --lang ca --limit 10 --dry-run --sample 10
    python3.12 frontend/scripts/translate_console_words.py --part short --apply
    python3.12 frontend/scripts/translate_console_words.py --part full --apply

Runs on Groq's free tier (8,000 tokens a minute, a daily limit per model), so the long descriptions can take days. A run stops
cleanly when both models have used up the day, keeps what it has, and the next run carries on: only text not yet translated is
sent. Routes not finished stay in English, and the console says so.
"""
import argparse, collections, json, os, pathlib, random, re, ssl, sys, time, urllib.error, urllib.request

import certifi

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend/public/api/console_words"
SPEC = "https://brubru-production.up.railway.app/api/v2/openapi.json"
MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b"]
CTX = ssl.create_default_context(cafile=certifi.where())
MEMORY = pathlib.Path.home() / ".brubru_tools/console_words_memory"
BATCH_CHARS = 2600
LANGS = {
    "fr": {
        "name": "French", "you": "vous",
        "heads": {"What it does": "Ce que cela fait", "When to use it": "Quand l'utiliser", "Input": "Paramètres", "Try it": "Essayer", "You get back": "Ce que vous obtenez", "Data freshness": "Fraîcheur des données"},
        "terms": "this body publishes = que cet organe publie; integer id = identifiant numérique; European Commission = Commission européenne; European Parliament = Parlement européen; European Council = Conseil européen; Council of the European Union = Conseil de l'Union européenne; Council of the EU = Conseil de l'UE; Court of Justice of the European Union = Cour de justice de l'Union européenne; European Central Bank = Banque centrale européenne; European Court of Auditors = Cour des comptes européenne; European Investment Bank = Banque européenne d'investissement; European Ombudsman = Médiateur européen; European Committee of the Regions = Comité européen des régions; European Economic and Social Committee = Comité économique et social européen; Publications Office = Office des publications; Eurogroup = Eurogroupe; body of a document, body text, full body = texte intégral (never corps); an EU body = un organe; scraping = extraction de données; feed = flux; to call the API, a call = appeler, un appel; delegated act = acte délégué; implementing act = acte d'exécution; Official Journal = Journal officiel; Court of Justice = Cour de justice; rapporteur = rapporteur; tender = marché public; call for proposals = appel à propositions; infringement = infraction; endpoint = route; item = élément",
        "bad": r"\bcorps\b(?! europ)|actes? d'impl[ée]mentation|point de terminaison", "stop": {"le", "la", "les", "des", "du", "une", "et", "pour", "dans", "sur", "avec"},
    },
    "nl": {
        "name": "Dutch", "you": "u",
        "heads": {"What it does": "Wat het doet", "When to use it": "Wanneer te gebruiken", "Input": "Invoer", "Try it": "Probeer het", "You get back": "Wat u terugkrijgt", "Data freshness": "Actualiteit van de gegevens"},
        "terms": "this body publishes = die dit orgaan publiceert; integer id = numeriek id; European Commission = Europese Commissie; European Parliament = Europees Parlement; European Council = Europese Raad; Council of the European Union = Raad van de Europese Unie; Council of the EU = Raad van de EU; Court of Justice of the European Union = Hof van Justitie van de Europese Unie; European Central Bank = Europese Centrale Bank; European Court of Auditors = Europese Rekenkamer; European Investment Bank = Europese Investeringsbank; European Ombudsman = Europese Ombudsman; European Committee of the Regions = Europees Comité van de Regio's; European Economic and Social Committee = Europees Economisch en Sociaal Comité; Publications Office = Publicatiebureau; Eurogroup = Eurogroep; body of a document, body text, full body = volledige tekst (never lichaam); an EU body = een orgaan; scraping = gegevens ophalen; feed = feed; to call the API, a call = aanroepen, een aanroep; delegated act = gedelegeerde handeling; implementing act = uitvoeringshandeling; Official Journal = Publicatieblad; Court of Justice = Hof van Justitie; rapporteur = rapporteur; tender = aanbesteding; call for proposals = oproep tot het indienen van voorstellen; infringement = inbreuk; endpoint = route; item = item",
        "bad": r"\blichaam\b|implementatiehandeling|eindpunt", "stop": {"de", "het", "een", "en", "van", "voor", "met", "op", "in", "aan"},
    },
    "es": {
        "name": "Spanish", "you": "tú",
        "heads": {"What it does": "Qué hace", "When to use it": "Cuándo usarlo", "Input": "Parámetros", "Try it": "Pruébalo", "You get back": "Qué obtienes", "Data freshness": "Actualidad de los datos"},
        "terms": "this body publishes = que publica este organismo; integer id = identificador numérico; European Commission = Comisión Europea; European Parliament = Parlamento Europeo; European Council = Consejo Europeo; Council of the European Union = Consejo de la Unión Europea; Council of the EU = Consejo de la UE; Court of Justice of the European Union = Tribunal de Justicia de la Unión Europea; European Central Bank = Banco Central Europeo; European Court of Auditors = Tribunal de Cuentas Europeo; European Investment Bank = Banco Europeo de Inversiones; European Ombudsman = Defensor del Pueblo Europeo; European Committee of the Regions = Comité Europeo de las Regiones; European Economic and Social Committee = Comité Económico y Social Europeo; Publications Office = Oficina de Publicaciones; Eurogroup = Eurogrupo; body of a document, body text, full body = texto completo (never cuerpo); an EU body = un organismo; scraping = extraer datos; feed = canal; to call the API, a call = llamar, una llamada; delegated act = acto delegado; implementing act = acto de ejecución; Official Journal = Diario Oficial; Court of Justice = Tribunal de Justicia; rapporteur = ponente; tender = licitación; call for proposals = convocatoria de propuestas; infringement = infracción; endpoint = ruta; item = elemento",
        "bad": r"\bcuerpos?\b(?! europeo)|actos? de implementaci[óo]n|punto final", "stop": {"el", "la", "los", "las", "de", "del", "una", "un", "y", "para", "con", "en"},
    },
    "ca": {
        "name": "Catalan", "you": "tu",
        "heads": {"What it does": "Què fa", "When to use it": "Quan fer-lo servir", "Input": "Paràmetres", "Try it": "Prova-ho", "You get back": "Què obtens", "Data freshness": "Actualitat de les dades"},
        "terms": "this body publishes = que publica aquest organisme; call for tender = licitació; call for expression of interest = convocatòria de manifestacions d'interès; integer id = identificador numèric; in full = complet; funding application = sol·licitud de finançament; Returns, at the start of a description = Retorna (never Torna); European Commission = Comissió Europea; European Parliament = Parlament Europeu; European Council = Consell Europeu; Council of the European Union = Consell de la Unió Europea; Council of the EU = Consell de la UE; Court of Justice of the European Union = Tribunal de Justícia de la Unió Europea; European Central Bank = Banc Central Europeu; European Court of Auditors = Tribunal de Comptes Europeu; European Investment Bank = Banc Europeu d'Inversions; European Ombudsman = Defensor del Poble Europeu; European Committee of the Regions = Comitè Europeu de les Regions; European Economic and Social Committee = Comitè Econòmic i Social Europeu; Publications Office = Oficina de Publicacions; Eurogroup = Eurogrup; body of a document, body text, full body = text complet (never cos); an EU body = un organisme; scraping = extreure dades (never raspallar); feed = canal; to call the API, a call = cridar, una crida; delegated act = acte delegat; implementing act = acte d'execució; Official Journal = Diari Oficial; Court of Justice = Tribunal de Justícia; rapporteur = ponent; tender = licitació; call for proposals = convocatòria de propostes; infringement = infracció; endpoint = ruta; item = element; Brussels = Brussel·les; regulation = reglament. Write correct Catalan with all its accents, never Spanish",
        "bad": r"\bcos\b(?! europeu)|\bcossos\b|raspall|id enter|actes? d'implementaci[óo]|punt final|\bel qual\b.*\bdel que\b", "stop": {"el", "la", "els", "les", "de", "del", "una", "un", "i", "per", "amb", "en"},
    },
    "it": {
        "name": "Italian", "you": "tu",
        "heads": {"What it does": "Cosa fa", "When to use it": "Quando usarlo", "Input": "Parametri", "Try it": "Provalo", "You get back": "Cosa ottieni", "Data freshness": "Aggiornamento dei dati"},
        "terms": "this body publishes = che questo organismo pubblica; integer id = identificativo numerico; European Commission = Commissione europea; European Parliament = Parlamento europeo; European Council = Consiglio europeo; Council of the European Union = Consiglio dell'Unione europea; Council of the EU = Consiglio dell'UE; Court of Justice of the European Union = Corte di giustizia dell'Unione europea; European Central Bank = Banca centrale europea; European Court of Auditors = Corte dei conti europea; European Investment Bank = Banca europea per gli investimenti; European Ombudsman = Mediatore europeo; European Committee of the Regions = Comitato europeo delle regioni; European Economic and Social Committee = Comitato economico e sociale europeo; Publications Office = Ufficio delle pubblicazioni; Eurogroup = Eurogruppo; body of a document, body text, full body = testo completo (never corpo); an EU body = un organismo; scraping = estrarre dati; feed = flusso; to call the API, a call = chiamare, una chiamata; delegated act = atto delegato; implementing act = atto di esecuzione; Official Journal = Gazzetta ufficiale; Court of Justice = Corte di giustizia; rapporteur = relatore; tender = appalto; call for proposals = invito a presentare proposte; infringement = infrazione; endpoint = percorso; item = elemento",
        "bad": r"\bcorpo\b(?! europeo)|\bcorpi\b|atti? di implementazione|punto finale", "stop": {"il", "lo", "la", "le", "gli", "di", "del", "della", "una", "un", "e", "per", "con"},
    },
}
# These stay in the visitor's language; every other EU body keeps the name the console shows it under.
TRANSLATED_BODIES = {"European Commission", "European Parliament", "European Council", "Council of the European Union", "Council of the EU", "Court of Justice of the European Union", "European Central Bank", "European Court of Auditors", "European Investment Bank", "European Ombudsman", "European Committee of the Regions", "European Economic and Social Committee", "Publications Office", "Eurogroup"}
BODY_NAMES = []
ENGLISH = {"the", "of", "and", "with", "for", "to", "from", "this", "that", "is", "are", "by", "on", "it", "each", "one", "returns", "when", "use"}


def fnv(text: str) -> str:
    """The same 32-bit FNV-1a as routeWordsKey in services/api_console.ts, over code points."""
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch)
        h = (h * 0x01000193) & 0xFFFFFFFF
    return format(h, "08x")


def plain_dashes(text: str) -> str:
    return re.sub(r"\s*—\s*", ": ", text)


def first_sentence(description: str) -> str:
    """As whatItDoes in services/api_console.ts."""
    m = re.search(r"\*\*What it does\*\*:?\s*([\s\S]+?)(?:\n\s*\n|\*\*When|$)", description)
    source = m.group(1) if m else (description or "").split("\n\n")[0]
    text = re.sub(r"\s+", " ", re.sub(r"[`*]", "", source)).strip()
    if not text:
        return ""
    stop = -1
    for found in re.finditer(r"\.\s", text):
        if not re.search(r"(?:^|[\s(])(?:e\.g|i\.e|etc|No|nr|vs|Art)$", text[: found.start()]):
            stop = found.start()
            break
    return text[: stop + 1] if stop > 40 else text[:260]


def blocks(description: str) -> list:
    """A description in paragraphs: repeated ones are sent once, and code fences are never sent."""
    return re.split(r"(\n\s*\n)", description)


def worth_sending(block: str) -> bool:
    b = block.strip()
    return bool(b) and not b.startswith("```") and bool(re.search(r"[A-Za-z]{3}", re.sub(r"`[^`]*`", "", b)))


def mask(text: str) -> str:
    for i, name in enumerate(BODY_NAMES):
        if name in text:
            text = text.replace(name, f"{{B{i}}}")
    return text


def unmask(text: str) -> str:
    return re.sub(r"\{B(\d+)\}", lambda m: BODY_NAMES[int(m.group(1))] if int(m.group(1)) < len(BODY_NAMES) else m.group(0), text)


def gate(source: str, target: str, lang: dict) -> str:
    """Why this translation fails, or an empty string. Each test compares it with its source."""
    if not isinstance(target, str) or not target.strip():
        return "empty"
    for label, pattern in (("code", r"`[^`]*`"), ("address", r"https?://[^\s)]+|/api/v2/[^\s)`]*"), ("placeholder", r"\{[^}\s]+\}"), ("tag", r"</?[a-z][^>]*>")):
        lost = collections.Counter(re.findall(pattern, source)) - collections.Counter(re.findall(pattern, target))
        if lost:
            return f"lost {label}: {list(lost)[:2]}"
    bare_s, bare_t = re.sub(r"`[^`]*`", " ", source), re.sub(r"`[^`]*`", " ", target)
    nums = lambda s: collections.Counter(re.sub(r"[.,\s]", "", n) for n in re.findall(r"\d[\d.,]*\d|\d", s))
    if nums(bare_s) - nums(bare_t):
        return f"lost number: {list(nums(bare_s) - nums(bare_t))[:2]}"
    if source.count("**") != target.count("**"):
        return "bold markers differ"
    list_lines = lambda s: len(re.findall(r"(?m)^\s*-\s", s))
    if list_lines(source) != list_lines(target):
        return "list lines differ"
    if "—" in target:
        return "em dash"
    if len(source) > 40 and not 0.45 <= len(target) / len(source) <= 2.6:
        return f"length ratio {len(target) / len(source):.2f}"
    words = re.findall(r"[^\W\d_]+", re.sub(r"\{B\d+\}", " ", bare_t).lower())
    if len(words) >= 5:
        if target.strip() == source.strip():
            return "not translated"
        english = sum(w in ENGLISH for w in words) / len(words)
        own = sum(w in lang["stop"] for w in words) / len(words)
        if english > 0.10 or english > own:
            return f"still English ({english:.2f} against {own:.2f})"
    if re.search(lang["bad"], target, re.I):
        return "not the EU's official term"
    return ""


def ask(key: str, code: str, lang: dict, items: dict) -> dict:
    heads = "; ".join(f"{a} = {b}" for a, b in lang["heads"].items())
    system = (
        f"You translate the documentation of Brubru, a service of European Union data, from English into {lang['name']}, for people "
        f"who are not programmers. Answer with one JSON object with exactly the same keys, each value the translation of that text: "
        f"nothing added, nothing left out, no notes.\nRules:\n"
        f"- Keep the Markdown exactly as it is: every ** marker, every line break, every list dash.\n"
        f"- Never change anything inside backticks. Never change web addresses, paths, parameter names, placeholders in braces, "
        f"HTML tags, numbers, dates, or codes such as CELEX, ECLI, COM(2024) 12 and COD.\n"
        f"- Keep every acronym and product name as it is (ENISA, EFSA, TED, CORDIS, OEIL, EUR-Lex, Brubru).\n"
        f"- Use these words: {lang['terms']}.\n- These headings are always written so: {heads}.\n"
        f"- Address the reader as '{lang['you']}'. Plain words. Never use an em dash: use a colon or a comma."
    )
    while True:
        alive = [m for m in MODELS if m not in ask.dead]
        if not alive:
            raise DayIsOver()
        now = time.time()
        for m in alive:
            if now >= ask.reset.get(m, 0):
                ask.left[m] = 8000
        model = alive[0]  # The first model read better on the Catalan sample: the next is for when it has run out for the day.
        if ask.left.get(model, 8000) < 3000:
            time.sleep(max(1.0, ask.reset.get(model, 0) - now))
            continue
        extra = {"reasoning_effort": "none"} if model.startswith("qwen") else {"reasoning_effort": "low"}
        body = json.dumps({"model": model, "temperature": 0.1, "response_format": {"type": "json_object"}, "reasoning_format": "hidden", **extra, "messages": [
            {"role": "system", "content": system}, {"role": "user", "content": json.dumps(items, ensure_ascii=False)},
        ]}).encode()
        req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "brubru-console-words"})
        try:
            with urllib.request.urlopen(req, timeout=180, context=CTX) as r:
                reply = json.load(r)
                ask.left[model] = int(r.headers.get("x-ratelimit-remaining-tokens") or 8000)
                ask.reset[model] = time.time() + seconds(r.headers.get("x-ratelimit-reset-tokens") or "1s")
            ask.tokens[0] += reply.get("usage", {}).get("prompt_tokens", 0)
            ask.tokens[1] += reply.get("usage", {}).get("completion_tokens", 0)
            ask.calls[model] = ask.calls.get(model, 0) + 1
            return json.loads(re.sub(r"(?s)<think>.*?</think>", "", reply["choices"][0]["message"]["content"]))
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")
            if e.code == 429 and ("per day" in text or "TPD" in text or "RPD" in text):
                print(f"[INFO] {model}: the day's limit is reached: {re.sub(r'Organization [^ ]+ ', '', text)[:220]}", flush=True)
                ask.dead.add(model)
                continue
            if e.code == 429:
                ask.left[model] = 0
                ask.reset[model] = time.time() + (float(e.headers.get("retry-after") or 0) or 20)
                continue
            if e.code == 400 and "json" in text.lower():
                return {}  # The model wrote invalid JSON: the items go again one at a time.
            if e.code in (500, 502, 503, 504):
                time.sleep(10)
                continue
            print(f"[ERROR] {model}: {e.code} {text[:200]}", flush=True)
            raise
        except (json.JSONDecodeError, KeyError, TimeoutError, urllib.error.URLError):
            time.sleep(5)
            return {}


def seconds(text: str) -> float:
    """Groq's reset: 15.24s, 607ms, 1m2.5s."""
    total = 0.0
    for value, unit in re.findall(r"([\d.]+)(ms|s|m|h)", text):
        total += float(value) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]
    return total or 1.0


class DayIsOver(Exception):
    """Both models have used up the day: keep what is done, and carry on tomorrow."""


ask.left, ask.reset, ask.calls, ask.dead = {}, {}, {}, set()
ask.tokens = [0, 0]


def batches(texts: list) -> list:
    out, cur, size = [], {}, 0
    for i, text in enumerate(texts):
        if cur and size + len(text) > BATCH_CHARS:
            out.append(cur)
            cur, size = {}, 0
        cur[str(i)] = text
        size += len(text)
    if cur:
        out.append(cur)
    return out


def translate_all(key: str, code: str, lang: dict, texts: list, memory: dict) -> tuple:
    todo = [t for t in dict.fromkeys(texts) if t not in memory]
    failures = collections.Counter()
    print(f"[INFO] {code}: {len(todo)} new segments of {len(set(texts))}, {sum(map(len, todo)):,} characters", flush=True)
    for n, batch in enumerate(batches([mask(x) for x in todo]), 1):
        reply = ask(key, code, lang, batch)
        retry = []
        for k, source in batch.items():
            why = gate(source, reply.get(k), lang) if k in reply else "no answer"
            if why:
                retry.append((k, source, why))
            else:
                memory[unmask(source)] = unmask(reply[k])
        for k, source, first_why in retry:  # One at a time, once: a batch can fail on its neighbour.
            one = ask(key, code, lang, {"0": source})
            why = gate(source, one.get("0"), lang) if "0" in one else "no answer"
            if why:
                failures[why.split(":")[0].split(" (")[0]] += 1
                MEMORY.mkdir(parents=True, exist_ok=True)
                with open(MEMORY / f"{code}_failed.txt", "a") as f:
                    f.write(f"{why} || {unmask(source)[:300]!r}\n")
            else:
                memory[unmask(source)] = unmask(one["0"])
        save_memory(code, memory)
        if n % 5 == 0:
            print(f"[INFO] {code}: batch {n}, tokens {ask.tokens}, calls {ask.calls}, failed {sum(failures.values())}", flush=True)
    return memory, failures


def save_memory(code: str, memory: dict) -> None:
    MEMORY.mkdir(parents=True, exist_ok=True)
    (MEMORY / f"{code}.json").write_text(json.dumps(memory, ensure_ascii=False))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--lang", action="append", choices=sorted(LANGS))
    p.add_argument("--part", choices=("short", "full", "all"), default="all", help="short: summary and first sentence. full: the long description")
    p.add_argument("--revalidate", action="store_true", help="judge every route again, not only those whose English changed")
    p.add_argument("--limit", type=int, help="only this many routes, picked evenly: for trying a language")
    p.add_argument("--sample", type=int, default=0, help="print this many segments beside their source")
    p.add_argument("--dry-run", action="store_true", help="write no file in the repo")
    p.add_argument("--apply", action="store_true")
    a = p.parse_args()
    if not a.apply and not a.dry_run:
        sys.exit("Say --dry-run or --apply")
    key = next((l.split("=", 1)[1].strip() for l in (pathlib.Path.home() / "Developer/brubru/backend/.env").read_text().splitlines() if l.startswith("GROQ_API_KEY=")), "")
    if not key:
        sys.exit("[ERROR] no GROQ_API_KEY in backend/.env")
    spec = json.load(urllib.request.urlopen(SPEC, timeout=180, context=CTX))
    lists = json.load(urllib.request.urlopen(SPEC.replace("openapi.json", "pick-lists"), timeout=60, context=CTX))
    BODY_NAMES.extend(sorted({b["name"] for b in lists["bodies"] if len(b["name"].split()) >= 3 and b["name"] not in TRANSLATED_BODIES}, key=len, reverse=True))
    routes = []
    for path, item in spec["paths"].items():
        get = item.get("get")
        if not get or not path.startswith("/api/v2/"):
            continue
        summary, description = get.get("summary") or "", get.get("description") or ""
        routes.append({"path": path, "key": fnv(summary + "\n" + description), "summary": plain_dashes(summary), "description": plain_dashes(description)})
    routes.sort(key=lambda r: r["path"])
    if a.limit:
        step = max(1, len(routes) // a.limit)
        routes = routes[::step][: a.limit]
    print(f"[INFO] {len(routes)} routes", flush=True)
    bad_runs = 0
    for code in a.lang or sorted(LANGS):
        lang = LANGS[code]
        path_small, path_full = OUT / f"{code}.json", OUT / f"{code}_full.json"
        small = json.loads(path_small.read_text()) if path_small.exists() else {}
        full = json.loads(path_full.read_text()) if path_full.exists() else {}
        want_short, want_full = a.part in ("short", "all"), a.part in ("full", "all")
        changed = routes if a.revalidate else [r for r in routes if (want_short and small.get(r["path"], {}).get("k") != r["key"]) or (want_full and full.get(r["path"], {}).get("k") != r["key"])]
        memory_file = MEMORY / f"{code}.json"
        memory = json.loads(memory_file.read_text()) if memory_file.exists() else {}
        # Today's gate judges what is stored too: a rule learned from reading the last run clears what it let through.
        stale = [s for s, x in memory.items() if gate(mask(s), mask(x), lang)]
        for s in stale:
            del memory[s]
        if stale:
            print(f"[INFO] {code}: {len(stale)} stored segments fail today's gate, sent again", flush=True)
        texts = []
        for r in changed:
            if want_short:
                texts += [t for t in (r["summary"], first_sentence(r["description"])) if t]
            if want_full:
                texts += [b for b in blocks(r["description"]) if worth_sending(b)]
        failures = collections.Counter()
        ended = False
        try:
            memory, failures = translate_all(key, code, lang, texts, memory)
        except DayIsOver:
            ended = True
            print(f"[INFO] {code}: stopped for the day, what is done is kept", flush=True)
        save_memory(code, memory)
        whole_short, whole_full, waiting = 0, 0, 0
        for r in changed:
            sentence = first_sentence(r["description"])
            if want_short:
                if (not r["summary"] or r["summary"] in memory) and (not sentence or sentence in memory):
                    small[r["path"]] = {"k": r["key"], "s": memory.get(r["summary"], ""), "w": memory.get(sentence, "")}
                    whole_short += 1
                else:
                    small.pop(r["path"], None)
                    waiting += 1
            if want_full:
                parts = [memory.get(b) if worth_sending(b) else b for b in blocks(r["description"])]
                if all(x is not None for x in parts):
                    full[r["path"]] = {"k": r["key"], "d": "".join(parts)}
                    whole_full += 1
                else:
                    full.pop(r["path"], None)
                    waiting += 1
        live = {r["path"] for r in routes} if not a.limit else None
        if live:
            small = {k: v for k, v in small.items() if k in live}
            full = {k: v for k, v in full.items() if k in live}
        print(f"[OK] {code}: short {whole_short}, full {whole_full}, {waiting} stay in English for now, failures {dict(failures)}, tokens {ask.tokens}", flush=True)
        bad_runs += waiting
        if a.sample:
            random.seed(7)
            pool = [t for t in dict.fromkeys(texts) if t in memory]
            for t in random.sample(pool, min(a.sample, len(pool))):
                print(f"--- {t[:420]}\n=== {memory[t][:420]}")
        if a.apply:
            OUT.mkdir(parents=True, exist_ok=True)
            # One route a line, so a re-run's diff shows the routes that changed.
            for target, words in ((path_small, small), (path_full, full)):
                lines = [f"{json.dumps(k, ensure_ascii=False)}:{json.dumps(v, ensure_ascii=False, separators=(',', ':'))}" for k, v in sorted(words.items())]
                target.write_text("{\n" + ",\n".join(lines) + "\n}\n")
            print(f"[OK] wrote {path_small.stat().st_size:,} and {path_full.stat().st_size:,} bytes", flush=True)
    print(f"[INFO] tokens in {ask.tokens[0]:,}, out {ask.tokens[1]:,}", flush=True)
    if bad_runs:
        print(f"[INFO] {bad_runs} route-language pairs stay in English until a re-run", flush=True)


if __name__ == "__main__":
    main()
