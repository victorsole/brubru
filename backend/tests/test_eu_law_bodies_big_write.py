"""A large law text is written as COPY data, text and HTML apart, never as one SQL literal (20 Oct 2026).

18 Oct 2026: the 42 MB text and 42 MB XHTML of 32018R0688, inlined by psycopg2 into one UPDATE, restarted Postgres
twice. No DB: a fake engine records what store() sends.
"""
import csv
import importlib.util
import io
import sys
from pathlib import Path

csv.field_size_limit(sys.maxsize)  # this test's reader; Postgres reads COPY csv without that limit

BACKEND = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fetch_eu_law_bodies", BACKEND / "scripts" / "fetch_eu_law_bodies.py")
feb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(feb)


class _Engine:
    def __init__(self):
        self.tx = []

    def begin(self):
        eng = self

        class _Conn:
            def __enter__(self):
                self.calls = []
                eng.tx.append(self.calls)
                return self

            def __exit__(self, *a):
                return False

            def execute(self, stmt, params=None):
                self.calls.append(("execute", str(stmt), params))

            @property
            def connection(self):
                calls = self.calls

                class _Raw:
                    def cursor(self):
                        class _Cur:
                            def execute(self, sql, args=None):
                                calls.append(("cursor", sql, args))

                            def copy_expert(self, sql, buf):
                                calls.append(("copy", sql, next(csv.reader(io.StringIO(buf.read())))[0]))
                        return _Cur()
                return _Raw()
        return _Conn()


def test_a_large_body_goes_as_copy_data_text_then_html():
    eng = _Engine()
    txt = 'line 1, "quoted"\nline 2' + "x" * 3_000_000
    html = '<p class="a">line 1, "quoted"</p>\n' + "y" * 2_000_000
    feb.store(eng, 7, html, txt)
    assert len(eng.tx) == 2  # one transaction per column
    (t1, t2) = eng.tx
    assert [c[0] for c in t1] == ["cursor", "copy", "cursor"] and t1[1][2] == txt and t1[2][2] == (7,)
    assert "SET body_txt" in t1[2][1]
    assert [c[0] for c in t2] == ["cursor", "copy", "cursor"] and t2[1][2] == html
    assert "SET body_html" in t2[2][1] and "body_fetched_at = now()" in t2[2][1] and t2[2][2] == (len(txt), 7)
    assert all(len(c[1]) < 300 for tx in eng.tx for c in tx)  # no SQL text carries the body


def test_a_small_body_keeps_the_one_statement():
    eng = _Engine()
    feb.store(eng, 8, "<p>short</p>", "short")
    assert len(eng.tx) == 1 and eng.tx[0][0][0] == "execute" and eng.tx[0][0][2]["txt"] == "short"
