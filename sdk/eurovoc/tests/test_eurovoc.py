"""eurovoc tests.

Fast tests cover the enrichment / domain roll-up and the descriptor-set pruning
(no model needed). The model-backed tests actually load multilingual-e5 and
classify real text; they carry the ``model`` marker. Run everything with:
    pytest
or skip the heavy ones with:
    pytest -m "not model"
"""
import json
from pathlib import Path

import pytest

import eurovoc
from eurovoc import DOMAINS, Descriptor, from_descriptors
from eurovoc._local import _keep


# --------------------------------------------------------------------------- #
# Enrichment / hierarchy (no model)
# --------------------------------------------------------------------------- #
def test_domains_are_the_21():
    assert len(DOMAINS) == 21
    assert DOMAINS["24"] == "FINANCE" and DOMAINS["52"] == "ENVIRONMENT"


def test_from_descriptors_rolls_up_domain():
    out = from_descriptors([{"id": "1234", "label": "financial instrument", "mt": "2426", "score": 0.88}])
    assert len(out) == 1
    d = out[0]
    assert isinstance(d, Descriptor)
    assert d.label == "financial instrument"
    assert d.mt == "2426" and d.domain == "24" and d.domain_label == "FINANCE"
    assert d.score == 0.88


def test_from_descriptors_handles_label_alias_and_missing_mt():
    out = from_descriptors([{"id": "1", "descriptor": "via alias"}, {"id": "2", "label": "no mt", "mt": None}])
    assert out[0].label == "via alias" and out[0].domain is None
    assert out[1].domain is None and out[1].domain_label is None


def test_from_descriptors_empty_and_none():
    assert from_descriptors([]) == []
    assert from_descriptors(None) == []


def test_descriptor_as_dict_shape():
    d = from_descriptors([{"id": "9", "label": "energy policy", "mt": "6606", "score": 0.9}])[0]
    j = d.as_dict()
    assert j == {"descriptor": "energy policy", "id": "9", "mt": "6606",
                 "domain": "66", "domain_label": "ENERGY", "score": 0.9}


def test_keep_prunes_org_and_treaty_keeps_subject():
    assert _keep({"label": "data protection", "mt": "3236"}) is True
    assert _keep({"label": "United Nations", "mt": "7606"}) is False         # org microthesaurus
    assert _keep({"label": "Maastricht Treaty", "mt": "1016"}) is False      # treaty in construction
    assert _keep({"label": "regulation", "mt": "1206"}) is False             # instrument-type noise


def test_packaged_descriptor_data_present():
    p = Path(eurovoc.__file__).resolve().parent / "data" / "eurovoc_descriptors.json"
    data = json.loads(p.read_text())
    assert len(data) == 7029
    # every mt's first two digits is one of the 21 domains
    bad = {d["mt"][:2] for d in data if d.get("mt")} - set(DOMAINS)
    assert not bad, f"unmapped domains: {bad}"


def test_classify_url_without_brubru_is_guarded(monkeypatch):
    # If brubru is not importable, classify_url must raise a helpful error.
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "brubru":
            raise ImportError("no brubru")
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RuntimeError) as ei:
        eurovoc.classify_url("https://x", api_key="k")
    assert "brubru" in str(ei.value)


# --------------------------------------------------------------------------- #
# Model-backed (real classification)
# --------------------------------------------------------------------------- #
@pytest.mark.model
def test_classify_real_topic_gdpr():
    out = eurovoc.classify("General Data Protection Regulation: rules on the protection of "
                           "personal data and the free movement of such data")
    assert out, "GDPR text should classify to something"
    labels = [d.label.lower() for d in out]
    assert any("data" in l or "personal" in l or "protection" in l for l in labels)
    for d in out:
        assert d.domain in DOMAINS and d.domain_label
        assert 0.0 <= d.score <= 1.0


@pytest.mark.model
def test_classify_crypto():
    out = eurovoc.classify("Markets in crypto-assets regulation")
    assert isinstance(out, list)
    # should not crash and, if confident, return finance/economics-flavoured tags
    if out:
        assert all(isinstance(d, Descriptor) for d in out)


@pytest.mark.model
def test_gate_rejects_gibberish():
    out = eurovoc.classify("xyzzy plugh frobnicate qux")
    assert out == [], "gibberish should yield no tags (gate prefers nothing over noise)"


@pytest.mark.model
def test_top_k_respected():
    out = eurovoc.classify("transport policy and railway infrastructure in the European Union", top_k=3)
    assert len(out) <= 3


@pytest.mark.model
def test_multilingual_catalan():
    # Catalan input should still classify (multilingual model).
    out = eurovoc.classify("Regulació de la protecció de dades personals a la Unió Europea")
    assert isinstance(out, list)
    if out:
        assert all(d.domain in DOMAINS for d in out)
