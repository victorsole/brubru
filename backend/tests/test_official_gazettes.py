"""
BOE and DOGC ingestion for the Terraqui / LIFE DPP-TEX watch (8 Oct 2026).

No network and no database: the fetchers take an injected session and the sync's
verdict function is pure. What these pin down is the part that makes the ingestion
trustworthy: the matcher keeps the regime and drops contract awards and curricula, the
BOE nesting variants parse, an empty day is not an error, and a window that READ nothing
is a failure rather than a quiet day.
"""

import sys
from datetime import date
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.scrapers import official_gazettes as og  # noqa: E402


@pytest.mark.parametrize("title,section,tier", [
    # the regime, in both languages, in the rule sections
    ("Real Decreto 999/2026, por el que se regula la gestión de residuos de productos textiles y calzado", "1", "strict"),
    ("Decret 12/2026, de responsabilitat ampliada del productor de tèxtils", "1", "strict"),
    ("Resolución por la que se publica el Convenio sobre ecodiseño de productos sostenibles", "3", "strict"),
    ("Orden por la que se crea el pasaporte digital de producto", "1", "strict"),
    # a consultation in the announcements section still counts
    ("Anuncio por el que se somete a información pública el proyecto de real decreto de residuos textiles", "5B", "strict"),
    # waste and the environment are the broad tier, rule sections only
    ("Real Decreto por el que se regula el registro de producción y gestión de residuos", "1", "broad"),
    ("Resolución de la Dirección General de Calidad y Evaluación Ambiental, por la que se formula declaración", "3", "broad"),
    # not the regime
    ("Anuncio de formalización de contratos de: Oficialía Mayor. Objeto: Suministro de vestuario", "5A", None),
    ("Anuncio de licitación: suministro de envases", "5A", None),
    # a contract notice that cites an Order is still a contract notice
    ("Anuncio de licitación conforme a la Orden HAC/1/2026: suministro de prendas textiles", "5A", None),
    ("Resolución de nombramiento de funcionario", "2A", None),
    ("Decret 180/2025, del currículum del cicle formatiu de grau mitjà d'arts plàstiques i disseny en indumentària tèxtil", "1", None),
])
def test_matcher_keeps_the_regime_and_drops_noise(title, section, tier):
    got, _ = og.classify(title, section)
    assert got == tier, title


def test_broad_tier_does_not_apply_to_announcement_sections():
    assert og.classify("Anuncio de la autorización de una instalación de gestión de residuos", "5B")[0] is None
    assert og.classify("Anuncio de la autorización de una instalación de gestión de residuos", "3")[0] == "broad"


def test_dogc_rows_are_all_rules():
    assert og.classify("Ordre de modificació de la gestió de residus i economia circular", always_broad=True)[0] == "broad"


def test_accents_and_case_are_folded():
    assert og.fold("TÈXTIL Calçat Ecodiseño") == "textil calcat ecodiseno"
    assert og.classify("DECRET sobre el TÈXTIL i el CALÇAT", "1")[0] == "strict"


def _summary(sections):
    return {"data": {"sumario": {"diario": [{"seccion": sections}]}}}


def test_boe_parser_handles_every_nesting_the_api_uses():
    # a bare object where a list would have one element, items directly under the
    # department, and items under an epigraph (single object and list)
    payload = _summary([
        {"codigo": "1", "departamento": {          # department as a single object
            "nombre": "MINISTERIO PARA LA TRANSICION ECOLOGICA",
            "epigrafe": {"nombre": "Residuos", "item": {   # epigraph and item as single objects
                "identificador": "BOE-A-2026-1", "titulo": "Real Decreto por el que se regula la gestión de residuos de productos textiles",
                "url_html": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-1",
                "url_pdf": {"texto": "https://www.boe.es/pdf/BOE-A-2026-1.pdf"}}}}},
        {"codigo": "3", "departamento": [{
            "nombre": "MINISTERIO DE HACIENDA",
            "item": [{"identificador": "BOE-A-2026-2", "titulo": "Resolución sobre el convenio de asistencia"},
                     {"identificador": "BOE-A-2026-3", "titulo": "Resolución de biodiversidad y evaluación ambiental"}]}]},
        {"codigo": "5A", "departamento": [{"nombre": "X", "item": [
            {"identificador": "BOE-B-2026-4", "titulo": "Anuncio de formalización de contratos: suministro de vestuario"}]}]},
    ])
    scanned, items = og.parse_boe_summary(payload, date(2026, 10, 8))
    assert scanned == 4  # every item read, matched or not
    assert [i.identifier for i in items] == ["BOE-A-2026-1", "BOE-A-2026-3"]
    first = items[0]
    assert (first.tier, first.section, first.rank) == ("strict", "1", "Residuos")
    assert first.pdf_url == "https://www.boe.es/pdf/BOE-A-2026-1.pdf"
    assert first.url.endswith("id=BOE-A-2026-1")


class FakeResponse:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise og.requests.HTTPError(str(self.status_code))


class FakeSession:
    def __init__(self, by_url_part):
        self.by_url_part = by_url_part
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params))
        for part, resp in self.by_url_part.items():
            if part in url or (params and part in str(params)):
                return resp
        return FakeResponse(404)


_ISSUE = _summary([{"codigo": "1", "departamento": [{"nombre": "M", "item": [
    {"identificador": "BOE-A-9", "titulo": "Real Decreto de ecodiseño de productos textiles"}]}]}])


def test_boe_empty_day_is_not_an_error_and_a_server_error_is():
    s = FakeSession({"20261008": FakeResponse(200, _ISSUE), "20261007": FakeResponse(404),
                     "20261006": FakeResponse(500)})
    res = og.fetch_boe(3, today=date(2026, 10, 8), session=s, pace=0)
    assert res.days_with_issue == 1 and res.scanned == 1 and len(res.items) == 1
    assert res.newest_published == date(2026, 10, 8)
    assert res.errors == ["2026-10-06: HTTP 500"]  # the 404 Sunday-style day is silent


def test_dogc_reads_pages_and_flags_a_broken_payload():
    row = {"n_mero_de_control": "26200001", "t_tol_de_la_norma": "Decret 1/2026, de responsabilitat ampliada del productor",
           "t_tol_de_la_norma_es": "Decreto 1/2026, de responsabilidad ampliada del productor",
           "data_de_publicaci_del_diari": "2026-10-06T00:00:00.000", "rang_de_norma": "Decret",
           "format_pdf": {"url": "https://portaljuridic.gencat.cat/x/pdf"},
           "url_ltima_versi_format_html": {"url": "https://portaljuridic.gencat.cat/x"}}
    other = dict(row, n_mero_de_control="26200002", t_tol_de_la_norma="Decret 2/2026, de nomenaments",
                 t_tol_de_la_norma_es="Decreto 2/2026, de nombramientos")
    ok = og.fetch_dogc(30, today=date(2026, 10, 8), session=FakeSession({"n6hn-rmy7": FakeResponse(200, [row, other])}))
    assert ok.scanned == 2 and [i.identifier for i in ok.items] == ["26200001"]
    assert ok.items[0].tier == "strict" and ok.items[0].rank == "Decret"
    assert ok.items[0].title_es.startswith("Decreto 1/2026")

    broken = og.fetch_dogc(30, today=date(2026, 10, 8),
                           session=FakeSession({"n6hn-rmy7": FakeResponse(200, {"error": True, "message": "query.soql.no-such-column"})}))
    assert broken.scanned == 0 and broken.errors and "unexpected payload" in broken.errors[0]


def test_sync_judges_a_window_that_read_nothing_as_failed():
    sys.path.insert(0, str(BACKEND / "scripts"))
    import sync_official_gazettes as sync

    quiet_but_read = og.ScanResult(gazette="boe", days_requested=5, days_with_issue=4, scanned=800)
    assert sync.judge(quiet_but_read) == ("success", "")  # scanned plenty, matched nothing: healthy

    read_nothing = og.ScanResult(gazette="boe", days_requested=5, days_with_issue=0, scanned=0)
    assert sync.judge(read_nothing)[0] == "failed"

    all_errors = og.ScanResult(gazette="boe", days_requested=5, errors=["2026-10-08: HTTP 500"] * 5)
    assert sync.judge(all_errors)[0] == "failed"

    dogc_nothing = og.ScanResult(gazette="dogc", days_requested=30, scanned=0)
    assert sync.judge(dogc_nothing)[0] == "failed"

    short_window = og.ScanResult(gazette="boe", days_requested=2, days_with_issue=0, scanned=0)
    assert sync.judge(short_window)[0] == "success"  # two days cannot be judged

    partial = og.ScanResult(gazette="boe", days_requested=5, days_with_issue=3, scanned=500, errors=["2026-10-06: HTTP 500"])
    status, reason = sync.judge(partial)
    assert status == "success" and reason.startswith("partial")
