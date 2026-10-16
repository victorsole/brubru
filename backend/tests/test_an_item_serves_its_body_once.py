"""An item serves its text once: the deprecated alias keys stay, their values are empty.

Three "deprecated alias kept one release" fields from 5 May 2026 were still carrying the
whole text on 16 Oct 2026: `body` (= body_txt or body_html) on 13 item models, `text` on
consultation feedback, `full_text` + `has_full_text` on adopted and tabled texts. Measured
on GovClipping's morning window: register documents 100 MB of text served twice,
delegated acts 5.4 MB twice, implementing acts 166 MB twice; one implementing act
(32018R0688) carried 41 MB three times over and its page took 96 s. No client collection
referenced the aliases (GovClipping's 56 requests: 0 mentions).

The public changelog promises that a field is never removed without a major version, so
the keys remain and the values are always empty (Victor, 16 Oct 2026: "keep the field
names, empty the values"). This test holds that on the one helper the 13 routes share,
on the two hand-written aliases, and on every pydantic model that serves body_txt.
"""
import importlib
import pkgutil
from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

import api.v1 as v1
import api.v2 as v2
from api.v1._body import deprecated_body

ALIASES = ("body", "text", "full_text")


class TestTheSharedHelperIsEmpty:
    @pytest.mark.parametrize("txt,html", [("some text", None), (None, "<p>html</p>"), ("t", "<p>h</p>"), (None, None)])
    def test_returns_none_whatever_it_is_given(self, txt, html):
        assert deprecated_body(txt, html) is None


class TestAdoptedAndTabledTexts:
    def test_full_text_aliases_are_empty_while_body_txt_is_served(self):
        from api.v1.texts_adopted import _row_to_item
        when = datetime(2026, 10, 6)
        r = SimpleNamespace(id="a1", ta_reference="P10_TA(2026)0001", title="T", description=None, text_type="other",
                            procedure_ref=None, parliamentary_term=10, adoption_date=when, committees=[],
                            rapporteur_name=None, rapporteur_mep_id=None, celex_number=None, vote_results=None,
                            related_documents=None, source_url="https://www.europarl.europa.eu/doceo/x",
                            full_text_url=None, pdf_url=None, full_text="The European Parliament, " * 40,
                            document_date=when.date(), first_seen=when, scraped_at=when, last_updated=when)
        item = _row_to_item(r)
        assert item.body_txt and item.has_body
        assert item.full_text is None and item.has_full_text is False
        assert "full_text" in item.model_fields and "has_full_text" in item.model_fields  # the keys stay


class TestConsultationFeedback:
    def test_the_text_alias_is_assigned_empty(self):
        import inspect
        import api.v1.consultations as c
        src = inspect.getsource(c)
        assert "text=None," in src and "text=body_text" not in src


def _models(package):
    seen = {}
    for mod in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        try:
            m = importlib.import_module(mod.name)
        except Exception:  # a module that needs a live service is not a model source
            continue
        for name, obj in vars(m).items():
            if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
                seen[f"{mod.name}.{name}"] = obj
    return seen


class TestEveryBodyBearingModel:
    def test_an_alias_field_defaults_to_empty_and_is_never_required(self):
        found = {}
        for pkg in (v1, v2):
            found.update(_models(pkg))
        with_body = {k: m for k, m in found.items() if "body_txt" in m.model_fields}
        assert len(with_body) >= 40, f"only {len(with_body)} body-bearing models found; the walk is broken"
        bad = {}
        for k, m in with_body.items():
            for a in ALIASES:
                f = m.model_fields.get(a)
                if f is not None and (f.is_required() or f.default not in (None, "")):
                    bad[k] = a
        assert not bad, f"alias fields that are required or default to text: {bad}"
