"""Register O65 (23 Oct 2026): a corrigendum that corrects an act's title date; its text as the corrigenda print it."""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from scripts.fix_eu_laws_corrigendum_dates import decide  # noqa: E402
from scripts.leg_folder import title_date_corrections as corrected_dates  # noqa: E402

# 32006D0635R(01), the helpdesk's example
EURATOM = ("Corrigendum to Commission Decision 2006/635/Euratom of 4 April 2006 on the conclusion ( Official Journal of "
           "the European Union L 261 of 22 September 2006 ) On the cover in the contents and on page 26 in the title and "
           "the signature: for: 4 April 2006 , read: 4 April 2005 .")
# 32022D2417R(01): ellipses, then a numbered second correction
ELLIPSIS = ("On page 1, the title on the contents page and the title on page 1: for: … of 26 July 2022 … , read: … of "
            "5 December 2022 … . 2. On page 3, where the place and date of adoption are cited: for: Done at Brussels, "
            "26 July 2022 . , read: Done at Brussels, 5 December 2022 . .")
# 32019D1798R(01): the date glued to nothing, a place changed with it
GLUED = ("on page 1, in the title: for: Decision 2019/1798of the European Parliament and of the Council of 14 October "
         "2019 appointing the European Chief Prosecutor , read: Decision (EU) 2019/1798 of the European Parliament and "
         "of the Council of 23 October 2019 appointing the European Chief Prosecutor ; on page 2: for: Done at "
         "Luxembourg, 14 October 2019 . , read: Done at Strasbourg, 23 October 2019 . .")
# a corrigendum that corrects something else: an article, no date
OTHER = "On page 5, Article 2(1): for: 'Member States shall' , read: 'Member States may' ."
# two corrections in one sentence, the first without a date: the second must not be swallowed by the first's "read:"
TWO = "Article 1: for: 'shall' , read: 'may' ; title and signature: for: 3 March 2022 , read: 2 March 2022 ."


def _pairs(text, celex=None):
    return [c[:2] for c in corrected_dates(text, celex)]


def test_the_pairs_each_shape_states():
    assert _pairs(EURATOM) == [("2006-04-04", "2005-04-04")]
    assert _pairs(ELLIPSIS) == [("2022-07-26", "2022-12-05")] * 2
    assert _pairs(GLUED) == [("2019-10-14", "2019-10-23")] * 2
    assert _pairs(OTHER) == []
    assert _pairs(TWO) == [("2022-03-03", "2022-03-02")]


def test_stated_means_the_correction_says_it_is_the_acts_own_date():
    """Register O66: the place before "for:" names the title, signature or adoption date, or the corrected text quotes
    the act's number."""
    assert [c[2] for c in corrected_dates(EURATOM)] == [True]          # "in the title and the signature"
    assert [c[2] for c in corrected_dates(ELLIPSIS)] == [True, True]   # "the title ...", "place and date of adoption"
    assert [c[2] for c in corrected_dates(GLUED)] == [True, False]     # "in the title"; "on page 2" alone says nothing
    assert [c[2] for c in corrected_dates(GLUED, "32019D1798")] == [True, False]  # "Done at ..." quotes no number
    assert [c[2] for c in corrected_dates(TWO)] == [True]               # "title and signature", after an Article fix
    cover = ("On the cover and on page 7: for: \u2018Commission Implementing Decision (EU) 2018/1109 of 1 August 2018 "
             "renewing the authorisation\u2019 , read: \u2018Commission Implementing Decision (EU) 2018/1109 of 3 August "
             "2018 renewing the authorisation\u2019 .")
    assert corrected_dates(cover, "32018D1109") == [("2018-08-01", "2018-08-03", True)]   # quotes 2018/1109
    assert corrected_dates(cover, "32018D1110") == [("2018-08-01", "2018-08-03", False)]  # another act's number
    assert corrected_dates(cover, "32018D0110") == [("2018-08-01", "2018-08-03", False)]  # 2018/110 is not 2018/1109
    # the corrigendum's own heading ("... on the signature of an Agreement") is not where the correction applies
    heading = ("Corrigendum to Council Decision (EU) 2020/1 of 12 May 2020 on the signature, on behalf of the Union, "
               "of an Agreement ( Official Journal of the European Union L 1 of 13 May 2020 ) On page 5, Article 3: "
               "for: \u2018from 12 May 2020\u2019 , read: \u2018from 15 May 2020\u2019 .")
    assert corrected_dates(heading, "32020D0001") == [("2020-05-12", "2020-05-15", False)]


def test_three_readings_must_agree():
    pairs = corrected_dates(EURATOM)
    assert decide("2006-04-04", pairs, ["2005-04-04"]) == ("2005-04-04", None)
    # Cellar disagrees with the corrigendum: left
    assert decide("2006-04-04", pairs, ["2006-04-04"])[0] is None
    # the stored date is not the one the corrigendum corrects: left
    assert decide("2005-04-04", pairs, ["2005-04-04"])[0] is None
    # two corrigenda correct the same date to different dates: left
    assert decide("2006-04-04", pairs + [("2006-04-04", "2006-05-04")], ["2005-04-04"])[0] is None
