"""/delegated-acts and /implementing-acts document what they serve (14 Oct 2026).

The descriptions promised an objection deadline, EP and Council scrutiny and a parent
procedure that no row carried; gave `status=scrutiny` (not a status: it answered 500)
and an AI Act example that returns 0; and said the data came daily at 04:00 UTC from
backfill_eu_comitology.py, which is not the job that feeds them."""
from __future__ import annotations

import inspect
import re

from api.v1 import w4_endpoints as v1
from api.v2.legislative import secondary_acts as v2

STATUSES = {s.value for s in v1.SecondaryActStatusEnum}


def _routes():
    for module in (v1, v2):
        for router in (module.delegated_router, module.implementing_router):
            for r in router.routes:
                yield module, r


def test_every_example_uses_parameters_and_values_the_route_accepts():
    for module, r in _routes():
        accepted = set(inspect.signature(r.endpoint).parameters)
        examples = re.findall(r"^GET (/api/v[12]/[\w/-]+?)(/[^?\s]+)?(?:\?(\S+))?$", r.description, re.M)
        assert len(examples) >= 2, r.path
        for _, item, query in examples:
            for pair in filter(None, (query or "").split("&")):
                key, _, value = pair.partition("=")
                assert key in accepted, (r.path, key)
                if key == "status":
                    assert value in STATUSES, value


def test_the_status_list_in_the_description_is_the_enum():
    for module, r in _routes():
        if r.path.endswith("{reference:path}"):
            continue
        line = next(l for l in r.description.splitlines() if l.startswith("- `status`"))
        named = set(re.findall(r"`([a-z_]+)`", line)) - {"status"}
        assert named <= STATUSES, named


def test_the_stale_claims_are_gone_and_the_real_ones_are_there():
    for module, r in _routes():
        d = r.description
        assert "backfill_eu_comitology" not in d and "04:00 UTC" not in d and "status=scrutiny" not in d
        assert "32024R1689" not in d          # the AI Act example that returned 0
        assert "—" not in d and "—" not in r.summary
    delegated = next(r for m, r in _routes() if m is v2 and r.path == "/delegated-acts")
    for field in ("objection_deadline_earliest", "scrutiny_period", "ep_scrutiny", "body_source",
                  "parent_procedure_ref", "updated_to"):
        assert field in delegated.description, field
    assert "objection_deadline`, is null" in delegated.description
