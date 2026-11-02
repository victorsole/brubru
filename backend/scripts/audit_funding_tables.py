#!/usr/bin/env python3.12
"""The five canonical datapoints counted over WHOLE tables behind the funding lists (register O139, 2 Nov 2026).

scripts/audit_funding_datapoints.py reads what a few rows of each list serve; that missed 27 outage pages, 139
Share menus and 14,039 funded projects created after their last change, none of them on a page it read. This
counts them on the database side, reads no bodies back, and exits 1 on a value that is simply wrong:

  no public_url | an outage page or Share menu as text | a call or tender dated ahead | no creation_date |
  creation_date after the last change

Missing dates and short texts are printed, not failed: the data-quality backlog (O109, O110, O123; Victor,
2 Nov 2026). Stored text is what these count; a list composes a missing body from the row's own fields.

    python3.12 scripts/audit_funding_tables.py      # from backend, with DATABASE_URL
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text

FAILS = ("url_null", "outage", "share", "doc_future", "created_null", "created_after_change")
_OUTAGE = "substr({b},1,120) LIKE '%Сървърът е временно недостъпен%'"
_SHARE = "position('Mastodon' in substr({b},1,300))>0 AND position('Facebook' in substr({b},1,300))>0"


def _select(table, url, body, doc, deadline, created, changed, where="true"):
    has_body = body is not None
    return f"""SELECT count(*) AS n,
      count(*) FILTER (WHERE {url} IS NULL OR {url} = '' OR {url} NOT LIKE 'http%') AS url_null,
      {f"count(*) FILTER (WHERE {_OUTAGE.format(b=body)})" if has_body else "0"} AS outage,
      {f"count(*) FILTER (WHERE {_SHARE.format(b=body)})" if has_body else "0"} AS share,
      {f"count(*) FILTER (WHERE {body} IS NULL OR btrim({body}) = '')" if has_body else "0"} AS no_text,
      {f"count(*) FILTER (WHERE octet_length({body}) < 200)" if has_body else "0"} AS short_text,
      count(*) FILTER (WHERE {doc} IS NULL) AS doc_null,
      count(*) FILTER (WHERE {doc}::date > current_date) AS doc_future,
      {f"count(*) FILTER (WHERE {doc}::date = {deadline}::date)" if deadline else "0"} AS doc_is_deadline,
      count(*) FILTER (WHERE {created} IS NULL) AS created_null,
      count(*) FILTER (WHERE {created} > {changed} + interval '1 second') AS created_after_change
      FROM {table} WHERE {where}"""


_AGENCY = "item_type IN ('tender','call','grant','eoi_call','framework') AND body_code <> 'commission'"
TABLES = {
    "agency calls and tenders (economy_items)": _select("economy_items", "public_url", "body_txt", "document_date", "deadline", "creation_date", "updated_at", _AGENCY),
    "TED (tenders)": _select("tenders", "ted_url", "description", "publication_date", "submission_deadline", "created_at", "updated_at"),
    "F&T calls for tenders": _select("ft_calls_for_tenders", "source_url", "description", "published_at", "deadline", "first_seen_at", "last_updated"),
    "F&T calls for proposals": _select("ft_calls_for_proposals", "source_url", "description", "published_at", "deadline", "first_seen_at", "last_updated"),
    "cascade calls": _select("ft_cascade_calls", "source_url", "description", "published_at", "deadline", "first_seen", "last_updated"),
    "funded projects": _select("ft_funded_projects", "source_url", "objective", "CASE WHEN published_at::date <= current_date THEN published_at WHEN start_date <= current_date THEN start_date::timestamp END", None, "first_seen", "last_updated"),
    "TED award notices": _select("ted_award_notices", "public_url", "body_txt", "publication_date", None, "first_seen", "last_updated"),
    "FTS recipients (economy_items)": _select("economy_items", "public_url", "body_txt", "document_date", None, "creation_date", "updated_at", "body_code='commission' AND item_type='funding_recipient'"),
    "partner announcements": _select("ft_partner_search_announcements", "public_url", None, "first_seen", None, "first_seen", "last_updated"),
    "cohesion allocations": _select("eu_cohesion_finances", "public_url", "body_txt", "document_date", None, "created_at", "updated_at"),
    "cohesion outcomes": _select("eu_cohesion_outcomes", "public_url", "body_txt", "document_date", None, "created_at", "updated_at"),
    "CAP payments": _select("eu_cap_payments", "public_url", "body_txt", "document_date", None, "created_at", "updated_at"),
    "Solidarity Fund": _select("eu_solidarity_fund", "public_url", "body_txt", "document_date", None, "created_at", "updated_at"),
}


def main() -> int:
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    bad = 0
    with engine.connect() as c:
        c.execute(text("SET statement_timeout = '180s'"))
        for name, sql in TABLES.items():
            row = dict(c.execute(text(sql)).mappings().one())
            fails = {k: row[k] for k in FAILS if row[k]}
            rest = {k: v for k, v in row.items() if k not in FAILS and k != "n" and v}
            bad += bool(fails)
            print(f"[{'FAIL' if fails else 'OK'}] {name}: {row['n']} rows; {fails or ''} {rest or ''}".rstrip())
    print(f"[DONE] tables={len(TABLES)} failing={bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
