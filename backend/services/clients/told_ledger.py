"""The told-ledger: what each client has already been sent.

Why (9 Oct 2026). The DPP watch called five items URGENT five mornings running that the
client had received on Monday 5 October: it decides "urgent" from an item's date alone, so a
deadline that has been told stays urgent until it passes, and a genuinely new item has to
compete with the repetition. URGENT has to mean new AND dated.

Design, in four decisions that each exist because the obvious version fails:

1. A TABLE (`client_sent_mails`, migration 286), not a file. The watch runs on Railway from the
   deployed repository; a local or gitignored file would not be there, and a tracked file would
   publish client correspondence in a public repository.
2. No message text is stored. A mail is reduced to what the watch can match on: the identifiers
   it mentioned (normalised URLs, TRIS numbers, OEIL procedure references, Have Your Say
   initiative ids, parliamentary question numbers, ELI/CELEX) and the DATES it mentioned.
3. A deadline counts as told only if its DATE appears in the mail. A consultation that was
   extended, or a workshop that moved, is new again, which is exactly when the client needs
   to hear. Undated items (a news item, a post) are told once their identifier was mentioned.
4. It fails loud. An unreadable ledger, or one with no rows for the client, is reported in the
   verdict text: the watch must not claim "nothing is new" because it could not look.

Pure functions (extract, match, annotate) are separated from the database functions so they
can be tested without one.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import parse_qs, unquote, urlparse

# --------------------------------------------------------------------------
# Tuning
# --------------------------------------------------------------------------

# A deadline we already told about is worth one short reminder this close to it...
REMIND_WITHIN_DAYS = 5
# ...but only if the telling was at least this long ago (a mail sent on Monday does not
# need a reminder on Wednesday).
REMIND_AFTER_DAYS = 7
# Item types whose date is a deadline or an event: "told" requires that date in the mail.
DATED_TYPES = {"consultation", "jrc_workshop"}
# A deadline one day off the one in the mail is the same deadline ("closes at the end of Monday 26" vs
# the portal's 27 at 00:00); a real extension is days or weeks and is new again.
DATE_TOLERANCE_DAYS = 1
# How far back sent mails still count.
LOOKBACK_DAYS = 180

# --------------------------------------------------------------------------
# Dates: day + month name in six languages (accents folded)
# --------------------------------------------------------------------------

_MONTHS = {
    1: ("january", "januari", "janvier", "enero", "gener", "gennaio"),
    2: ("february", "februari", "fevrier", "febrero", "febrer", "febbraio"),
    3: ("march", "maart", "mars", "marzo", "marc"),
    4: ("april", "avril", "abril", "aprile"),
    5: ("may", "mei", "mai", "mayo", "maig", "maggio"),
    6: ("june", "juni", "juin", "junio", "juny", "giugno"),
    7: ("july", "juli", "juillet", "julio", "juliol", "luglio"),
    8: ("august", "augustus", "aout", "agosto", "agost"),
    9: ("september", "septembre", "septiembre", "setembre", "settembre"),
    10: ("october", "oktober", "octobre", "octubre", "ottobre"),
    11: ("november", "novembre", "noviembre"),
    12: ("december", "decembre", "diciembre", "desembre", "dicembre"),
}
_MONTH_NUM = {name: n for n, names in _MONTHS.items() for name in names}
_MONTH_ALT = "|".join(sorted(_MONTH_NUM, key=len, reverse=True))
_DAY_MONTH = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th|er|º|°)?\s*(?:de\s+|del\s+|d['’]\s*|of\s+|\.\s*)?\s*({_MONTH_ALT})\b"
    rf"(?:\s*(?:de\s+|del\s+|,\s*)?(20\d{{2}}))?")
_MONTH_DAY = re.compile(rf"\b({_MONTH_ALT})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s*(20\d{{2}}))?")
_ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_DMY = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d{2})\b")


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


def _mk(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def extract_dates(text: str, sent_on: date) -> list[date]:
    """Every calendar date the message mentions. A date with no year takes the sending
    year, or the next one when it would otherwise lie far in the past (a December mail that
    says "5 January")."""
    t = _fold(text.replace(" ", " "))
    found: set[date] = set()

    def with_year(m: int, d: int, y: str | None) -> date | None:
        if y:
            return _mk(int(y), m, d)
        cand = _mk(sent_on.year, m, d)
        if cand and (sent_on - cand).days > 200:
            cand = _mk(sent_on.year + 1, m, d)
        return cand

    for d_, mon, y in _DAY_MONTH.findall(t):
        dt = with_year(_MONTH_NUM[mon], int(d_), y or None)
        if dt:
            found.add(dt)
    for mon, d_, y in _MONTH_DAY.findall(t):
        dt = with_year(_MONTH_NUM[mon], int(d_), y or None)
        if dt:
            found.add(dt)
    for y, m, d_ in _ISO.findall(t):
        dt = _mk(int(y), int(m), int(d_))
        if dt:
            found.add(dt)
    for d_, m, y in _DMY.findall(t):
        dt = _mk(int(y), int(m), int(d_))
        if dt:
            found.add(dt)
    return sorted(found)


# --------------------------------------------------------------------------
# Identifiers
# --------------------------------------------------------------------------

_URL = re.compile(r"https?://[^\s<>\"']+", re.I)


def _clean_url(u: str) -> str:
    """A link in running text: strip trailing punctuation, and a closing bracket only when it has
    no opening partner inside the link (so ".../EPRS_BRI(2026)791501" survives but "(see https://x)" does not)."""
    while u and u[-1] in ".,;:]}'\"":
        u = u[:-1]
    while u.endswith(")") and u.count(")") > u.count("("):
        u = u[:-1]
    return u
_OEIL = re.compile(r"\b(\d{4}/\d{4}\([A-Z]{3}\))")
_TRIS = re.compile(r"\b(20\d{2}/\d{4}/[A-Z]{2})\b")
_EPQ_A = re.compile(r"\bE-10-(20\d{2})-(\d{6})\b")
_EPQ_B = re.compile(r"\bE-(\d{6})/(20\d{2})\b")
_EPRS = re.compile(r"\bEPRS_[A-Z]{3}\((20\d{2})\)(\d{6})")
_CELEX = re.compile(r"\bCELEX:?(\d{5}[A-Z]\d{4})\b")
_ELI = re.compile(r"/eli/(reg|dir|dec)/(\d{4})/(\d{1,4})\b")
_HYS = re.compile(r"/initiatives/(\d+)")
_ELI_LETTER = {"reg": "R", "dir": "L", "dec": "D"}


def unwrap(url: str) -> str:
    """Gmail wraps links as google.com/url?q=<real>&source=gmail: read the real target."""
    u = urlparse(url)
    if u.netloc.endswith("google.com") and u.path == "/url":
        q = parse_qs(u.query).get("q")
        if q:
            return q[0]
    return url


def normalise_url(url: str) -> str:
    """host + path, lower-cased, no scheme/www/query/fragment/trailing slash. The query is
    kept only where it IS the resource (a YouTube video)."""
    url = unwrap(url).rstrip(".,;")
    u = urlparse(url)
    host = u.netloc.lower().removeprefix("www.")
    path = unquote(u.path).rstrip("/")
    if host in ("youtube.com", "m.youtube.com") and path == "/watch":
        v = parse_qs(u.query).get("v")
        if v:
            return f"{host}/watch?v={v[0]}"          # a video id is case-sensitive: keep it as written
    # Lower-cased on purpose: the same page reaches us as ".../20261002IPR47884/..." from a database row
    # and ".../20261002ipr47884/..." from a typed link, and two pages that differ only by case do not exist
    # on the sites this ledger covers.
    return f"{host}{path}".lower()


def identifiers_from(text: str) -> set[str]:
    """Stable identity keys found in a piece of text (a mail, or a watch item's title and
    URL). Everything is derived from what the text SAYS; nothing is guessed."""
    keys: set[str] = set()
    urls = [unwrap(_clean_url(u)) for u in _URL.findall(text or "")]
    blob = unquote(text or "") + " " + " ".join(unquote(u) for u in urls)
    for u in urls:
        n = normalise_url(u)
        if n and "/" in n:
            keys.add("url:" + n)
        m = _HYS.search(unquote(u))
        if m:
            keys.add("hys:" + m.group(1))
        q = parse_qs(urlparse(u).query)
        for v in q.get("uri", []) + q.get("q", []):
            for c in _CELEX.findall(v):
                keys.add("celex:" + c)
    for m in _OEIL.findall(blob):
        keys.add("oeil:" + m)
    for m in _TRIS.findall(blob):
        keys.add("tris:" + m)
    for y, n in _EPQ_A.findall(blob):
        keys.add(f"epq:{n}/{y}")
    for n, y in _EPQ_B.findall(blob):
        keys.add(f"epq:{n}/{y}")
    for y, n in _EPRS.findall(blob):
        keys.add(f"eprs:{y}/{n}")
    for c in _CELEX.findall(blob):
        keys.add("celex:" + c)
    for kind, y, n in _ELI.findall(blob):
        keys.add(f"celex:3{y}{_ELI_LETTER[kind]}{int(n):04d}")
    return keys


def item_identifiers(item: dict) -> set[str]:
    """Identity keys of one watch hit: its URL, plus any reference in its title."""
    text = " ".join(str(item.get(k) or "") for k in ("url", "title"))
    return identifiers_from(text)


# --------------------------------------------------------------------------
# Matching and annotation (pure)
# --------------------------------------------------------------------------

def _as_date(x) -> date | None:
    if isinstance(x, datetime):
        return x.date()
    return x if isinstance(x, date) else None


def match_told(item: dict, mails: Iterable[dict]) -> dict | None:
    """The most recent entry that already covers this item, or None.

    A deadline-type item (consultation, workshop) is covered only if its date is among the
    dates the message mentioned; any other item is covered by an identifier match alone."""
    keys = item_identifiers(item)
    if not keys:
        return None
    d = _as_date(item.get("d"))
    need_date = item.get("item_type") in DATED_TYPES and d is not None
    for m in sorted(mails, key=lambda r: r["sent_at"], reverse=True):
        if not keys & set(m.get("identifiers") or ()):
            continue
        if need_date and not any(abs((d - md).days) <= DATE_TOLERANCE_DAYS
                                 for md in (m.get("mentioned_dates") or ())):
            continue
        return {"sent_at": m["sent_at"], "subject": m.get("subject", ""),
                "channel": m.get("channel", "email"), "thread_ref": m.get("thread_ref")}
    return None


def annotate(results: dict[str, list[dict]], mails: list[dict], today: date | None = None) -> dict:
    """Mark every hit that was already sent. A told hit is no longer urgent (the original
    flag is kept in `was_urgent`); a told deadline that is close and was told long enough ago
    is flagged `remind`. Returns counts for the verdict line."""
    today = today or date.today()
    told_t: set[str] = set()      # counted by title: one item that matches two scopes is still one item
    cleared_t: set[str] = set()
    remind_t: set[str] = set()
    for hits in results.values():
        for h in hits:
            t = match_told(h, mails)
            if not t:
                continue
            h["told"] = t
            told_t.add(str(h.get("title")))
            if h.get("urgent"):
                h["was_urgent"] = True
                h["urgent"] = False
                cleared_t.add(str(h.get("title")))
            d = _as_date(h.get("d"))
            sent = _as_date(t["sent_at"])
            if (t["channel"] != "dismissed" and h.get("item_type") in DATED_TYPES and d is not None
                    and sent is not None and 0 <= (d - today).days <= REMIND_WITHIN_DAYS
                    and (today - sent).days >= REMIND_AFTER_DAYS):
                h["remind"] = True
                remind_t.add(str(h.get("title")))
    return {"told": len(told_t), "cleared": len(cleared_t), "remind": len(remind_t)}


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------

def load_mails(db, client_key: str, today: date | None = None) -> list[dict]:
    """The client's sent mails inside the look-back window, as plain dicts."""
    from sqlalchemy import text
    today = today or date.today()
    rows = db.execute(text("""
        SELECT sent_at, channel, subject, thread_ref, identifiers, mentioned_dates
        FROM client_sent_mails
        WHERE client_key = :c AND sent_at >= :since
        ORDER BY sent_at DESC"""),
        {"c": client_key, "since": datetime.combine(today - timedelta(days=LOOKBACK_DAYS),
                                                    datetime.min.time(), tzinfo=timezone.utc)}).mappings().all()
    return [dict(r) for r in rows]


def record_mail(db, *, client_key: str, sent_at: datetime, subject: str, identifiers: Iterable[str],
                mentioned_dates: Iterable[date], thread_ref: str | None = None, channel: str = "email",
                source: str = "scan", note: str | None = None) -> str:
    """Insert or update one sent message. Re-recording the same thread updates the row."""
    from sqlalchemy import text
    params = {"c": client_key, "t": sent_at, "ch": channel, "s": subject[:300], "th": thread_ref,
              "ids": sorted(set(identifiers)), "ds": sorted(set(mentioned_dates)),
              "src": source, "n": note}
    if thread_ref:
        row = db.execute(text("""
            INSERT INTO client_sent_mails
                (client_key, sent_at, channel, subject, thread_ref, identifiers, mentioned_dates, source, note)
            VALUES (:c, :t, :ch, :s, :th, :ids, :ds, :src, :n)
            ON CONFLICT (client_key, thread_ref) WHERE thread_ref IS NOT NULL
            DO UPDATE SET sent_at = EXCLUDED.sent_at, channel = EXCLUDED.channel, subject = EXCLUDED.subject,
                          identifiers = EXCLUDED.identifiers, mentioned_dates = EXCLUDED.mentioned_dates,
                          source = EXCLUDED.source, note = EXCLUDED.note
            RETURNING (xmax = 0) AS inserted"""), params).first()
        db.commit()
        return "inserted" if row and row[0] else "updated"
    dup = db.execute(text("SELECT 1 FROM client_sent_mails WHERE client_key=:c AND sent_at=:t AND subject=:s"),
                     params).first()
    if dup:
        return "exists"
    db.execute(text("""
        INSERT INTO client_sent_mails
            (client_key, sent_at, channel, subject, thread_ref, identifiers, mentioned_dates, source, note)
        VALUES (:c, :t, :ch, :s, :th, :ids, :ds, :src, :n)"""), params)
    db.commit()
    return "inserted"
