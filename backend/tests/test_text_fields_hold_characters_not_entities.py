"""Plain-text fields hold characters, not HTML entities (16 Oct 2026: "(S&amp;D)" in 1,362 questions)."""
import io
import zipfile

from scripts.backfill_parl_question_text import extract_docx_text
from scripts.decode_text_entities import decode


def test_entities_are_decoded_once_or_twice():
    assert decode("Biljana Borzan (S&amp;D)") == "Biljana Borzan (S&D)"
    assert decode("formation sur le thème &amp;quot;management&amp;quot;") == 'formation sur le thème "management"'
    assert decode("GARA SUA N. 108/2025&#8211; PROCEDURA") == "GARA SUA N. 108/2025– PROCEDURA"
    assert decode("no entity here") == "no entity here" and decode(None) is None


def test_the_question_reader_decodes_the_document_xml():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", "<w:document><w:t>Biljana Borzan</w:t><w:t>(S&amp;D)</w:t></w:document>")
    assert extract_docx_text(buf.getvalue()) == "Biljana Borzan\n(S&D)"
