"""Is a named party an organisation? One rule for every source that does not say (27 Oct 2026).

TED never marks a winner as a person or an organisation (351840-2025 names three individual experts
beside a company), and the F&T Portal's Partner Search lists sole traders and individuals with their
own PIC as organisations, with no natural-person field. Victor's rule (27 Oct 2026): no person
profiles. A name carrying a legal form or an organisation word is an organisation's.
"""
from __future__ import annotations

import re
from typing import Optional

# PostgreSQL's pattern (\m, \M: a word's start and end), used in SQL as it is.
ORG_FORM = (
    r"\m(s\.?a|s\.?l\.?u?|s\.?a\.?s|s\.?a\.?r\.?l|s\.?r\.?l|s\.?p\.?a|s\.?r\.?o|d\.?o\.?o|b\.?v|n\.?v|u\.?a|e\.?v|"
    r"gmbh|ltd|limited|llp|llc|plc|inc|corp|ag|kg|ohg|asbl|aisbl|ivzw|vzw|oy|oyj|ab|as|a/s|aps|kft|zrt|uab|sia|ou|oü|"
    r"ltda|eurl|gie|eeig|ike|epe|ae|ry|onlus|sp\.? ?z\.? ?o\.? ?o|zoo|sp[oó][lł]ka|co|company|group|consult\w*|"
    r"institut\w*|universit\w*|association|foundation|stiftung|fondation|fondazione|fundacja|fundaci[oó]n|centre|"
    r"center|agency|services?|solutions|partners|international|ministry|minist[eè]re|office|council|bank|"
    r"cooperati\w*|coöperatief|societ[aà]|aktiengesellschaft)\M"
)
# The same pattern for Python's re (\b for both ends).
ORG_FORM_RE = re.compile(ORG_FORM.replace(r"\m", r"\b").replace(r"\M", r"\b"), re.I)

# Partner Search: the types a person's own registration takes (measured 27 Oct 2026: declared
# profiles typed Other, SME or private for-profit held personal names; NGOs, education and research
# establishments and public bodies did not).
PERSON_LIKE_TYPES = frozenset({"Other", "Small or medium-size enterprise", "Private for profit organisation"})


def has_org_form(name: Optional[str]) -> bool:
    """True when the name carries a legal form, an organisation word or a digit."""
    return bool(name) and (bool(ORG_FORM_RE.search(name)) or bool(re.search(r"\d", name)))


def may_be_a_person(name: Optional[str], organisation_type: Optional[str], registration_status: Optional[str]) -> bool:
    """A Partner Search profile left out with its announcements (Victor, 27 Oct 2026): self-registered
    (declared, not validated by the Commission, or no profile to say), of a type a person registers as,
    and named with no legal form, organisation word or digit. A validated profile is always kept; a
    nameless one is not a profile of anyone and is kept."""
    # As measured and approved: declared profiles (or none to say); sleeping, suspended and blocked
    # registrations (56 on 27 Oct 2026) were not in the measurement and are kept.
    if registration_status not in (None, "DECLARED") or organisation_type not in PERSON_LIKE_TYPES or not name:
        return False
    return not has_org_form(name)
