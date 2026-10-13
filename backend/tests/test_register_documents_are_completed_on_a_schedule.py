"""A register document is completed by the cron, not by a script someone remembers to run.

13 October 2026: the 100 newest documents on /commission-register-documents served no text, and
82 of them no date and no link. A document arrives as a reference and a title; its CELEX, date
and text came from scripts run by hand, last on 2 October, so 110 of the 111 documents that
arrived after 5 October had no text."""
import datetime as dt
import pathlib
import re
from types import SimpleNamespace

from scripts import complete_commission_documents as job

BACKEND = pathlib.Path(__file__).resolve().parents[1]
SINCE = dt.datetime(2026, 9, 13, tzinfo=dt.timezone.utc)
TEXT = ("<p>Council Decision</p>", "Council Decision (CFSP) 2026/2285 " * 40)
CORRIGENDUM = "32011L0089R(02)"
ROMANIAN = ("Jurnalul Oficial al Uniunii Europene RO Seria L 8.10.2026 Rectificare la Directiva 2011/89/UE a "
            "Parlamentului European si a Consiliului din 16 noiembrie 2011 de modificare a Directivelor 98/78/CE. "
            "La pagina 120, articolul 2 punctul 2: in loc de ... se citeste ...")


class _Result:
    def __init__(self, rows=(), scalar=0, rowcount=1):
        self.rows, self.scalar, self.rowcount = list(rows), scalar, rowcount

    def __iter__(self):
        return iter(self.rows)

    def scalar_one(self):
        return self.scalar


class _Engine:
    """Answers each of the job's statements; records every write."""

    def __init__(self, no_celex=(), taken=(), no_date=(), laws_have=0, no_text=(), no_title=(), no_languages=()):
        self.reads = {id(job.NO_CELEX): no_celex, id(job.TAKEN): [(c,) for c in taken],
                      id(job.NO_DATE): no_date, id(job.NO_TEXT): no_text, id(job.NO_TITLE): no_title,
                      id(job.NO_LANGUAGES): no_languages}
        self.laws_have, self.writes = laws_have, []

    def execute(self, stmt, params=None):
        if id(stmt) in self.reads:
            return _Result(self.reads[id(stmt)])
        if stmt is job.LAWS_HAVE:
            return _Result(scalar=self.laws_have)
        self.writes.append((stmt, params))
        return _Result(rowcount=self.laws_have if stmt is job.FROM_LAWS else 1)

    def connect(self):
        return self

    begin = connect

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _cellar(monkeypatch, holds=None, text=TEXT, in_language=None):
    """`holds` is what Cellar states per CELEX; None means Cellar does not answer at all."""
    asked = []

    def facts(celexes, ctx):
        asked.append(list(celexes))
        if holds is None:
            raise TimeoutError("Cellar did not answer")
        return {c: holds[c] for c in celexes if c in holds}
    monkeypatch.setattr(job.time, "sleep", lambda _s: None)
    monkeypatch.setattr(job, "_facts", facts)
    monkeypatch.setattr(job._laws, "_fetch", lambda celex, ctx: text)
    monkeypatch.setattr(job, "_fetch_in", lambda celex, lang, ctx: (in_language or {}).get(lang, "http_404"))
    return asked


def _held(date=None, **titles):
    return {"dates": {date} if date else set(), "titles": titles}


def _doc(i, **kw):
    kw.setdefault("portal_url", None)
    return SimpleNamespace(id=i, **kw)


def test_the_cron_runs_it_after_the_documents_and_the_law_texts_arrive():
    src = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
    hot = src[src.index('@router.post("/sync/hot-6h")'):src.index("hot-6h tier sync complete")]
    line = next(ln for ln in hot.splitlines() if "complete_commission_documents.py" in ln)
    assert '"--apply"' in line
    assert hot.index('results["commission_docs"] =') < hot.index(line)
    assert hot.index('results["eu_laws_bodies"] =') < hot.index(line)


def test_a_row_gets_the_celex_it_states_only_once_cellar_holds_it(monkeypatch):
    row = _doc(1, reference="32026D2285", title="Council Decision (CFSP) 2026/2285 of 12 October 2026")
    _cellar(monkeypatch, holds={"32026D2285": _held("2026-10-12")})
    db = _Engine(no_celex=[row])
    job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [(job.SET_CELEX, {"rid": 1, "v": "32026D2285"})]

    _cellar(monkeypatch, holds={})
    db = _Engine(no_celex=[row])
    work, reached, n = job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [] and n["celex"] == 0
    assert (work, reached) == (1, 1)  # Cellar answered: it does not hold it yet


def test_the_celex_is_read_whole_and_never_rebuilt_from_a_reference():
    link = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"
    # 52026SC0050 is an opinion of the Regulatory Scrutiny Board; SWD(2026) 50 is 52026SC0050(01).
    assert job.stated_celex("SWD(2026) 50", "COMMISSION STAFF WORKING DOCUMENT Monitoring Road Safety",
                            link + "52026SC0050(01)") == "52026SC0050(01)"
    assert job.stated_celex("SWD(2024) 29", "EVALUATION", link + "52024SC0029R(02)") == "52024SC0029R(02)"
    assert job.stated_celex("SWD(2026) 702", "SWD document 52026SC0702", None) == "52026SC0702"
    assert job.stated_celex("32011D0402", "CELEX:32011D0402(01)R(02)", None) == "32011D0402(01)R(02)"
    assert job.stated_celex("32024L2841R(01)", "Corrigendum to Directive (EU) 2024/2841", None) == "32024L2841R(01)"
    assert job.stated_celex("32026D05201", "Council Decision of 1 October 2026", None) == "32026D05201"
    # Nothing states one: none is made up from the document number.
    assert job.stated_celex("SWD(2026) 50", "COMMISSION STAFF WORKING DOCUMENT", None) is None
    assert job.stated_celex("JOIN(2026) 12", "JOINT COMMUNICATION", None) is None
    assert job.stated_celex("SEC(2026)2564", "Tentative agenda for forthcoming Commission meetings",
                            "https://ec.europa.eu/transparency/documents-register/detail?ref=SEC(2026)2564") is None
    # A string that only starts like a CELEX is not cut down to one.
    assert job.stated_celex(None, "CELEX:32011L0089R(02)x", None) is None
    assert job.stated_celex(None, None, link + "32011L0089R(02)&from=EN") is None


def test_a_celex_another_row_holds_is_never_given_twice(monkeypatch):
    asked = _cellar(monkeypatch, holds={"52026SC0702": _held("2026-10-02")})
    db = _Engine(no_celex=[_doc(1, reference="SWD(2026) 702", title="SWD document 52026SC0702")],
                 taken=["52026SC0702"])
    work, _, _ = job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [] and work == 0 and asked == []


def test_date_text_and_title_are_what_cellar_states(monkeypatch):
    title = "COMMISSION STAFF WORKING DOCUMENT Third River Basin Management Plans"
    _cellar(monkeypatch, holds={"52026SC0702": _held("2026-10-02", ENG=title, FRA="DOCUMENT DE TRAVAIL DES SERVICES")})
    db = _Engine(no_date=[_doc(1, celex="52026SC0702")], no_text=[_doc(1, celex="52026SC0702")],
                 no_title=[_doc(1, celex="52026SC0702", title="SWD document 52026SC0702")])
    work, reached, n = job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [
        (job.SET_DATE, {"rid": 1, "v": dt.date(2026, 10, 2)}),
        (job.SET_TEXT, {"rid": 1, "txt": TEXT[1], "html": TEXT[0]}),
        (job.SET_TITLE, {"rid": 1, "v": title}),
    ]
    assert (work, reached) == (3, 3)
    assert n == {"celex": 0, "date": 1, "text_from_laws": 0, "text_from_cellar": 1, "title": 1, "languages": 0}


def test_an_act_s_text_is_copied_from_the_laws_table_before_cellar_is_asked(monkeypatch):
    _cellar(monkeypatch, holds={})
    db = _Engine(laws_have=7)
    _, _, n = job.complete(db, None, SINCE, apply=True, limit=60)
    assert [w[0] for w in db.writes] == [job.FROM_LAWS] and n["text_from_laws"] == 7
    # Cellar is asked only for a text the laws table does not hold.
    assert "NOT EXISTS (SELECT 1 FROM eu_laws" in str(job.NO_TEXT)


def test_a_dry_run_writes_nothing(monkeypatch):
    _cellar(monkeypatch, holds={"32026D2285": _held("2026-10-12")})
    db = _Engine(no_celex=[_doc(1, reference="32026D2285", title="Council Decision")],
                 no_date=[_doc(2, celex="32026D2285")], laws_have=3, no_text=[_doc(2, celex="32026D2285")])
    _, _, n = job.complete(db, None, SINCE, apply=False, limit=60)
    assert db.writes == []
    assert (n["celex"], n["date"], n["text_from_laws"], n["text_from_cellar"]) == (1, 1, 3, 1)


def test_a_backlog_is_worked_through_over_several_runs(monkeypatch):
    asked = _cellar(monkeypatch, holds={})
    rows = [_doc(i, reference=f"32026D{2000 + i}", title="Council Decision") for i in range(5)]
    job.complete(_Engine(no_celex=rows), None, SINCE, apply=True, limit=2)
    assert asked[0] == ["32026D2000", "32026D2001"]


def test_cellar_refusing_us_is_not_read_as_no_text(monkeypatch):
    assert job.answered(TEXT) and job.answered("http_404") and job.answered("too_short_212")
    assert job.answered("names_another_act") and job.answered("no_language")
    for wall in ("http_403", "http_429", "http_503", "URLError", "TimeoutError", "pdf_PdfReadError", "empty"):
        assert not job.answered(wall), wall
    # Every source down: the run fails instead of reporting that nothing needed doing.
    _cellar(monkeypatch, holds=None, text="http_503")
    db = _Engine(no_celex=[_doc(1, reference="32026D2285", title="Council Decision")],
                 no_date=[_doc(2, celex="32026R2269")], no_text=[_doc(2, celex="32026R2269")],
                 no_title=[_doc(3, celex="52026SC0702", title="SWD document 52026SC0702")])
    work, reached, _ = job.complete(db, None, SINCE, apply=True, limit=60)
    assert (work, reached) == (4, 0) and db.writes == []
    assert job.verdict(work, reached, []) == (1, None)


def test_documents_still_incomplete_after_three_days_are_named_not_hidden():
    code, line = job.verdict(5, 5, [f"52026PC0{n}" for n in range(500, 511)])
    assert code == 0
    assert line.startswith("11 register documents older than 3 days still lack a date or a text: 52026PC0500, ")
    assert line.endswith("and 3 more")
    assert job.verdict(5, 5, []) == (0, None)
    assert job.verdict(0, 0, []) == (0, None)  # nothing to do is not a failure
    # A document that arrived yesterday is not yet late: Cellar can lag two days.
    assert "first_seen < :settled" in str(job.STILL)


def test_an_empty_or_disputed_answer_is_never_stored():
    assert job.one_title({"ENG": ""}) is None                      # Cellar returned an empty title for one SWD
    assert job.one_title({"ENG": "SWD/2026/119 final"}) is None    # the short form is not the title
    assert job.one_title({"ENG": "  COMMISSION STAFF  WORKING DOCUMENT\nEvaluation "}) == "COMMISSION STAFF WORKING DOCUMENT Evaluation"
    assert job.one_title(None) is None and job.one_title({}) is None
    assert job.one_date({"2026-10-02", "2026-10-03"}) is None
    assert job.one_date({"2026-10-02"}) == dt.date(2026, 10, 2)
    assert job.one_date(None) is None


def test_a_corrigendum_is_read_in_a_language_it_exists_in():
    # 274 of the 293 corrigenda held on 13 Oct 2026 have no English version; 236 exist in one language.
    assert job.pick_language({"ENG": "Corrigendum", "FRA": "Rectificatif", "RON": "Rectificare"}) == "ENG"
    assert job.pick_language({"SPA": "Corrección", "FRA": "Rectificatif", "BUL": "x"}) == "FRA"
    assert job.pick_language({"POL": "Sprostowanie", "SPA": "Corrección"}) == "SPA"
    assert job.pick_language({"RON": "Rectificare"}) == "RON"
    assert job.pick_language({"RON": "Rectificare", "BUL": "x"}) == "BUL"
    assert job.pick_language({}) is None and job.pick_language(None) is None
    # `languages` names the language of the stored title and text first.
    assert job.language_codes({"RON": "x"}) == ["RO"]
    assert job.language_codes({"POL": "x", "SPA": "x", "BUL": "x"}) == ["ES", "BG", "PL"]
    assert job.language_codes({}) == []
    assert job.one_title({"RON": "Rectificare la Directiva 2011/89/UE a Parlamentului European"}) \
        == "Rectificare la Directiva 2011/89/UE a Parlamentului European"
    assert job.is_corrigendum("32011L0089R(02)") and job.is_corrigendum("32011D0402(01)R(02)")
    # A proposal's later version is a full English document, read like any other.
    assert not job.is_corrigendum("52024SC0029R(02)") and not job.is_corrigendum("32011L0089")


def test_a_corrigendum_gets_its_own_date_text_title_and_languages(monkeypatch):
    title = "Rectificare la Directiva 2011/89/UE a Parlamentului European și a Consiliului"
    _cellar(monkeypatch, holds={CORRIGENDUM: _held("2026-10-08", RON=title)},
            in_language={"RON": ("<p>Rectificare</p>", ROMANIAN)})
    row = dict(celex=CORRIGENDUM)
    db = _Engine(no_date=[_doc(1, **row)], no_text=[_doc(1, **row)],
                 no_title=[_doc(1, title="CELEX:32011L0089R(02)", **row)],
                 no_languages=[_doc(1, languages=["EN"], **row)])
    _, _, n = job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [
        (job.SET_DATE, {"rid": 1, "v": dt.date(2026, 10, 8)}),      # its own date, not the 2011 directive's
        (job.SET_TEXT, {"rid": 1, "txt": ROMANIAN, "html": "<p>Rectificare</p>"}),
        (job.SET_TITLE, {"rid": 1, "v": title}),
        (job.SET_LANGUAGES, {"rid": 1, "v": ["RO"]}),
    ]
    assert n["languages"] == 1


def test_a_page_about_another_act_is_not_stored_as_the_corrigendum(monkeypatch):
    assert job.names_its_act("32024L2841R(01)", "Corrigendum to Directive (EU) 2024/2841 of the European Parliament")
    assert job.names_its_act("32012R0036R(03)", "Rectificatif au règlement (UE) n o 36/2012 du Conseil")
    assert job.names_its_act("31985L0374R(01)", "Corrigendum to Council Directive 85/374/EEC")
    assert job.names_its_act("32011L0089R(02)", "Rectificare la Directiva 2011/ 89/UE")
    assert not job.names_its_act("32011L0089R(02)", "Corrigendum to Directive (EU) 2024/2841")
    assert not job.names_its_act("not a celex", "2011/89")

    class _Page:
        def __init__(self, body):
            self.body = body

        def read(self):
            return self.body.encode()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False
    pages = {"another": "<html><body><p>Corrigendum to Directive (EU) 2024/2841 " + "of the Council " * 20 + "</p></body></html>",
             "stub": "<html><body><p>2011/89</p></body></html>",
             "own": "<html><body><p>" + ROMANIAN + "</p></body></html>"}
    asked = []
    for name, want in (("another", "names_another_act"), ("stub", "too_short_7")):
        monkeypatch.setattr(job.urllib.request, "urlopen", lambda req, **kw: _Page(pages[name]))
        assert job._fetch_in(CORRIGENDUM, "RON", None) == want
    monkeypatch.setattr(job.urllib.request, "urlopen",
                        lambda req, **kw: asked.append((req.full_url, req.get_header("Accept-language"))) or _Page(pages["own"]))
    html, txt = job._fetch_in(CORRIGENDUM, "RON", None)
    assert "Rectificare la Directiva 2011/89/UE" in txt and html
    # Asked for the corrigendum's own CELEX, brackets encoded, in the language it exists in.
    assert asked == [("https://publications.europa.eu/resource/celex/32011L0089R%2802%29", "ron")]


def test_a_document_cellar_lists_in_no_language_is_not_fetched(monkeypatch):
    _cellar(monkeypatch, holds={CORRIGENDUM: _held("2026-10-08")})
    assert job.text_for(CORRIGENDUM, {}, None) == "no_language"
    assert job.text_for("32026D2285", None, None) == TEXT  # an act is read in English, as before


def test_a_row_still_filed_under_the_act_it_corrects_is_left_alone():
    # "CELEX:32011L0089R(02)" stored under 32011L0089: that act's 2011 date and text are not its own.
    for stmt in (job.NO_CELEX, job.NO_DATE, job.NO_TEXT, job.FROM_LAWS, job.LAWS_HAVE, job.NO_TITLE,
                 job.NO_LANGUAGES, job.STILL):
        sql = str(stmt)
        assert "title ~ '^CELEX:\\S*R\\([0-9]+\\)'" in sql and "reference !~ 'R\\([0-9]{2}\\)$'" in sql, sql
    # The same two tests, as the database applies them.
    def misfiled(reference, title):
        return bool(re.search(r"^CELEX:\S*R\([0-9]+\)", title)) and not re.search(r"R\([0-9]{2}\)$", reference)
    assert misfiled("32011L0089", "CELEX:32011L0089R(02)")
    assert misfiled("32024L2841", "CELEX:32024L2841R(01): Corrigendum to Directive (EU) 2024/2841")
    assert not misfiled("32011L0089R(02)", "CELEX:32011L0089R(02)")   # refiled: completed like any row
    assert not misfiled("32026D2285", "Council Decision (CFSP) 2026/2285 of 12 October 2026")


def test_only_an_empty_cell_is_written():
    assert "coalesce(celex, '') = ''" in str(job.SET_CELEX)
    assert "publication_date IS NULL" in str(job.SET_DATE)
    assert "coalesce(text_body, '') = ''" in str(job.SET_TEXT)
    assert "coalesce(d.text_body, '') = ''" in str(job.FROM_LAWS)
    # A real title is never replaced: only the placeholder the feed reader wrote.
    assert f"title ~ '{job.PLACEHOLDER}'" in str(job.SET_TITLE)
    for placeholder in ("SWD document 52026SC0702", "SEC document 52026SC0133", "CELEX:32011L0089R(02)"):
        assert re.search(job.PLACEHOLDER, placeholder), placeholder
    assert not re.search(job.PLACEHOLDER, "COMMISSION STAFF WORKING DOCUMENT Evaluation")
    # Languages: only the feed reader's default is replaced, and only on a corrigendum.
    assert "IN ('{}', '{EN}')" in str(job.SET_LANGUAGES)
    assert "celex ~ '^3.*R\\([0-9]{2}\\)$'" in str(job.NO_LANGUAGES)
