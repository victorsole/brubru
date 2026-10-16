"""The redaction filter must keep uvicorn's access-log arguments intact (16 Oct 2026).

From 9 Aug to 16 Oct 2026 the filter collapsed record.args into the message; uvicorn's
AccessFormatter then failed to unpack them and every request was logged as a
"--- Logging error ---" traceback instead of an access line.
"""
import logging

from uvicorn.logging import AccessFormatter

from core.log_redaction import REDACTED, SecretRedactingFilter


def _access_record(path: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uvicorn.access", level=logging.INFO, pathname=__file__, lineno=1,
        msg='%s - "%s %s HTTP/%s" %d', args=("1.2.3.4:0", "GET", path, "1.1", 200), exc_info=None,
    )


def test_access_record_still_formats_after_the_filter():
    rec = _access_record("/api/v2/news/all?limit=10")
    assert SecretRedactingFilter().filter(rec) is True
    assert isinstance(rec.args, tuple) and len(rec.args) == 5
    line = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False).format(rec)
    assert "GET /api/v2/news/all?limit=10 HTTP/1.1" in line
    assert "200" in line


def test_a_key_in_the_access_path_is_still_redacted():
    rec = _access_record("/api/v2/news/all?api_key=brubru_live_secret123&limit=10")
    SecretRedactingFilter().filter(rec)
    line = AccessFormatter('%(client_addr)s - "%(request_line)s" %(status_code)s', use_colors=False).format(rec)
    assert "brubru_live_secret123" not in line
    assert REDACTED in line
    assert "limit=10" in line


def test_other_records_keep_the_format_then_scrub_behaviour():
    rec = logging.LogRecord("httpx", logging.INFO, __file__, 1, "GET %s", ("https://x/?key=abc",), None)
    SecretRedactingFilter().filter(rec)
    assert rec.args == ()
    assert "abc" not in rec.getMessage() and REDACTED in rec.getMessage()
