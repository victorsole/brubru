"""The committee-document brief must keep counting the way it was built to count.

Context (22 September 2026). Six deep-dives were brought current by hand in one
day, repeating the same fetch-and-count three times each. `deep_dive_brief.py`
does the plumbing; these tests pin the two rules that were got wrong in the wild
and the one that was got wrong while building it.

All offline: no network, no database, no browser.
"""

import importlib.util
import os
import pathlib
import sys
import tempfile

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _load(name: str):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_BACKEND, "scripts", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


brief = _load("deep_dive_brief")


def _doc(body: str) -> pathlib.Path:
    fh = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
    fh.write(body)
    fh.close()
    return pathlib.Path(fh.name)


def test_the_last_amendment_number_is_not_the_count():
    """The defect that shipped: "405 amendments" when members tabled 380.

    Parliament numbers amendments continuously across the draft report and every
    amendment document, so max(id) overstates the member count by the
    rapporteur's offset. The parse must expose count, range AND gaps so the
    arithmetic is checkable rather than trusted.
    """
    # members start at 26 because the rapporteur's own draft report used 1-25
    body = "AMENDMENTS\n26 - 30\n" + "".join(
        f"\nAmendment {i}\nProposal for a regulation\nArticle 3\n" for i in range(26, 31))
    p = _doc(body)
    got = brief.parse_one(p)
    p.unlink()

    ids = sorted(set(got["ids"]))
    assert got["amendments"] == 5, "five amendments, not thirty"
    assert ids[-1] == 30 and ids[0] == 26
    assert ids[-1] != len(ids), "the highest number must not be mistaken for the count"
    assert got["header_range"] == ["26", "30"]


def test_a_gap_in_the_numbering_is_reported_not_smoothed():
    """A missing amendment means a document failed to parse; do not hide it."""
    body = "".join(f"\nAmendment {i}\nProposal for a regulation\nArticle 3\n"
                   for i in [1, 2, 5])
    p = _doc(body)
    ids = sorted(set(brief.parse_one(p)["ids"]))
    p.unlink()
    gaps = [x for x in range(ids[0], ids[-1] + 1) if x not in set(ids)]
    assert gaps == [3, 4], "the caller must be able to see the hole"


def test_names_are_matched_by_CASE_not_by_a_letter_range():
    """`KNOTEK Ondřej` was dropped, so 6 of 7 shadows were found.

    An explicit [A-ZÀ-Ý] range silently excludes Latin Extended-A. Structure
    belongs in the regex, case belongs in Python. Same family as the
    accent-folding bug in audit_deep_dives.
    """
    seg = ("Shadow rapporteur WÖLKEN Tiemo (S&D) KNOTEK Ondřej (PfE) "
           "VERYGA Aurelijus (ECR) DE LA PISA CARRIÓN Margarita (PfE) "
           "MARTINS Catarina (The Left)")
    people = brief._people(seg)
    names = [n for n, _ in people]

    assert "KNOTEK Ondřej" in names, "Latin Extended-A must not be dropped"
    assert "WÖLKEN Tiemo" in names
    assert "DE LA PISA CARRIÓN Margarita" in names, "multi-word surnames survive"
    assert len(people) == 5
    assert dict(people)["KNOTEK Ondřej"] == "PfE"


def test_the_committee_name_does_not_bleed_into_the_surname():
    """First attempt produced "IMCO Internal Market and Consumer Protection IJABS Ivars"."""
    seg = ("Committee responsible Rapporteur Appointed IMCO "
           "Internal Market and Consumer Protection IJABS Ivars (Renew) 03/10/2024")
    people = brief._people(seg)
    assert people, "a rapporteur must be found"
    name = people[0][0]
    assert name == "IJABS Ivars", f"got {name!r}"


def test_gateway_rows_carry_their_real_links():
    """doceo paths are not derivable from a PE number, so they must come from OEIL.

    A joint committee file uses a CJnn prefix (CJ80 for the Industrial
    Accelerator Act), an opinion uses <CTTE>-AD-. Guessing produced 404s.
    """
    text = ("Documentation gateway European Parliament Document type Committee Reference "
            "Date Summary Committee draft report PE792.067 11/09/2026 "
            "Committee opinion ENVI PE789.106 06/07/2026 "
            "European Commission Document type Reference Date Summary "
            "Legislative proposal COM(2026)0100 04/03/2026")
    html = ('<a href="https://www.europarl.europa.eu/doceo/document/CJ80-PR-792067_EN.html">x</a>'
            '<a href="https://www.europarl.europa.eu/doceo/document/ENVI-AD-789106_EN.html">y</a>')
    rows = brief.gateway(text, html)
    by_ref = {r["ref"]: r for r in rows}

    assert "PE792.067" in by_ref and "PE789.106" in by_ref
    assert "COM(2026)0100" not in by_ref, "the Commission block must stay out"
    assert by_ref["PE792.067"]["url"].endswith("CJ80-PR-792067_EN.html")
    assert by_ref["PE789.106"]["url"].endswith("ENVI-AD-789106_EN.html")
    assert by_ref["PE789.106"]["committee"] == "ENVI"


def test_a_missing_link_is_left_as_None_rather_than_guessed():
    text = ("Documentation gateway European Parliament Document type Committee Reference Date "
            "Summary Committee draft report PE999.999 01/01/2026 "
            "European Commission Document type Reference Date Summary")
    rows = brief.gateway(text, "<html></html>")
    assert rows and rows[0]["url"] is None, "never invent a doceo path"


def test_the_roll_call_tally_is_read_from_the_annex():
    body = ("FINAL VOTE BY ROLL CALL IN COMMITTEE RESPONSIBLE\n\n"
            " 33 +\n ECR Someone Else\n\n 10 -\n ID Another Person\n\n 2 0\n NI Third Person\n")
    p = _doc(body)
    got = brief.rollcall(p)
    p.unlink()
    assert got == {"for": 33, "against": 10, "abstain": 2}


def test_no_roll_call_annex_returns_None_rather_than_zeros():
    """A document without a vote must not report a unanimous one."""
    p = _doc("DRAFT REPORT\nAmendment 1\nProposal for a regulation\nArticle 1\n")
    got = brief.rollcall(p)
    p.unlink()
    assert got is None
