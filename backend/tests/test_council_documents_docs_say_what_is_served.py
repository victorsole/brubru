"""/council-documents documents what it serves (14 Oct 2026).

Two of the three documented examples returned 0 on production (`document_type=conclusions`,
`policy_area=energy`): no row has ever carried either value. The description promised
"press releases in full" while the 57 releases held stopped on 28 September, and said the
corpus was a policy-driven slice of the register. The item route answered any institution's
publication id as a Council document."""
from __future__ import annotations

import inspect
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1 import council_documents as v1  # noqa: E402
from api.v2.council import council_documents as v2  # noqa: E402

STORED_TYPES = {"document", "press_release", "meeting_agenda"}


def _route(module, path):
    return next(r for r in module.router.routes if r.path == path)


def _try_it(description):
    return re.findall(r"^GET (/api/v[12]/[\w/-]+)(?:\?(\S+))?$", description, re.M)


def test_every_example_uses_parameters_and_values_the_route_serves():
    for module, prefix in ((v1, "/council-documents"), (v2, "/council-documents")):
        route = _route(module, prefix)
        accepted = set(inspect.signature(route.endpoint).parameters)
        examples = _try_it(route.description)
        assert len(examples) >= 3
        for _, query in examples:
            for pair in filter(None, (query or "").split("&")):
                key, _, value = pair.partition("=")
                assert key in accepted, (key, route.description[:60])
                if key == "document_type":
                    assert value in STORED_TYPES, value
                assert key != "policy_area" or value.isupper(), value


def test_the_description_names_only_document_types_that_are_stored():
    for module in (v1, v2):
        desc = _route(module, "/council-documents").description
        named = set(re.findall(r"`document_type`[^\n]*", desc)[0].split("`")[1::2]) - {"document_type", "source=meetings"}
        assert named <= STORED_TYPES, named
        assert "conclusions` /" not in desc and "policy_area=energy" not in desc


def test_the_writers_store_those_types():
    discover = (BACKEND / "scripts" / "discover_council_documents.py").read_text(encoding="utf-8")
    press = (BACKEND / "scripts" / "sync_council_press_releases.py").read_text(encoding="utf-8")
    assert 'category="document"' in discover and 'category="press_release"' in press


def test_the_coverage_note_no_longer_promises_what_is_not_held():
    src = inspect.getsource(v1.list_council_documents)
    assert "press releases in full" not in src and "policy-driven slice" not in src
    assert "browser check" in src and "15 July 2024" in src


def test_the_item_route_only_answers_a_council_publication():
    src = inspect.getsource(v1.get_council_document_detail)
    assert "InstitutionalPublication.institution_slug.ilike" in src and "COUNCIL_INSTITUTION_SLUGS" in src
