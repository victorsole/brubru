"""Offline tests for the OEIL probe (services/scrapers/oeil_probe.py and scripts/oeil_probe_scan.py).

No network: pages are golden fixtures saved on 9 Oct 2026 and every HTTP exchange goes through
httpx.MockTransport. Time is injected, so no test sleeps.
"""
import csv
import gzip
import json
from pathlib import Path

import httpx
import pytest

from services.scrapers import oeil_probe as op
from services.scrapers.oeil_probe import (
    DEFAULT_BANDS,
    Band,
    OeilProber,
    ProbeBlocked,
    audit_targets,
    classify_response,
    cod_instrument,
    derive_bands,
    fetch_epod_union,
    normalise_label,
    numbers_by_band,
    parse_procedure,
    parse_ref,
    reconcile,
)

FIX = Path(__file__).parent / "fixtures" / "oeil_probe"


def page(name: str) -> str:
    with gzip.open(FIX / name, "rt", encoding="utf-8") as fh:
        return fh.read()


NOT_FOUND = (FIX / "not_found_404.json").read_text(encoding="utf-8")


# ------------------------------------------------------------------ parsing (golden pages)


def test_parse_cod_page():
    rec = parse_procedure(page("cod_2026_0265.html.gz"))
    assert rec["ref"] == "2026/0265(COD)"
    assert rec["title"] == "Public Procurement Act"
    assert rec["type_code"] == "COD"
    assert rec["type_label"].startswith("Ordinary legislative procedure")
    assert rec["instrument"] == "Regulation"
    assert rec["subject"].startswith("2.10.02")
    assert rec["status"] == "Preparatory phase in Parliament"


def test_parse_cod_directive_keeps_instrument_first_and_links_after():
    rec = parse_procedure(page("cod_2026_0012.html.gz"))
    assert rec["ref"] == "2026/0012(COD)"
    assert rec["instrument"] == "Directive"
    assert any(e.startswith("Amending Directive") for e in rec["extras"][1:])


@pytest.mark.parametrize("name,ref,code", [
    ("nle_2026_0041.html.gz", "2026/0041(NLE)", "NLE"),
    ("ini_2026_2003.html.gz", "2026/2003(INI)", "INI"),
    ("imm_2026_2030.html.gz", "2026/2030(IMM)", "IMM"),
])
def test_parse_non_cod_pages_have_type_title_and_no_instrument(name, ref, code):
    rec = parse_procedure(page(name))
    assert rec["ref"] == ref and rec["type_code"] == code
    assert rec["title"]
    assert rec["instrument"] is None


def test_key_events_motions_and_texts_of_an_adopted_resolution():
    rec = parse_procedure(page("rsp_adopted_2026_2565.html.gz"))
    assert rec["type_code"] == "RSP" and rec["status"] == "Procedure completed"
    events = [(e["date"], e["event"], e["reference"]) for e in rec["key_events"]]
    assert events == [("2026-01-20", "Debate in Parliament", ""),
                      ("2026-01-22", "Decision by Parliament", "T10-0023/2026"),
                      ("2026-01-22", "Results of vote in Parliament", "")]
    assert rec["text_refs"] == ["T10-0023/2026"]
    assert "B10-0069/2026" in rec["motion_refs"] and len(rec["motion_refs"]) >= 3


def test_a_debate_only_resolution_has_no_motion_and_no_decision():
    rec = parse_procedure(page("rsp_debate_only_2026_2561.html.gz"))
    names = [e["event"] for e in rec["key_events"]]
    assert names == ["Debate in Parliament", "End of procedure in Parliament"]
    assert rec["motion_refs"] == [] and rec["text_refs"] == []


def test_a_page_without_a_key_events_table_gives_an_empty_list():
    assert parse_procedure("<html><title>Procedure File: 2026/0001(BUD) | x</title><h2>2026/0001(BUD)</h2></html>")["key_events"] == []


def test_parse_page_that_is_not_a_procedure_gives_no_ref():
    assert parse_procedure("<html><title>Something else</title></html>")["ref"] is None


@pytest.mark.parametrize("raw,expected", [
    ("Regulation", "Regulation"), ("Directive", "Directive"), ("Decision", "Decision"),
    ("Regulation, Directive", "Regulation"), ("Recommendation", "Other: Recommendation"),
    (None, "Not stated"), ("", "Not stated"),
])
def test_cod_instrument(raw, expected):
    assert cod_instrument(raw) == expected


@pytest.mark.parametrize("status,text,kind", [
    (200, "<html>", "hit"),
    (404, NOT_FOUND, "miss"),
    (404, "<html>Not Found</html>", "anomaly"),   # a 404 WITHOUT OEIL's message is not a miss
    (403, "challenge", "anomaly"),
    (202, "", "anomaly"),
    (500, NOT_FOUND, "anomaly"),
])
def test_classify_response(status, text, kind):
    assert classify_response(status, text) == kind


def test_normalise_label_drops_the_r_suffix_only():
    assert normalise_label("2026/0182R(NLE)") == "2026/0182(NLE)"
    assert normalise_label("2026/0182(NLE)") == "2026/0182(NLE)"
    assert normalise_label("2026/2001(GBD)") == "2026/2001(GBD)"


def test_parse_ref():
    assert parse_ref("2026/0265(COD)") == (2026, 265, "COD")
    assert parse_ref("2026/0182R(NLE)") is None
    assert parse_ref("") is None


# ------------------------------------------------------------------ prober (mock transport, fake time)


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def make_prober(handler, **kw):
    t = FakeTime()
    client = httpx.Client(transport=httpx.MockTransport(handler))
    kw.setdefault("retry_delays", (1, 2, 3))
    return OeilProber(client=client, sleep=t.sleep, clock=t.clock, **kw), t


def ref_of(request: httpx.Request) -> str:
    return request.url.params["reference"]


def test_probe_hit_and_miss():
    def handler(req):
        if ref_of(req) == "2026/0265(COD)":
            return httpx.Response(200, text=page("cod_2026_0265.html.gz"))
        return httpx.Response(404, text=NOT_FOUND)

    p, _ = make_prober(handler)
    hit = p.probe("2026/0265(COD)")
    assert hit.kind == "hit" and hit.record["title"] == "Public Procurement Act"
    assert p.probe("2026/0265(CNS)").kind == "miss"
    assert p.requests == 2


def test_probe_stops_on_a_wall_and_never_reads_it_as_a_miss():
    p, _ = make_prober(lambda req: httpx.Response(403, text="<title>Browser check</title>"))
    with pytest.raises(ProbeBlocked):
        p.probe("2026/0001(COD)")


def test_probe_404_without_oeils_message_is_blocked():
    p, _ = make_prober(lambda req: httpx.Response(404, text="<html>nginx 404</html>"))
    with pytest.raises(ProbeBlocked):
        p.probe("2026/0001(COD)")


def test_probe_200_for_a_different_reference_is_blocked():
    p, _ = make_prober(lambda req: httpx.Response(200, text=page("cod_2026_0265.html.gz")))
    with pytest.raises(ProbeBlocked):
        p.probe("2026/0999(COD)")


def test_probe_backs_off_on_429_then_succeeds():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(429) if calls["n"] == 1 else httpx.Response(404, text=NOT_FOUND)

    p, t = make_prober(handler, pace=0)
    assert p.probe("2026/0001(COD)").kind == "miss"
    assert 1 in t.sleeps and calls["n"] == 2


def test_probe_gives_up_after_the_retries_on_persistent_503():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        return httpx.Response(503)

    p, _ = make_prober(handler, pace=0)
    with pytest.raises(ProbeBlocked):
        p.probe("2026/0001(COD)")
    assert calls["n"] == 4        # first try + three retries


def test_probe_transport_errors_are_retried_then_blocked():
    def handler(req):
        raise httpx.ConnectError("boom")

    p, _ = make_prober(handler, pace=0)
    with pytest.raises(ProbeBlocked):
        p.probe("2026/0001(COD)")


def test_sweep_tries_types_in_order_and_stops_at_the_first_hit():
    seen = []

    def handler(req):
        seen.append(ref_of(req))
        if ref_of(req) == "2026/0041(NLE)":
            return httpx.Response(200, text=page("nle_2026_0041.html.gz"))
        return httpx.Response(404, text=NOT_FOUND)

    p, _ = make_prober(handler, pace=0)
    res = p.sweep(2026, 41, ("COD", "NLE", "BUD"))
    assert res.ref == "2026/0041(NLE)"
    assert seen == ["2026/0041(COD)", "2026/0041(NLE)"]        # BUD never asked
    assert p.sweep(2026, 42, ("COD",)) is None


def test_pacing_waits_between_requests():
    p, t = make_prober(lambda req: httpx.Response(404, text=NOT_FOUND), pace=0.35)
    p.probe("2026/0001(COD)")
    p.probe("2026/0002(COD)")
    assert 0.35 in [round(s, 2) for s in t.sleeps]


# ------------------------------------------------------------------ bands and planning


def test_default_bands_cover_the_observed_series_without_overlap():
    names = [b.name for b in DEFAULT_BANDS]
    assert names == ["proposals", "appointments", "parliament", "resolutions"]
    ranges = [(b.lo, b.hi) for b in DEFAULT_BANDS]
    assert all(a[1] < b[0] for a, b in zip(ranges, ranges[1:]))


def test_derive_bands_adds_a_type_only_when_seen_twice():
    refs = ["2026/2600(COD)", "2025/2650(COD)", "2025/2700(GBD)"]     # COD twice in 2500+, GBD once
    bands = {b.name: b for b in derive_bands(refs)}
    assert "COD" in bands["resolutions"].types
    assert "GBD" not in bands["resolutions"].types
    assert bands["proposals"].types[:2] == DEFAULT_BANDS[0].types[:2]


def test_derive_bands_orders_known_types_by_frequency():
    refs = ["2026/0010(NLE)", "2026/0011(NLE)", "2026/0012(NLE)", "2026/0013(COD)"]
    types = {b.name: b for b in derive_bands(refs)}["proposals"].types
    assert types.index("NLE") < types.index("COD")


def test_numbers_by_band_filters_by_year():
    out = numbers_by_band(["2026/0010(COD)", "2025/0011(COD)", "2026/2600(RSP)", "2026/0850(NLE)"], 2026)
    assert out["proposals"] == {10} and out["resolutions"] == {2600} and out["appointments"] == {850}


def test_audit_targets_frontier_comes_first_and_never_probes_a_held_number():
    known = {"proposals": {1, 2, 3, 5}, "appointments": set(), "parliament": {2000, 2001}, "resolutions": {2500}}
    t = audit_targets(known, DEFAULT_BANDS, request_budget=200, day_ordinal=0, frontier_span=5)
    probed = [n for n, _ in t]
    first = probed[:5]
    assert first == [6, 7, 8, 9, 10]                  # just above the highest held proposal number
    for held in (1, 2, 3, 5, 2000, 2001, 2500):
        assert held not in probed
    assert len(set(probed)) == len(probed)


def test_a_small_budget_still_looks_above_the_highest_held_number_in_every_band():
    known = {"proposals": {308}, "appointments": {901}, "parliament": {2127}, "resolutions": {2925}}
    t = audit_targets(known, DEFAULT_BANDS, request_budget=150, day_ordinal=0, frontier_span=40)
    probed = {n for n, _ in t}
    assert 309 in probed and 902 in probed and 2128 in probed and 2926 in probed
    assert sum(len(types) for _, types in t) <= 150


def test_audit_targets_respect_the_request_budget():
    t = audit_targets({"proposals": {1}}, DEFAULT_BANDS, request_budget=60, day_ordinal=3, frontier_span=10)
    cost = sum(len(types) for _, types in t)
    assert 0 < cost <= 60


def test_audit_window_rotates_with_the_day():
    known = {"proposals": {50}, "appointments": {850}, "parliament": {2100}, "resolutions": {2900}}
    a = audit_targets(known, DEFAULT_BANDS, request_budget=300, day_ordinal=10, frontier_span=2)
    b = audit_targets(known, DEFAULT_BANDS, request_budget=300, day_ordinal=11, frontier_span=2)
    assert {n for n, _ in a} != {n for n, _ in b}


def test_audit_window_covers_every_unheld_number_over_enough_days():
    bands = (Band("only", 1, 30, ("COD",)),)
    known = {"only": {30}}
    covered = set()
    for day in range(6):
        covered |= {n for n, _ in audit_targets(known, bands, request_budget=10, day_ordinal=day, frontier_span=1)}
    assert set(range(1, 30)) <= covered


def test_reconcile():
    r = reconcile(["2026/0001(BUD)", "2026/2560(RSP)"], ["2026/0001(BUD)", "2026/0009(COD)"])
    assert r["on_oeil_not_held"] == ["2026/2560(RSP)"] and r["held_and_on_oeil"] == ["2026/0001(BUD)"]


# ------------------------------------------------------------------ EP Open Data list (unstable paging)


def _epod_handler(datasets, total):
    """datasets: {page_size: [labels returned for that size, in order]}"""
    def handler(req):
        size, offset = int(req.url.params["limit"]), int(req.url.params["offset"])
        labels = datasets[size][offset:offset + size]
        return httpx.Response(200, json={"data": [{"label": l} for l in labels], "meta": {"total": total}})
    return handler


def test_epod_union_recovers_labels_one_paging_run_drops():
    full = [f"2026/{n:04d}(COD)" for n in range(1, 11)]
    datasets = {
        100: full[:8] + [full[0]],            # a duplicate row and two labels missing
        50: full[2:] + [full[2]],
        37: full[:3] + full[6:],
        29: full[:10],
    }
    client = httpx.Client(transport=httpx.MockTransport(_epod_handler(datasets, 10)))
    labels, total = fetch_epod_union(2026, client=client, sleep=lambda s: None, page_pause=0)
    assert total == 10 and labels == set(full)


def test_epod_retries_a_429_and_an_error_body():
    answers = iter([httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json={"error": "backend"}),
                    httpx.Response(200, json={"data": [{"label": "2026/0001(BUD)"}], "meta": {"total": 1}})])
    sleeps = []
    client = httpx.Client(transport=httpx.MockTransport(lambda req: next(answers)))
    labels, total = fetch_epod_union(2026, page_sizes=(100,), client=client, sleep=sleeps.append, page_pause=0)
    assert labels == {"2026/0001(BUD)"} and total == 1
    assert 7 in sleeps and 15 in sleeps


def test_epod_gives_up_loudly_instead_of_returning_an_empty_list():
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, json={"error": "down"})))
    with pytest.raises(ProbeBlocked):
        fetch_epod_union(2026, page_sizes=(100,), client=client, sleep=lambda s: None, page_pause=0)


# ------------------------------------------------------------------ the script: exit codes and outputs


from scripts import oeil_probe_scan as scan  # noqa: E402  (plain import: a broken script must FAIL in CI, not skip)


class FakeProber:
    """Stands in for OeilProber: `existing` maps number -> (type, title)."""
    existing = {}
    blocked = False

    def __init__(self, **kw):
        self.requests = 0

    def sweep(self, year, number, types):
        if FakeProber.blocked:
            raise ProbeBlocked("wall")
        self.requests += len(types)
        if number in FakeProber.existing:
            t, title = FakeProber.existing[number]
            return op.ProbeResult(f"{year}/{number:04d}({t})", "hit",
                                  {"title": title, "type_code": t, "type_label": "x", "instrument": "Regulation",
                                   "subject": "s", "status": "st", "extras": []})
        return None

    def probe(self, ref):
        p = parse_ref(ref)
        if p and p[1] in FakeProber.existing and FakeProber.existing[p[1]][0] == p[2]:
            return op.ProbeResult(ref, "hit", {"title": "listed", "type_code": p[2]})
        return op.ProbeResult(ref, "miss")


@pytest.fixture
def fake(monkeypatch):
    FakeProber.existing, FakeProber.blocked = {}, False
    monkeypatch.setattr(scan, "OeilProber", FakeProber)
    return FakeProber


def audit_args(**kw):
    base = dict(mode="audit", year=2026, out=None, pace=0, max_seconds=60, max_requests=100, numbers="1-6",
                day_ordinal=0, tail_gap=100, no_epod=True)
    base.update(kw)
    return type("A", (), base)()


def test_audit_reports_a_gap_with_exit_1_and_names_it_on_stderr(fake, monkeypatch, capsys):
    tracked = {"2026/0001(BUD)", "2025/0002(COD)"}          # BUD and COD are types some table holds
    monkeypatch.setattr(scan, "load_brubru_refs", lambda year: ({"2026/0001(BUD)"}, set(), tracked))
    fake.existing = {1: ("BUD", "held one"), 4: ("COD", "A new procedure")}
    assert scan.run_audit(audit_args()) == 1
    err = capsys.readouterr().err
    assert "[GAP]" in err and "2026/0004(COD)" in err and "A new procedure" in err
    assert "2026/0001(BUD)" not in err.replace("summary", "")          # a held procedure is not a gap


def test_audit_clean_run_exits_0(fake, monkeypatch, capsys):
    monkeypatch.setattr(scan, "load_brubru_refs", lambda year: ({"2026/0001(BUD)"}, set(), {"2026/0001(BUD)"}))
    fake.existing = {1: ("BUD", "held one")}
    assert scan.run_audit(audit_args()) == 0
    assert "[OK]" in capsys.readouterr().out


def test_audit_blocked_is_exit_2(fake, monkeypatch, capsys):
    monkeypatch.setattr(scan, "load_brubru_refs", lambda year: (set(), set(), set()))
    fake.blocked = True
    assert scan.run_audit(audit_args()) == 2
    assert "[ERROR]" in capsys.readouterr().err


def test_audit_that_plans_nothing_fails_instead_of_passing(fake, monkeypatch, capsys):
    monkeypatch.setattr(scan, "load_brubru_refs", lambda year: (set(), set(), set()))
    monkeypatch.setattr(scan, "audit_targets", lambda *a, **k: [])
    assert scan.run_audit(audit_args(numbers=None)) == 2


def test_full_scan_writes_csv_and_summary_and_exits_0(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(scan, "DEFAULT_BANDS", (Band("a", 1, 5, ("COD",)), Band("b", 2000, 2003, ("INI",))))
    monkeypatch.setattr(scan, "fetch_epod_union", lambda year: ({"2026/0002(COD)", "2026/2001(INI)", "2026/2002(GBD)"}, 3))
    fake.existing = {2: ("COD", "Law one"), 2001: ("INI", "Report one")}
    out = tmp_path / "o"
    rc = scan.run_full(audit_args(mode="full", out=str(out), numbers=None, no_epod=False, tail_gap=10))
    assert rc == 0
    rows = list(csv.DictReader(open(out / "oeil_2026_procedures.csv", encoding="utf-8-sig")))
    assert [r["procedure_ref"] for r in rows] == ["2026/0002(COD)", "2026/2001(INI)"]
    assert rows[0]["cod_instrument"] == "Regulation" and rows[1]["cod_instrument"] == ""
    assert set(("key_events", "motion_refs", "text_refs")) <= set(rows[0])
    feed = json.loads((out / "oeil_2026_procedures.json").read_text())
    assert [f["procedure_ref"] for f in feed] == ["2026/0002(COD)", "2026/2001(INI)"]
    assert all(f["state"] == "served" for f in feed)
    summary = json.loads((out / "oeil_2026_probe_summary.json").read_text())
    assert summary["procedures_found"] == 2
    assert summary["listed_but_not_served_by_oeil"] == ["2026/2002(GBD)"]
    assert (out / "summary.md").read_text().startswith("## OEIL probe 2026")


def test_full_scan_exits_1_when_the_list_probe_finds_what_the_scan_missed(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(scan, "DEFAULT_BANDS", (Band("a", 1, 5, ("COD",)),))
    fake.existing = {2: ("COD", "Law one")}
    # the EP list names a procedure of another type in the scanned series: the scan (COD only) misses it
    monkeypatch.setattr(scan, "fetch_epod_union", lambda year: ({"2026/0002(COD)", "2026/0004(NLE)"}, 2))
    FakeProber.existing[4] = ("NLE", "Found by label")
    monkeypatch.setattr(FakeProber, "sweep", lambda self, y, n, types: op.ProbeResult(f"{y}/{n:04d}(COD)", "hit",
                        {"title": "Law one", "type_code": "COD", "instrument": "Regulation", "extras": []}) if n == 2 else None)
    rc = scan.run_full(audit_args(mode="full", out=str(tmp_path), numbers=None, no_epod=False, tail_gap=10))
    assert rc == 1


def test_full_scan_that_finds_nothing_exits_2(fake, monkeypatch, tmp_path):
    monkeypatch.setattr(scan, "DEFAULT_BANDS", (Band("a", 1, 5, ("COD",)),))
    assert scan.run_full(audit_args(mode="full", out=str(tmp_path), numbers=None, no_epod=True, tail_gap=10)) == 2


def test_split_gaps_by_held_type():
    tracked = ["2025/0001(COD)", "2026/2500(RSP)"]
    counted, untracked = op.split_gaps_by_held_type(
        ["2026/0002(COD)", "2026/2002(INS)", "2026/2501(RSP)", "2026/2001(GBD)"], tracked)
    assert counted == ["2026/0002(COD)", "2026/2501(RSP)"]
    assert untracked == ["2026/2002(INS)", "2026/2001(GBD)"]


def test_split_gaps_counts_a_type_again_the_day_a_table_holds_it():
    assert op.split_gaps_by_held_type(["2026/2002(INS)"], ["2025/2005(INS)"]) == (["2026/2002(INS)"], [])


def test_audit_does_not_degrade_on_a_type_no_table_holds(fake, monkeypatch, capsys):
    monkeypatch.setattr(scan, "load_brubru_refs", lambda year: ({"2026/0001(BUD)"}, set(), {"2026/0001(BUD)"}))
    fake.existing = {1: ("BUD", "held one"), 2: ("INS", "Motion of censure")}
    assert scan.run_audit(audit_args(numbers="1-3")) == 0
    cap = capsys.readouterr()
    assert "[GAP]" not in cap.err
    assert "no Brubru table holds" in cap.out and "2026/0002(INS)" in cap.out


def test_audit_lists_an_untracked_type_apart_and_still_degrades_on_a_real_gap(fake, monkeypatch, capsys):
    tracked = {"2026/0001(BUD)", "2025/0009(COD)"}
    monkeypatch.setattr(scan, "load_brubru_refs", lambda year: ({"2026/0001(BUD)"}, set(), tracked))
    fake.existing = {1: ("BUD", "held one"), 2: ("INS", "Motion of censure"), 4: ("COD", "A new procedure")}
    assert scan.run_audit(audit_args(numbers="1-5")) == 1
    cap = capsys.readouterr()
    assert "2026/0004(COD)" in cap.err and "2026/0002(INS)" not in cap.err
    assert "2026/0002(INS)" in cap.out


def test_the_audit_is_registered_as_an_audit_with_a_budget_inside_its_timeout():
    """Drop is_audit and the cron records every gap as a failed job, forever red; a budget past the
    timeout would kill the run mid-probe. Both were the failure modes of ep_council_gaps."""
    from services.sync.source_registry import MEUB_SOURCES as SOURCES

    spec = next(s for s in SOURCES if s.key == "oeil_probe_audit")
    assert spec.is_audit and spec.tier == "warm" and spec.script == "scripts/oeil_probe_scan.py"
    assert spec.args[:2] == ("--mode", "audit")
    max_seconds = int(spec.args[spec.args.index("--max-seconds") + 1])
    assert max_seconds + 120 <= spec.timeout
    assert (Path(scan.__file__).parent.parent / spec.script).exists()
    keys = [s.key for s in SOURCES if s.tier == "warm"]
    # It compares against what the OEIL sync just wrote, so it must run AFTER it in the tier's order.
    assert keys.index("oeil_probe_audit") > keys.index("oeil_carriages")
    assert keys.index("oeil_probe_audit") > keys.index("oeil_roles")


def test_the_script_never_imports_a_database_writer():
    src = Path(scan.__file__).read_text()
    assert "SET TRANSACTION READ ONLY" in src
    for banned in (".commit()", "INSERT INTO", "UPDATE ", "DELETE FROM", "session.add"):
        assert banned not in src
