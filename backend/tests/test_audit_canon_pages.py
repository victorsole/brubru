"""The EU Canon publish gate (22 Oct 2026): placeholders, the publisher, the EU credit and
untranslated blocks, each a defect found live on that day."""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from scripts.audit_canon_pages import problems, text_blocks  # noqa: E402

EN = ("<html><body><p>The Regulation sits at the intersection of chemicals regulation, consumer "
      "information and the circular economy agenda of the Union.</p>"
      "<p>Manufacturers must draw up technical documentation and keep it for ten years after placing.</p>"
      "<footer><p>Built by Beresol BV</p>\n<p>Apeldoorn, Netherlands</p>"
      "<p>EU legal texts &copy; European Union, EUR-Lex, reused under Decision 2011/833/EU.</p></footer>"
      "</body></html>")
IT = ("<html><body><p>Il regolamento si colloca all'incrocio tra la disciplina delle sostanze chimiche, "
      "l'informazione dei consumatori e l'economia circolare dell'Unione.</p>"
      "<p>I fabbricanti devono redigere la documentazione tecnica e conservarla per dieci anni.</p>"
      "<footer><p>Sviluppato da Beresol BV</p>\n<p>Apeldoorn, Paesi Bassi</p>"
      "<p>Testi giuridici dell'UE &copy; Unione europea, EUR-Lex, riutilizzati ai sensi della decisione 2011/833/UE.</p></footer>"
      "</body></html>")


def _page(tmp_path, html, name="it.html"):
    p = tmp_path / name
    p.write_text(html, encoding="utf-8")
    return p


def test_a_clean_translation_passes(tmp_path):
    assert problems(_page(tmp_path, IT), text_blocks(EN)) == []
    assert problems(_page(tmp_path, EN, "index.html"), None) == []


def test_a_placeholder_left_by_the_translator_fails(tmp_path):
    page = _page(tmp_path, IT.replace("Sviluppato da Beresol BV", "Sviluppato da __MASK0__CBrubru"))
    assert any("placeholder" in p for p in problems(page, text_blocks(EN)))


def test_the_wrong_publisher_and_seat_fail(tmp_path):
    page = _page(tmp_path, IT.replace("Beresol BV", "Beresol SL").replace("Apeldoorn, Paesi Bassi", "Bruxelles, Belgio"))
    found = problems(page, text_blocks(EN))
    assert any("Beresol SL" in p for p in found) and any("Brussels" in p for p in found)


def test_a_footer_without_the_eu_credit_fails(tmp_path):
    page = _page(tmp_path, IT.replace("2011/833/UE", "XXXX"))
    assert any("credit" in p for p in problems(page, text_blocks(EN)))


def test_english_left_in_a_translation_fails_and_shared_names_do_not(tmp_path):
    english_block = ("The Regulation sits at the intersection of chemicals regulation, consumer "
                     "information and the circular economy agenda of the Union.")
    half = IT.replace(IT[IT.index("Il regolamento"):IT.index("</p>")], english_block)
    many = "".join(f"<p>{english_block}</p>" for _ in range(6))
    en_many = EN.replace("<footer>", many + "<footer>")
    it_many = half.replace("<footer>", many + "<footer>")
    assert any("still in English" in p for p in problems(_page(tmp_path, it_many), text_blocks(en_many)))
    # translated titles that keep the act's number and the brand are not English, however many
    en_titles = "".join("<p>The Detergents Regulation (2026) explained | Brubru EU Canon</p>" for _ in range(6))
    it_titles = "".join("<p>Explica el Reglament de Detergents (2026) | Brubru EU Canon</p>" for _ in range(6))
    en_title = EN.replace("<footer>", en_titles + "<footer>")
    it_title = IT.replace("<footer>", it_titles + "<footer>")
    assert problems(_page(tmp_path, it_title), text_blocks(en_title)) == []
