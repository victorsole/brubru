"""The Court of Auditors' items are read from the site's own files, not its rendered pages.

18 Oct 2026: 81 ECA bodies stored U+FFFD where the source has curly quotes ("the
�industrial leadership� priority"). The article file a news page loads, ECAHTMLNews/<id>/
en/body.html, is UTF-8 with bare Windows-1252 quotes pasted into one paragraph; the page
shows that copy in a hidden block, decoded to U+FFFD, and the extractor read hidden text.
Publication pages held hidden SharePoint metadata or, for record pages, only "Access
document" and the summaries of OTHER reports. Now:
  - news        -> body.html over the site's SharePoint REST API, decoded as UTF-8 with a
                   Windows-1252 fallback for the bytes that are not UTF-8;
  - publication -> the English PDF, ECAPublications/<id>/<id>_EN.pdf.
The fetcher's direct route decodes the same way.
"""
import importlib
import pathlib
import sys
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
eca = importlib.import_module("services.scrapers.economy_eca")
common = importlib.import_module("services.scrapers.economy_common")

# The live file's bytes: one paragraph in UTF-8, the next with bare 0x93/0x94/0x96/0x92.
BODY = ("<p>Funding for close-to-market research under the “industrial leadership” priority "
        "of Horizon 2020 was not sufficiently geared towards commercialisation.</p>").encode("utf-8") + \
       (b"<p>Funding for close-to-market research under the \x93industrial leadership\x94 priority of "
        b"Horizon 2020 \x96 the EU\x92s 2014-2020 research flagship programme \x96 was not sufficiently "
        b"geared towards commercialisation of innovative ideas and products.</p>")


def test_mixed_bytes_decode_to_real_quotes():
    s = common.decode_mixed(BODY)
    assert "�" not in s
    assert s.count("“industrial leadership”") == 2 and "EU’s" in s and "–" in s


def test_news_is_read_from_its_article_file(monkeypatch):
    asked = []
    monkeypatch.setattr(eca, "http_get", lambda url: asked.append(url) or SimpleNamespace(content=BODY))
    txt, html = eca.news_body("https://www.eca.europa.eu/en/news/NEWS-SR-2026-24")
    assert asked == ["https://www.eca.europa.eu/_api/web/getFileByServerRelativePath("
                     "decodedUrl='///ECAHTMLNews/NEWS-SR-2026-24/en/body.html')/$value"]
    assert "�" not in txt and "“industrial leadership”" in txt and "<p>" in html


def test_a_publication_is_its_english_pdf(monkeypatch):
    asked = []
    monkeypatch.setattr(eca, "http_get", lambda url: asked.append(url) or SimpleNamespace(content=b"%PDF-1.7 x"))
    monkeypatch.setattr(eca, "extract_pdf", lambda raw: "Speech by the President of the Court. " * 20)
    txt, html, kind = eca.own_body("https://www.eca.europa.eu/en/publications/AR-2025-speech-CONT", "publication")
    assert asked == ["https://www.eca.europa.eu/ECAPublications/AR-2025-speech-CONT/AR-2025-speech-CONT_EN.pdf"]
    assert kind == "pdf" and txt.startswith("Speech by") and "AR-2025-speech-CONT_EN.pdf" in html


def test_a_page_that_is_not_a_pdf_is_no_publication_body(monkeypatch):
    monkeypatch.setattr(eca, "http_get", lambda url: SimpleNamespace(content=b"<html>Not found</html>"))
    assert eca.own_body("https://www.eca.europa.eu/en/publications/XX-1", "publication") == (None, None, None)


def test_the_body_fetcher_takes_the_same_route(monkeypatch):
    fetcher = importlib.import_module("scripts.fetch_institutional_news_bodies")
    monkeypatch.setattr(eca, "http_get", lambda url: SimpleNamespace(content=BODY * 2))
    monkeypatch.setattr(fetcher, "_read", lambda *a, **k: (_ for _ in ()).throw(AssertionError("page read")))
    txt, _, err = fetcher.fetch("https://www.eca.europa.eu/en/news/NEWS-SR-2026-24")
    assert err is None and "�" not in txt


def test_the_fetcher_decodes_a_page_without_u_fffd(monkeypatch):
    fetcher = importlib.import_module("scripts.fetch_institutional_news_bodies")
    page = b"<html><body><main><h1>An agency article headline</h1>" + BODY * 3 + b"</main></body></html>"
    monkeypatch.setattr(fetcher, "_read", lambda url, timeout, accept="*/*", with_url=False:
                        (page, url) if with_url else page)
    txt, _, err = fetcher.fetch("https://agency.europa.eu/en/news/an-article")
    assert err is None and "�" not in txt and "“industrial leadership”" in txt
