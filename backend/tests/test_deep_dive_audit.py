"""The deep-dive detector must keep finding what it was built to find.

Context (22 September 2026). Twelve of thirteen deep-dives had gone stale, with
no trigger anywhere: deep-dives are in no cron, no sync registry and no
`/morning` phase, and they sit outside the canonical six-product feature tree,
so the `/news` feature walk never reached them.

These tests pin the two matching rules that took a wrong first attempt each, and
the structural rule that caught three real layout defects. They are offline: no
database, no network, no browser.
"""

import os
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import importlib.util


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_BACKEND, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


audit = _load("audit_deep_dives")
validate = _load("validate_deep_dive_html")


def test_rapporteur_is_matched_on_surname_not_full_string():
    """OEIL stores 'SCHENK Oliver'; the pages write 'Oliver Schenk'.

    A full-string match finds neither, which would report every page as current.
    """
    assert audit.surname("SCHENK Oliver") == "schenk"
    assert audit.surname("VAN LANSCHOT Reinier") == "van"  # first caps token
    assert audit.surname("ABADÍA JOVER Maravillas") == "abadia"
    assert audit.surname(None) is None


def test_matching_folds_accents():
    """'ABADÍA' and 'ABADIA' are the same person; a substring test says otherwise."""
    assert audit.fold("ABADÍA JOVER") == "abadia jover"
    assert audit.fold("Sinkevičius") == "sinkevicius"
    assert audit.fold("WÖLKEN Tiemo") == "wolken tiemo"
    # The page writes the accented form; the needle is folded, so it must match.
    assert audit.fold("SCHENK") in audit.fold("Rapporteur: Oliver Schenk (EPP)")


def test_the_oeil_gateway_row_parser_finds_a_tabled_report():
    """eMeeting alone misses a report until it reaches a committee agenda.

    Found 22 September 2026, by Victor rather than by this script. The
    Industrial Accelerator Act's joint draft report PE792.067 was dated
    9 September and entered OEIL's Documentation gateway on 11 September, while
    `ep_emeeting_documents` held nothing for that procedure newer than 6 July.
    All six pages still said no draft report had been tabled, and the detector
    reported the file as current. Both sources, every run.

    This pins the row parser offline, against the gateway's own flattened
    wording, so it keeps finding reports, opinions and amendment batches, and
    keeps ignoring the Commission block that follows.
    """
    block = (
        "Documentation gateway European Parliament Document type Committee Reference Date "
        "Summary Committee draft report PE792.067 11/09/2026 "
        "Committee opinion ENVI PE789.106 06/07/2026 "
        "Amendments tabled in committee PE790.005 13/07/2026 "
        "Committee report tabled for plenary, 1st reading/single reading A9-0141/2024 21/03/2024 "
        "European Commission Document type Reference Date Summary "
        "Legislative proposal COM(2026)0100 04/03/2026"
    )
    i = block.find("Documentation gateway European Parliament")
    j = block.find("European Commission Document type", i)
    rows = [{"kind": m.group(1).strip(), "committee": (m.group(2) or "").strip() or None,
             "ref": m.group(3), "date": m.group(4)}
            for m in audit._GATEWAY_ROW.finditer(block[i:j])]

    refs = [r["ref"] for r in rows]
    assert "PE792.067" in refs, "the draft report that was missed must be found"
    assert "PE789.106" in refs and "PE790.005" in refs
    assert "A9-0141/2024" in refs, "plenary reports count too"
    assert "COM(2026)0100" not in refs, "the Commission block must stay out"

    by_ref = {r["ref"]: r for r in rows}
    assert by_ref["PE792.067"]["kind"] == "Committee draft report"
    assert by_ref["PE792.067"]["date"] == "11/09/2026"
    assert by_ref["PE789.106"]["committee"] == "ENVI"
    assert by_ref["PE792.067"]["committee"] is None, "a joint report names no committee"


def test_page_text_decodes_html_entities_before_matching():
    """Pages write non-ASCII names as entities; folding Unicode does not touch those.

    Found 22 September 2026. The pharma-laws page carries its rapporteur as
    `W&ouml;lken`, so the detector searched folded text for "wolken" in a string
    that still read "w&ouml;lken" and reported the rapporteur as missing from
    ALL pages of a file that named him correctly. Same shape as the accent bug,
    one layer further out: normalise the encoding before you normalise the
    letters.
    """
    import tempfile

    doc = ('<html><body><p>Rapporteur: Tiemo W&ouml;lken (S&amp;D)</p>'
           '<p>Shadow: Ond&#345;ej Knotek</p></body></html>')
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(doc)
        tmp = pathlib.Path(fh.name)
    text = audit.page_text(tmp)
    tmp.unlink()

    assert "w&ouml;lken" not in text, "the entity must be decoded, not carried through"
    assert audit.surname("WÖLKEN Tiemo") in text          # named entity
    assert audit.surname("KNOTEK Ondřej") in text         # numeric entity


def test_a_bare_section_title_is_rejected():
    """The defect that rendered as narrow columns.

    A section title outside a `section__header` gets absorbed into the flex row.
    The markup looks fine; only a render shows it. This makes it fail statically.
    """
    bad = ('<html><head><meta name="brubru:last-reviewed" content="2026-09-22"></head><body>'
           '<h2 class="section__title">11. Who is handling it</h2><p>x</p></body></html>')
    fails = validate.static_checks_text(bad) if hasattr(validate, "static_checks_text") else None
    if fails is None:
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
            fh.write(bad)
            tmp = pathlib.Path(fh.name)
        fails = validate.static_checks(tmp)
        tmp.unlink()
    assert any("NOT inside a section__header" in f for f in fails), fails


def test_two_active_timeline_items_are_rejected():
    """A page cannot be at two stages of the procedure at once."""
    import tempfile
    html = ('<html><head><meta name="brubru:last-reviewed" content="2026-09-22"></head><body>'
            '<div class="section__header"><h2 class="section__title">1. A</h2></div>'
            '<div class="timeline__item active">x</div>'
            '<div class="timeline__item active">y</div></body></html>')
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(html)
        tmp = pathlib.Path(fh.name)
    fails = validate.static_checks(tmp)
    tmp.unlink()
    assert any("marked active" in f for f in fails), fails


def test_the_active_rule_covers_both_naming_conventions():
    """Deep-dives write the current stage two different ways.

    Found 22 September 2026: the rule matched `timeline__item active` only, so
    it was dead on 6 of the 10 deep-dives that carry a timeline -- EU Inc., the
    Industrial Accelerator Act, the Critical Medicines Act, Biotech, CSAM and
    Late Payments all use the BEM modifier `timeline__item--active`. A check
    that cannot fire on most of its corpus is not a check.
    """
    import tempfile

    head = ('<html><head><meta name="brubru:last-reviewed" content="2026-09-22">'
            # the stylesheet declares the modifier too; counting CSS reported
            # three "active items" on a page that has exactly one
            '<style>.timeline__item--active::before{}</style></head><body>'
            '<div class="section__header"><h2 class="section__title">1. A</h2></div>')

    def check(fragment):
        with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
            fh.write(head + fragment + "</body></html>")
            tmp = pathlib.Path(fh.name)
        fails = validate.static_checks(tmp)
        tmp.unlink()
        return fails

    one = '<div class="timeline__item--active">x</div>'
    assert check(one) == [], "one modifier-styled active item is valid"
    assert any("marked active" in f for f in check(one + one)), "two must fail"
    assert any("no active item" in f for f in check('<div class="timeline__item">x</div>')), \
        "a timeline naming no current stage must fail"
    assert check('<div class="timeline__item active">x</div>') == [], \
        "the legacy spelling must keep passing"


def test_a_well_formed_page_passes():
    """No false positives, or the check will be ignored."""
    import tempfile
    html = ('<html><head><meta name="brubru:last-reviewed" content="2026-09-22"></head><body>'
            '<div class="section__header"><h2 class="section__title">1. A</h2></div>'
            '<div class="section__header"><h2 class="section__title">2. B</h2></div>'
            '<div class="timeline__item active">x</div>'
            '<div class="timeline__item done">y</div></body></html>')
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as fh:
        fh.write(html)
        tmp = pathlib.Path(fh.name)
    fails = validate.static_checks(tmp)
    tmp.unlink()
    assert fails == [], fails


def test_every_deep_dive_page_on_disk_passes_the_static_checks():
    """The live pages must stay valid, not just the fixtures."""
    from services.comparator.deep_dives import DEEP_DIVES
    public = pathlib.Path(_REPO_ROOT) / "frontend" / "public"
    bad = {}
    for d in DEEP_DIVES:
        for page in sorted((public / d["base_path"].lstrip("/")).glob("*.html")):
            fails = validate.static_checks(page)
            if fails:
                bad[str(page.relative_to(public))] = fails
    assert not bad, bad
