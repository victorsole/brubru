"""Delegated acts carry what the RegDel register says about their scrutiny (14 Oct 2026).

/legislative/delegated-acts documented an objection deadline, Parliament and Council
scrutiny and the parent procedure, and served none of them on any of its 2,162 acts; 43
of the 49 adopted acts had no adoption date, and the parent act came from a regex that
took an act named inside the basic act's title on 47 acts. The register's own API has
all of it except the day scrutiny starts, so the deadline is served as a floor."""
from __future__ import annotations

import pathlib
from datetime import date, datetime

from scripts import ingest_regdel_acts as job

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _ms(y, m, d):
    """Midnight in Brussels, as the register writes it: 22:00 or 23:00 UTC the day before."""
    from zoneinfo import ZoneInfo
    return int(datetime(y, m, d, tzinfo=ZoneInfo("Europe/Brussels")).timestamp() * 1000)


def _ev(kind, y, m, d, who="INSTITUTION_COMMISSION", months=None):
    e = {"eventType": kind, "eventInstitution": who, "eventDate": _ms(y, m, d), "deadline": None}
    if months is not None:
        e["deadline"] = {"deadlineType": "EXTENDEND", "deadlineRaw": float(months)}
    return e


def test_a_register_time_is_read_as_the_brussels_day():
    # 1785189600000 is C(2026)5161's adoption: 27 Jul 22:00 UTC, 28 Jul in Brussels.
    assert job.event_day(1785189600000) == date(2026, 7, 28)
    assert job.event_day(_ms(2026, 3, 1)) == date(2026, 3, 1)


def test_the_floor_is_adoption_plus_period():
    s = job.scrutiny_from_events([_ev("DA_ADOPTION", 2026, 7, 13)], "2", "adopted")
    assert s["adoption_date"] == date(2026, 7, 13)
    assert s["objection_deadline_earliest"] == date(2026, 9, 13)
    assert s["ep_scrutiny"] == dict.fromkeys(job.SCRUTINY_EVENTS.values()) | {"extension_months": None}


def test_an_extension_moves_the_floor_and_is_recorded_for_its_institution():
    s = job.scrutiny_from_events([
        _ev("DA_ADOPTION", 2023, 5, 2),
        _ev("DA_EXTENSION", 2023, 5, 25, "INSTITUTION_PARLIAMENT", months=2),
        _ev("DA_OBJECTION", 2023, 7, 11, "INSTITUTION_PARLIAMENT"),
    ], "2", "objected")
    assert s["objection_deadline_earliest"] == date(2023, 9, 2)
    assert s["ep_scrutiny"]["extension_requested"] == "2023-05-25"
    assert s["ep_scrutiny"]["extension_months"] == 2
    assert s["ep_scrutiny"]["objection"] == "2023-07-11"
    assert s["council_scrutiny"]["objection"] is None


def test_one_or_three_months_uses_the_shorter_and_a_month_end_is_clamped():
    s = job.scrutiny_from_events([_ev("DA_ADOPTION", 2026, 1, 31)], "1/3", "adopted")
    assert s["objection_deadline_earliest"] == date(2026, 2, 28)


def test_no_floor_when_scrutiny_closed_early_or_the_act_is_gone_or_the_period_is_unknown():
    both = [_ev("DA_ADOPTION", 2026, 3, 1),
            _ev("DA_EARLY_NON_OBJECTION", 2026, 3, 20, "INSTITUTION_PARLIAMENT"),
            _ev("DA_EARLY_NON_OBJECTION", 2026, 3, 25, "INSTITUTION_COUNCIL")]
    assert job.scrutiny_from_events(both, "2", "published")["objection_deadline_earliest"] is None
    one = both[:2]
    assert job.scrutiny_from_events(one, "2", "published")["objection_deadline_earliest"] == date(2026, 5, 1)
    assert job.scrutiny_from_events(both[:1], "2", "withdrawn")["objection_deadline_earliest"] is None
    assert job.scrutiny_from_events(both[:1], None, "adopted")["objection_deadline_earliest"] is None


def test_the_publication_event_gives_the_first_publication_date():
    s = job.scrutiny_from_events([_ev("DA_PUBLICATION", 2026, 9, 24), _ev("DA_ADOPTION", 2026, 7, 13)],
                                 "2", "published")
    assert s["publication_date"] == date(2026, 9, 24)


def _item(**kw):
    item = {"id": 3004, "cCode": "C(2026)3147", "completeTitle": "Commission Delegated Regulation (EU) 2026/1753",
            "delegatedActStatus": "PUBLISHED", "updateDate": 1790288441945, "summary": " Euro 7 battery rules ",
            "basicAct": {"celexNumber": "32018R0858", "procedureCode": "2016/0014/COD", "deadlineRaw": "2"}}
    item.update(kw)
    return item


def test_register_fields_normalise_the_procedure_and_keep_the_period_for_delegated_acts_only():
    f = job.register_fields(_item(), "delegated")
    assert f["parent_procedure_ref"] == "2016/0014(COD)"
    assert f["register_parent_celex"] == "32018R0858"
    assert f["scrutiny_period"] == "2" and f["description"] == "Euro 7 battery rules"
    assert f["status_urgent"] is False and f["regdel_id"] == 3004
    assert job.register_fields(_item(delegatedActStatus="PUBLISHED_URGENCY_PROCEDURE"), "delegated")["status_urgent"]
    impl = job.register_fields(_item(urgent=True), "implementing")
    assert impl["scrutiny_period"] is None and impl["status_urgent"] is False


def _record(**kw):
    r = {"act_type": "delegated", "reference": "C(2026)3147", "is_pipeline": False,
         "norm_title": "x", "parent_celex": "32009L0039"}
    r.update({k: None for k in ("regdel_id", "parent_procedure_ref", "description", "scrutiny_period",
                                "regdel_updated_at")})
    r.update(status_urgent=False, parent_from_register=False, celex=None)
    r.update(kw)
    return r


def test_enrich_replaces_the_regex_parent_and_matches_announced_acts_by_title():
    title = "COMMISSION DELEGATED REGULATION (EU) …/... amending Regulation (EU) 2019/2144 as regards x y z"
    planned = _record(reference="PLANNED:abc", is_pipeline=True, norm_title=job._normalised_title(title),
                      parent_celex=None)
    stray = _record(reference="C(2026)9999")
    items = {"delegated": [_item(), {"id": 7, "cCode": None, "completeTitle": title, "delegatedActStatus": "PLANNED",
                                     "basicAct": {"celexNumber": "32019R2144"}}]}
    records = [_record(), planned, stray]
    assert job.enrich(records, items) == 2
    assert records[0]["parent_celex"] == "32018R0858" and records[0]["regdel_id"] == 3004
    assert records[0]["parent_from_register"] is True
    assert planned["regdel_id"] == 7 and planned["parent_celex"] == "32019R2144"
    # Unmatched: nothing invented, the regex's value stays and may only fill an empty cell.
    assert stray["parent_celex"] == "32009L0039" and stray["regdel_id"] is None
    assert stray["parent_from_register"] is False


def test_the_upsert_writes_the_register_columns_without_blanking_them():
    import re
    src = (BACKEND / "scripts" / "ingest_regdel_acts.py").read_text(encoding="utf-8")
    flat = re.sub(r"\s+", " ", src)
    for col in ("regdel_id", "parent_procedure_ref", "description", "scrutiny_period", "regdel_updated_at"):
        assert f"{col} = COALESCE(EXCLUDED.{col}, secondary_acts.{col})" in flat, col
    # urgency_procedure has one writer, the events phase, never the upsert.
    assert "urgency_procedure = COALESCE" not in flat and "urgency_procedure = %(urgent)s" in flat
    # A regex parent never replaces a held one; a draft title never replaces a final one.
    assert "ELSE COALESCE(secondary_acts.parent_celex, EXCLUDED.parent_celex) END" in flat
    assert "AND secondary_acts.title !~" in flat
    # A run that cannot read the register still stores the export's rows and says so.
    assert "[SYNC_STATUS] degraded" in src


def test_the_change_signal_ignores_the_bookkeeping_columns():
    sql = (BACKEND / "migrations" / "291_secondary_acts_scrutiny.sql").read_text(encoding="utf-8")
    assert "'scraped_at,body_fetched_at,regdel_updated_at,regdel_events_read_for'" in sql


def test_the_api_serves_the_fields():
    from api.v1 import w4_endpoints as api
    fields = api.SecondaryActItem.model_fields
    for f in ("objection_deadline_earliest", "scrutiny_period", "urgency_procedure"):
        assert f in fields, f
    assert api._scrutiny_period_label("1/3") == "1 or 3 months"
    assert api._scrutiny_period_label("1") == "1 month"
    assert api._scrutiny_period_label(None) is None


def test_urgency_is_read_from_the_events_as_well_as_the_status():
    s = job.scrutiny_from_events([_ev("DA_URGENT_ADOPTION", 2019, 10, 9), _ev("DA_URGENT_PUB", 2019, 10, 10)],
                                 "2", "published")
    assert s["urgent"] is True and s["adoption_date"] == date(2019, 10, 9)
    assert job.scrutiny_from_events([_ev("DA_ADOPTION", 2019, 10, 9)], "2", "published")["urgent"] is False


def _rec(ref, celex=None, regdel_id=None, act_type="delegated"):
    return {"act_type": act_type, "reference": ref, "celex": celex, "regdel_id": regdel_id}


def test_one_record_per_celex_and_per_c_number_the_same_way_every_run():
    a, b = _rec("C(2016)1372", "32017R0867", 900), _rec("C(2017)597", "32017R0867", 800)
    kept, dropped = job.dedupe([a, b], {})
    assert kept == [b] and dropped == [a]                      # lowest register id
    kept, _ = job.dedupe([b, a], {"32017R0867": "C(2016)1372"})
    assert kept == [a]                                          # the one the row holds wins
    # Two acts without a CELEX under one C-number collide; two CELEX holders do not.
    x, y = _rec("C(2026)1", None, 5, "implementing"), _rec("C(2026)1", None, 4, "implementing")
    assert job.dedupe([x, y], {})[0] == [y]
    p, q = _rec("C(2026)2", "32026R0001", 1), _rec("C(2026)2", "32026R0002", 2)
    assert len(job.dedupe([p, q], {})[0]) == 2


def test_an_adoption_date_is_corrected_only_where_the_act_names_the_registers_date():
    title = "Commission Delegated Regulation (EU) 2022/826 of 23 March 2022 supplementing"
    assert job.title_date(title) == date(2022, 3, 23)
    assert job.adoption_to_store(date(2022, 5, 23), date(2022, 3, 23), title) == date(2022, 3, 23)
    assert job.adoption_to_store(date(2022, 5, 23), date(2022, 3, 24), title) == date(2022, 5, 23)
    assert job.adoption_to_store(None, date(2022, 3, 24), title) == date(2022, 3, 24)
    assert job.adoption_to_store(date(2022, 5, 23), None, title) == date(2022, 5, 23)


def test_a_dropped_connection_is_tried_again_and_an_http_error_is_not(monkeypatch):
    import http.client
    import urllib.error
    monkeypatch.setattr("time.sleep", lambda s: None)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        return b"ok"
    assert job.with_retries(flaky, "test") == b"ok" and len(calls) == 3

    def refused():
        calls.append(1)
        raise urllib.error.HTTPError("u", 403, "Forbidden", {}, None)
    calls.clear()
    try:
        job.with_retries(refused, "test")
    except urllib.error.HTTPError:
        pass
    assert len(calls) == 1
