"""The daily OJ update of docs/LEG_2026-10 (Victor, 20 Oct 2026): each new legal act gets the export's folder, the
ledger records every decision, and the table carries a source column.

Cellar is replaced by fakes: the tests build a small dump, run the script on it and read what it wrote.
"""
import csv
import io
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND.parent))

from backend.scripts import update_leg_from_oj as u  # noqa: E402

D1, D2 = date(2026, 10, 14), date(2026, 10, 15)
CDM = "http://publications.europa.eu/ontology/cdm#"


def rdf(celex, title="A title", lang="ENG"):
    m = __import__("re").match(r"(\d)(\d{4})([A-Z]+)(\d+)", celex)
    return (f'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:j.0="{CDM}">'
            f'<rdf:Description rdf:about="http://publications.europa.eu/resource/cellar/w">'
            f"<j.0:resource_legal_id_celex>{celex}</j.0:resource_legal_id_celex>"
            f"<j.0:resource_legal_id_sector>{m[1]}</j.0:resource_legal_id_sector>"
            f"<j.0:resource_legal_year>{m[2]}</j.0:resource_legal_year>"
            f"<j.0:resource_legal_type>{m[3]}</j.0:resource_legal_type>"
            f"<j.0:resource_legal_number_natural_celex>{int(m[4])}</j.0:resource_legal_number_natural_celex>"
            f"<j.0:work_date_document>2026-10-13</j.0:work_date_document></rdf:Description>"
            f'<rdf:Description rdf:about="http://publications.europa.eu/resource/cellar/w.0001">'
            f'<j.0:expression_uses_language rdf:resource="http://publications.europa.eu/resource/authority/language/{lang}"/>'
            f"<j.0:expression_title>{title}</j.0:expression_title></rdf:Description></rdf:RDF>").encode()


def formex_zip(names=("L_202602266EN.000101.fmx.xml", "L_202602266EN.doc.fmx.xml", "L_202602266EN.toc.fmx.xml")):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, "<ACT><TITLE><TI><P>An act</P></TI></TITLE></ACT>")
    return buf.getvalue()


def act(work, num, celex, lang3="ENG", fmts=("fmx4", "xhtml")):
    return {"work": f"http://publications.europa.eu/resource/cellar/{work}", "oj_id": f"L_2026{num:05d}", "celex": celex,
            "lang3": lang3, "language": "en" if lang3 == "ENG" else "de", "fmts": {f: "m" for f in fmts}, "title": "t"}


@pytest.fixture
def world(tmp_path, monkeypatch):
    dump, out = tmp_path / "docs" / "LEG_2026-10", tmp_path / "table"
    dump.mkdir(parents=True)
    out.mkdir()
    (dump / "w-export").mkdir()
    (dump / "w-export" / "tree_non_inferred.rdf").write_bytes(rdf("32026R0001"))
    with (out / "leg_2026-10_table.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["CELEX", "Title of document"])
        w.writerows([["32026R0001", "x"], ["32026R0002", "y"]])
    days = {D1: [act("w-new", 2266, "32026R2266"),           # a new English act: added with its Formex
                 act("w-agr", 2305, "22026A02305"),          # an international agreement: skipped
                 act("w-pend", 2311, None),                  # no CELEX yet: pending
                 act("w-corr", 90870, "32026R1753R(02)", lang3="DEU"),  # corrigendum without English: metadata only
                 act("w-export", 2241, "32026R0001"),        # its folder is in the export: already
                 act("w-other", 2242, "32026R0002"),         # its CELEX is in the export under another folder
                 act("w-bad", 2243, "32026R2243"),           # the metadata states another CELEX: error
                 act("w-evil", 2244, "32026R2244")],         # a zip with a path in it: error
            D2: [act("w-next", 2300, "32026D2300")]}
    rdfs = {"w-new": rdf("32026R2266"), "w-corr": rdf("32026R1753R(02)", lang="DEU"), "w-bad": rdf("32026R9999"),
            "w-evil": rdf("32026R2244"), "w-next": rdf("32026D2300"), "w-pend": rdf("32026R2311")}
    zips = {"w-new": formex_zip(), "w-evil": formex_zip(("../evil.xml",)), "w-next": formex_zip(("L_202602300EN.000101.fmx.xml",)),
            "w-pend": formex_zip(("L_202602311EN.000101.fmx.xml",))}
    calls = {"rebuild": 0, "formex": []}
    monkeypatch.setattr(u, "publication_days", lambda since, today: [d for d in sorted(days) if since <= d <= today])
    monkeypatch.setattr(u, "list_day", lambda d: [dict(a) for a in days[d]])
    monkeypatch.setattr(u, "fetch_rdf", lambda w: rdfs.get(w))
    monkeypatch.setattr(u, "fetch_formex", lambda w: calls["formex"].append(w) or zips.get(w))
    monkeypatch.setattr(u, "rebuild", lambda dump_, out_: calls.__setitem__("rebuild", calls["rebuild"] + 1))
    return dump, out, days, calls


def ledger(out):
    with (out / u.LEDGER).open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def test_each_publication_gets_the_exports_folder_or_a_recorded_reason(world):
    dump, out, days, calls = world
    rc = u.run(dump, out, apply=True, today=D2, since=D1)
    assert rc == 1  # two errors (w-bad, w-evil): the run must not read as a success
    st = {r["work_id"]: r["status"] for r in ledger(out)}
    assert st == {"w-new": "added", "w-agr": "skipped", "w-pend": "pending", "w-corr": "added", "w-export": "already",
                  "w-other": "already", "w-bad": "error", "w-evil": "error", "w-next": "added"}
    new = dump / "w-new"
    assert u.rdf_celexes((new / "tree_non_inferred.rdf").read_bytes()) == {"32026R2266"}
    assert sorted(p.name for p in (new / "fmx4").iterdir()) == [
        "L_202602266EN.000101.fmx.xml", "L_202602266EN.doc.fmx.xml", "L_202602266EN.toc.fmx.xml"]
    marker = json.loads((new / u.SOURCE_FILE).read_text())
    assert (marker["source"], marker["oj_date"], marker["oj_id"], marker["celex"]) == ("OJ daily", "2026-10-14", "L_202602266", "32026R2266")
    assert not (dump / "w-corr" / "fmx4").exists() and (dump / "w-corr" / "tree_non_inferred.rdf").exists()
    assert "w-corr" not in calls["formex"]  # no English version: Formex is not even asked for
    for gone in ("w-agr", "w-pend", "w-bad", "w-evil", "w-other"):
        assert not (dump / gone).exists(), gone
    assert not list((dump.parent / ".leg_oj_tmp").glob("*"))  # nothing half-built is left behind
    assert calls["rebuild"] == 1


def test_the_next_run_finishes_what_was_pending_and_does_not_repeat_final_rows(world):
    dump, out, days, calls = world
    u.run(dump, out, apply=True, today=D2, since=D1)
    n_rows = len(ledger(out))
    days[D1][2]["celex"] = "32026R2311"  # Cellar has assigned the CELEX since
    u.run(dump, out, apply=True, today=D2, since=D1, recheck_days=0)
    rows = ledger(out)
    assert (dump / "w-pend" / "fmx4" / "L_202602311EN.000101.fmx.xml").exists()
    latest = u.latest_status(rows)
    assert latest[("2026-10-14", "L_202602311")]["status"] == "added"
    # final rows (added, already, skipped) are not written twice; pending and errors are written again
    assert len(rows) - n_rows == 3  # w-pend added, w-bad and w-evil error again
    assert calls["rebuild"] == 2


def test_a_dry_run_writes_nothing(world):
    dump, out, days, calls = world
    before = sorted(p.name for p in dump.iterdir())
    assert u.run(dump, out, apply=False, today=D2, since=D1) == 0
    assert sorted(p.name for p in dump.iterdir()) == before
    assert not (out / u.LEDGER).exists() and calls["rebuild"] == 0


def test_a_backfill_day_left_open_is_read_again_after_the_default_start(world, monkeypatch):
    dump, out, days, calls = world
    u.run(dump, out, apply=True, today=D2, since=D1)  # one-off backfill from D1, leaving w-pend and errors open
    # D2 is done; D1, before the new start, still has a pending publication and two errors
    assert u.days_to_read(ledger(out), D2, D2, recheck_days=0, max_days=31) == [D1]


def test_a_formex_zip_keeps_its_xml_files_and_leaves_the_figures_out(tmp_path):
    names = u.unpack_formex(formex_zip(("L_202602265EN.000101.fmx.xml", "L_202602265EN.000401.fmx.tif")), tmp_path)
    assert names == ["L_202602265EN.000101.fmx.xml"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["L_202602265EN.000101.fmx.xml"]


def test_a_formex_zip_with_a_path_or_a_hidden_name_is_refused(tmp_path):
    for bad in ("../x.xml", "sub/x.xml", ".hidden.xml", "../x.tif"):
        with pytest.raises(u.Fail):
            u.unpack_formex(formex_zip((bad,)), tmp_path)
    with pytest.raises(u.Fail):  # wrappers only: no act text
        u.unpack_formex(formex_zip(("L_1EN.doc.fmx.xml", "L_1EN.toc.fmx.xml")), tmp_path)


def test_the_table_says_where_each_row_comes_from(tmp_path, monkeypatch):
    xlsxwriter = pytest.importorskip("xlsxwriter")  # noqa: F841
    openpyxl = pytest.importorskip("openpyxl")
    from backend.scripts import build_leg_table as b
    dump, out = tmp_path / "dump", tmp_path / "out"
    for folder, celex, marker in (("w1", "32024R1689", None), ("w2", "32026R2266", "2026-10-14")):
        (dump / folder / "fmx4").mkdir(parents=True)
        (dump / folder / "tree_non_inferred.rdf").write_bytes(rdf(celex, "Regulation (EU) of the European Parliament and of the Council"))
        if marker:
            (dump / folder / b.SOURCE_FILE).write_text(json.dumps({"source": "OJ daily", "oj_date": marker}))
    out.mkdir()
    (out / "aliases.csv").write_text("celex,alias,acronym,source\n", encoding="utf-8")
    monkeypatch.setattr(b, "eurovoc_meta", lambda ids, cache: {"concept": {}, "mts": {}, "domains": {"12": "LAW"}})
    monkeypatch.setattr(b, "cellar_titles", lambda celexes, cache: {})
    monkeypatch.setattr(sys, "argv", ["build_leg_table.py", "--dump", str(dump), "--out", str(out)])
    b.main()
    with (out / "leg_2026-10_table.csv").open(newline="", encoding="utf-8-sig") as fh:
        rows = {r["CELEX"]: r for r in csv.DictReader(fh)}
    assert rows["32024R1689"]["source"] == "LEG_2026-10 export"
    assert rows["32026R2266"]["source"] == "OJ daily 2026-10-14"
    qa = json.loads((out / "qa.json").read_text())
    assert (qa["rows_from_export"], qa["rows_from_oj_daily"]) == (1, 1)
    wb = openpyxl.load_workbook(out / "leg_2026-10_table.xlsx")
    heads = [c.value for c in wb["Table"][1]]
    assert heads[-1] == "source"
    issuer = b.col_letter(len(heads))  # the kind sheets add the issuer after every Table column
    assert [c.value for c in wb["Regulations"][1]][len(heads)] == b.ISSUER_HEADER
    stats = [c.value for row in wb["Statistics"].iter_rows() for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    reg = [f for f in stats if "'Regulations'!" in f]
    assert reg and all(f"'Regulations'!${issuer}$" in f for f in reg), reg
    src = b.col_letter(heads.index("source"))
    assert any(f"Table'!${src}$" in f and "OJ daily*" in f for f in stats)
