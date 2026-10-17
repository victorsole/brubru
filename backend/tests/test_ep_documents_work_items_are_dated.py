"""Committee work items carry a document_date: the committee referral (15 Oct 2026).

574 of 575 work items in GovClipping's walk served document_date null (no committee vote
yet). Victor's decision (2 Oct 2026): date them by the procedure's committee referral, read
from its OEIL key events, while the merge keeps ordering on vote_date."""
import asyncio
import inspect
import uuid
from datetime import date, datetime

from api.v1 import ep_entities as m


class _Q:
    def __init__(self, rows):
        self.rows = rows

    def __getattr__(self, name):
        return lambda *a, **k: self

    def with_entities(self, *cols):
        # the merge reads (id, date) keys first, then the page's whole rows (17 Oct 2026)
        return _Q([tuple(getattr(r, c.key) for c in cols) for r in self.rows])

    def count(self):
        return len(self.rows)

    def all(self):
        return self.rows


class _DB:
    def __init__(self, by_model):
        self.by_model = by_model

    def query(self, model, *a):
        return _Q(self.by_model.get(getattr(model, "__name__", ""), []))


def _call(**given):
    fn = m.list_ep_documents
    kw = {n: given.get(n) for n in inspect.signature(fn).parameters}
    kw.update(given)
    out = fn(**kw)
    return asyncio.run(out) if inspect.iscoroutine(out) else out


def test_a_work_item_without_a_vote_is_dated_by_its_committee_referral():
    item = m.CommitteeWorkItem(id=uuid.uuid4(), committee_code="TRAN", procedure_ref="2026/0114(COD)",
                               title="Procedure File: 2026/0114(COD)", vote_date=None,
                               last_updated=datetime(2026, 10, 2, 19, 10))
    lc = m.LegislativeCarriage(oeil_procedure_ref="2026/0114(COD)", title="Rail passenger rights",
                               rapporteur_name="Jane DOE",
                               oeil_key_events=[{"date": "2026-04-20", "event_type": "Legislative proposal published"},
                                                {"date": "2026-05-04", "event_type": "Committee referral announced in Parliament, 1st reading"}])
    env = _call(db=_DB({"CommitteeWorkItem": [item], "LegislativeCarriage": [lc]}), limit=50, page=1, request=None)
    got = env.data[0]
    assert got.document_date == date(2026, 5, 4)
    assert got.title == "Rail passenger rights" and got.rapporteur_name == "Jane DOE"


def test_no_referral_no_date():
    assert m._referral_date(None) is None
    lc = m.LegislativeCarriage(oeil_key_events=[{"date": "2026-04-20", "event_type": "Legislative proposal published"}])
    assert m._referral_date(lc) is None
