"""A DOCX line break must not fuse the words either side of it.

EP answer documents separate lines with <w:cr/>, not <w:br/>. The extractor handled
neither, so "Executive Vice-President Fitto" + "on behalf of the European Commission"
came out as "...Fittoon behalf of...". 2,973 of 4,880 stored answers were damaged this
way, and every one of them passed the length check that was supposed to prove the body
was real: a length check is not a content check.
"""
import importlib.util
import io
import pathlib
import zipfile

BACKEND = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "bpqa", BACKEND / "scripts" / "backfill_parl_question_answers.py")
bpqa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bpqa)


def _docx(body_xml: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml",
                   '<?xml version="1.0"?><w:document xmlns:w="x"><w:body>'
                   + body_xml + "</w:body></w:document>")
    return buf.getvalue()


def test_a_carriage_return_separates_words():
    blob = _docx('<w:p><w:r><w:t>Vice-President Fitto</w:t></w:r>'
                 '<w:r><w:cr/><w:t>on behalf of the European Commission</w:t></w:r></w:p>')
    text = bpqa.extract_docx_text(blob)
    assert "Fittoon" not in text, f"words fused across the line break: {text!r}"
    assert "Fitto" in text and "on behalf of the European Commission" in text


def test_a_line_break_separates_words():
    blob = _docx('<w:p><w:r><w:t>first</w:t></w:r>'
                 '<w:r><w:br/><w:t>second</w:t></w:r></w:p>')
    assert "firstsecond" not in bpqa.extract_docx_text(blob)


def test_paragraphs_still_separate():
    blob = _docx('<w:p><w:r><w:t>one</w:t></w:r></w:p><w:p><w:r><w:t>two</w:t></w:r></w:p>')
    assert "onetwo" not in bpqa.extract_docx_text(blob)


def test_runs_inside_one_word_are_not_split():
    """Adjacent runs with no separator are one word: spell-check markup splits them."""
    blob = _docx('<w:p><w:r><w:t>Com</w:t></w:r><w:r><w:t>mission</w:t></w:r></w:p>')
    assert "Commission" in bpqa.extract_docx_text(blob)
