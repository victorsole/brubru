"""Both funded-project loaders run in the weekly tier, and a run says what it did (23 Oct 2026).

Nothing ran either loader: CORDIS was last read on 6 May and the F&T Portal on 15 Jun, while the
endpoint said weekly. The CORDIS loader also read its database URL from a repo-root .env only
(Railway has none), reused a cached dump for as long as /tmp lived, and never moved scraped_at
on an update, so nothing recorded when a dump was last read.
"""
import asyncio
import csv
import datetime as dt
import importlib
import io
import pathlib
import re
import sys
import zipfile
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

cordis = importlib.import_module("ingest_cordis_projects")
nonh = importlib.import_module("ingest_ft_projects_nonh2020")


def test_the_weekly_tier_runs_the_loaders_then_the_status_rule_then_the_participants(monkeypatch):
    import api.cron as cron
    calls = []

    async def _fake(name, script, args=None, timeout=600):
        calls.append((name, script, list(args or []), timeout))
        return {"status": "success"}

    recorded = {}
    monkeypatch.setattr(cron, "_run_script_async", _fake)
    monkeypatch.setattr(cron, "_verify_cron_secret", lambda authorization: None)
    monkeypatch.setattr(cron, "_record_tier_results", lambda tier, results, keys: recorded.update(keys=set(keys)))
    asyncio.run(cron.cron_sync_weekly(authorization="x"))

    order = [c[0] for c in calls]
    assert order.index("cordis_projects") < order.index("ft_projects_nonh2020") \
        < order.index("project_status_weekly") < order.index("ft_participants")
    by_name = {c[0]: c for c in calls}
    assert by_name["cordis_projects"][1:3] == ("scripts/ingest_cordis_projects.py", ["--programme", "all", "--apply"])
    assert by_name["ft_projects_nonh2020"][1:3] == ("scripts/ingest_ft_projects_nonh2020.py", ["--apply"])
    assert by_name["project_status_weekly"][1:3] == ("scripts/refresh_project_status.py", ["--apply"])
    assert {"cordis_projects", "ft_projects_nonh2020", "project_status_weekly"} <= recorded["keys"]
    for script in ("ingest_cordis_projects.py", "ingest_ft_projects_nonh2020.py"):   # the tier records them
        assert not re.search(r"record_run|sync_runs|--record", (BACKEND / "scripts" / script).read_text())


def test_cordis_reads_the_real_environment_first():
    sedia = importlib.import_module("ingest_funding_sedia")
    assert cordis.get_env is sedia.get_env


def _args(**kw):
    return SimpleNamespace(**{"force": False, "apply": True, "limit": 0, **kw})


def test_a_dump_already_read_is_skipped_and_a_newer_one_is_read(monkeypatch):
    read_at = dt.datetime(2026, 10, 8, 15, 42)
    saved = []
    monkeypatch.setattr(cordis, "last_read", lambda conn, programme: read_at)
    monkeypatch.setattr(cordis, "save_read", lambda conn, programme, modified, built, written: saved.append((programme, modified)))
    fetched = []
    monkeypatch.setattr(cordis, "download", lambda url, dest: fetched.append(url) or dest.write_bytes(b"x"))
    monkeypatch.setattr(cordis, "_read_dump", lambda programme, cache, conn, args: (7, 7))

    monkeypatch.setattr(cordis, "dump_modified", lambda url: dt.datetime(2026, 10, 8, 15, 42))
    assert cordis.ingest_dump("h2020", None, _args()) is None and fetched == [] and saved == []
    assert cordis.ingest_dump("h2020", None, _args(force=True)) == (7, 7) and len(fetched) == 1

    newer = dt.datetime(2026, 11, 6)
    monkeypatch.setattr(cordis, "dump_modified", lambda url: newer)
    assert cordis.ingest_dump("h2020", None, _args()) == (7, 7) and saved[-1] == ("h2020", newer)
    saved.clear()
    assert cordis.ingest_dump("h2020", None, _args(apply=False)) == (7, 7) and saved == []   # a dry run saves nothing


def test_a_read_cut_short_records_nothing_so_the_next_run_reads_the_dump_again(monkeypatch):
    saved = []
    monkeypatch.setattr(cordis, "last_read", lambda conn, programme: None)
    monkeypatch.setattr(cordis, "save_read", lambda *a: saved.append(a))
    monkeypatch.setattr(cordis, "dump_modified", lambda url: dt.datetime(2026, 11, 6))
    monkeypatch.setattr(cordis, "download", lambda url, dest: dest.write_bytes(b"x"))

    def _killed(programme, cache, conn, args):
        raise ConnectionError("server closed the connection")
    monkeypatch.setattr(cordis, "_read_dump", _killed)
    try:
        cordis.ingest_dump("horizon", None, _args())
    except ConnectionError:
        pass
    assert saved == []
    monkeypatch.setattr(cordis, "_read_dump", lambda programme, cache, conn, args: (0, 0))
    cordis.ingest_dump("horizon", None, _args())
    assert saved == []                                                  # an empty read is no read


def test_every_read_stamps_scraped_at_on_both_loaders():
    for sql in (cordis._UPSERT_SQL, nonh.UPSERT):
        conflict = " ".join(sql.split("ON CONFLICT", 1)[1].split())
        assert re.search(r"\bscraped_at\s*=\s*NOW\(\)", conflict)


def _zip(path, n):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["id", "title", "status", "startDate", "endDate"], delimiter=";")
    w.writeheader()
    for i in range(n):
        w.writerow({"id": str(100000 + i), "title": f"Project {i}", "status": "SIGNED",
                    "startDate": "2025-01-01", "endDate": "2028-12-31"})
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("project.csv", buf.getvalue())


def test_the_dump_is_written_batch_by_batch_while_it_is_read(monkeypatch, tmp_path):
    for name in ("load_coordinator_map", "load_full_org_map"):
        monkeypatch.setattr(cordis, name, lambda z: {})
    monkeypatch.setattr(cordis, "_csv_groupby", lambda z, member, key: {})
    batches = []
    monkeypatch.setattr(cordis, "_write", lambda conn, chunk: batches.append(len(chunk)) or len(chunk) - (chunk[0]["project_id"] == "100400"))
    _zip(tmp_path / "d.zip", 450)
    assert cordis._read_dump("h2020", tmp_path / "d.zip", None, _args()) == (450, 449)
    assert batches == [200, 200, 50]
    batches.clear()
    assert cordis._read_dump("h2020", tmp_path / "d.zip", None, _args(apply=False)) == (450, 0) and batches == []


def _cordis_main(monkeypatch, capsys, outcomes):
    monkeypatch.setattr(cordis, "get_env", lambda key: "postgresql://ci")
    monkeypatch.setattr(cordis.psycopg2, "connect", lambda url: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(cordis, "ingest_dump", lambda programme, conn, args: outcomes[programme])
    code = cordis.main(["--programme", "all", "--apply"])
    return code, capsys.readouterr().out


def test_cordis_fails_on_an_empty_read_and_reports_unwritten_projects(monkeypatch, capsys):
    code, out = _cordis_main(monkeypatch, capsys, {"horizon": (20000, 20000), "h2020": None, "fp7": None})
    assert code == 0 and "skipped=['fp7', 'h2020']" in out and "degraded" not in out
    code, out = _cordis_main(monkeypatch, capsys, {"horizon": (0, 0), "h2020": None, "fp7": None})
    assert code == 1 and "[ERROR]" in out
    code, out = _cordis_main(monkeypatch, capsys, {"horizon": (20000, 19998), "h2020": None, "fp7": None})
    assert code == 0 and "[SYNC_STATUS] degraded: projects not written {'horizon': 2}" in out


def test_the_portal_crawl_fails_when_it_writes_nothing_and_says_which_slices_were_refused(monkeypatch, capsys):
    monkeypatch.setattr(nonh, "crawl", lambda **kw: (0, ["2026 p1"]))
    assert nonh.main(["--apply"]) == 1 and "[ERROR] no project written" in capsys.readouterr().out
    monkeypatch.setattr(nonh, "crawl", lambda **kw: (27000, ["2019 p40"]))
    assert nonh.main(["--apply"]) == 0
    assert "[SYNC_STATUS] degraded: the index refused 1 year slice(s): 2019 p40" in capsys.readouterr().out
    monkeypatch.setattr(nonh, "crawl", lambda **kw: (28000, []))
    assert nonh.main(["--apply"]) == 0 and "degraded" not in capsys.readouterr().out
    monkeypatch.setattr(nonh, "crawl", lambda **kw: None)
    assert nonh.main(["--probe"]) == 0
