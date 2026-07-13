"""
Brubru curated-procedure overlay for /api/v1/procedures/{reference}.

The raw `legislative_carriages` row is sourced from OEIL on a 6-hour sync and is
necessarily generic and sometimes stale. For a small set of high-salience files,
Brubru maintains a hand-verified, editorially-curated overlay: a plain-English
status, the committee + rapporteur + shadow map, debate highlights, the political
dynamics, related procedures, and links back to Brubru's multilingual deep-dive.

This is the *synthesised, attributed* layer, deliberately NOT a raw dump of the
internal knowledge guide. It is keyed on the OEIL procedure reference and merged
into the DETAIL response under `curated`. EU Inc. (2026/0074(COD)) is the first
entry; the mechanism is generic, so any procedure with a Brubru deep-dive can be
added here.

Maintenance: when the underlying file moves (new committee vote, rapporteur,
trilogue), refresh the matching entry and bump `as_of`. Verify every fact against
the EP Legislative Observatory + primary committee documents before editing.
"""

from typing import Optional

from pydantic import BaseModel, Field


class CuratedKeyFact(BaseModel):
    label: str
    value: str


class CuratedActor(BaseModel):
    committee: str
    role: str = Field(description="lead | opinion | budgetary")
    rapporteur: Optional[str] = None
    group: Optional[str] = None
    appointed: Optional[str] = None
    note: Optional[str] = None


class CuratedShadow(BaseModel):
    name: str
    group: str
    country: Optional[str] = None


class CuratedEvent(BaseModel):
    date: str
    event: str


class CuratedDebate(BaseModel):
    date: str
    forum: str
    summary: str
    source_url: Optional[str] = None


class CuratedRelatedProcedure(BaseModel):
    reference: str
    title: str
    relationship: str
    url: Optional[str] = None


class CuratedLink(BaseModel):
    label: str
    url: str


class BrubruCuration(BaseModel):
    """Hand-verified Brubru editorial overlay for a single procedure."""

    curated: bool = True
    as_of: str = Field(description="Date this overlay was last verified (ISO).")
    headline: str
    editorial_summary: str
    plain_status: str
    deep_dive: dict = Field(
        default_factory=dict,
        description="Language-code -> Brubru deep-dive URL.",
    )
    key_facts: list[CuratedKeyFact] = Field(default_factory=list)
    lead_committee: Optional[CuratedActor] = None
    opinion_committees: list[CuratedActor] = Field(default_factory=list)
    shadow_rapporteurs: list[CuratedShadow] = Field(default_factory=list)
    committee_notes: Optional[str] = None
    timeline_highlights: list[CuratedEvent] = Field(default_factory=list)
    key_debates: list[CuratedDebate] = Field(default_factory=list)
    political_dynamics: Optional[str] = None
    related_procedures: list[CuratedRelatedProcedure] = Field(default_factory=list)
    sources: list[CuratedLink] = Field(default_factory=list)
    attribution: str


_DEEP_DIVE_BASE = "https://brubru.beresol.eu/eu-inc"

_EU_INC = BrubruCuration(
    as_of="2026-07-13",
    headline=(
        "EU Inc. (the 28th Regime): a single, optional, fully-digital EU company "
        "form, now in the European Parliament's JURI committee."
    ),
    editorial_summary=(
        "EU Inc. is the Commission's proposal for one harmonised, optional corporate "
        "legal form that a company can choose instead of navigating 60-plus national "
        "limited-liability regimes across the 27 Member States. A company can be "
        "registered in 48 hours, for at most EUR 100, with zero minimum capital, fully "
        "online, and carry a single set of rules across its whole life cycle. It is the "
        "centrepiece of the wider '28th regime', not the entirety of it: complementary "
        "measures on taxation, digital identity and employment are being built around "
        "it. The file is the Commission's direct answer to the Draghi and Letta reports "
        "on European competitiveness. The same rapporteur, Renew's tax-side counterpart "
        "in ECON, and a full spread of committee shadows are now shaping it in "
        "Parliament, with a political commitment to conclude by the end of 2026."
    ),
    plain_status=(
        "In committee. During the 13-17 July 2026 committee week (the last before the "
        "summer recess of 27 July to 21 August), EU Inc. is on the agenda of three "
        "committees on the same day, Wednesday 15 July 2026: the lead committee JURI "
        "(committee consideration, rapporteur Repasi), ECON as an opinion-giving committee, "
        "and EMPL for an exchange of views with stakeholders on the 28th regime. This is "
        "the first concurrent committee-stage activity across all three since the file was "
        "referred. No committee report or final committee vote has been tabled yet; the "
        "Commission tabled the proposal on 18 March 2026 and the European Parliament "
        "referred it to JURI on 18 May 2026 (committee dossier JURI/10/05459). The first "
        "committee debate was a JURI exchange of views on 4 May 2026. The three institutions "
        "have committed to concluding negotiations by the end of 2026."
    ),
    deep_dive={
        "en": f"{_DEEP_DIVE_BASE}/index.html",
        "es": f"{_DEEP_DIVE_BASE}/es.html",
        "ca": f"{_DEEP_DIVE_BASE}/ca.html",
        "fr": f"{_DEEP_DIVE_BASE}/fr.html",
        "it": f"{_DEEP_DIVE_BASE}/it.html",
        "nl": f"{_DEEP_DIVE_BASE}/nl.html",
    },
    key_facts=[
        CuratedKeyFact(label="Instrument", value="Regulation (directly applicable in all Member States)"),
        CuratedKeyFact(label="Legal basis", value="Article 114 TFEU"),
        CuratedKeyFact(label="Minimum capital", value="EUR 0"),
        CuratedKeyFact(label="Registration time", value="48 hours via a central EU interface"),
        CuratedKeyFact(label="Maximum registration cost", value="EUR 100"),
        CuratedKeyFact(label="Commission documents", value="COM(2026) 321 (proposal), COM(2026) 320 (Communication)"),
        CuratedKeyFact(label="Lead Commissioner", value="Michael McGrath (DG Justice and Consumers)"),
        CuratedKeyFact(label="Signature feature", value="EU Employee Stock Options (EU-ESO), taxed only at disposal"),
        CuratedKeyFact(label="Target date of application", value="2028"),
        CuratedKeyFact(label="Estimated impact", value="~308,000 EU Inc. companies over 10 years; EUR 328-440m in savings"),
        CuratedKeyFact(label="Negotiation target", value="Agreement by end of 2026"),
    ],
    lead_committee=CuratedActor(
        committee="JURI",
        role="lead",
        rapporteur="René Repasi",
        group="S&D",
        appointed="2026-04-23",
        note="Germany (SPD); also led the predecessor own-initiative report 2025/2079(INL).",
    ),
    opinion_committees=[
        CuratedActor(committee="ECON", role="opinion", rapporteur="Aurore Lalucq", group="S&D", appointed="2026-05-18", note="Chair on behalf of the committee (France)."),
        CuratedActor(committee="EMPL", role="opinion", rapporteur="Johan Danielsson", group="S&D", appointed="2026-05-13", note="Sweden."),
        CuratedActor(committee="BUDG", role="budgetary", note="Decided NOT to give an opinion."),
    ],
    shadow_rapporteurs=[
        CuratedShadow(name="Axel Voss", group="EPP", country="Germany"),
        CuratedShadow(name="Pascale Piera", group="PfE", country="France"),
        CuratedShadow(name="Mario Mantovani", group="ECR", country="Italy"),
        CuratedShadow(name="Pascal Canfin", group="Renew", country="France"),
        CuratedShadow(name="Kira Marie Peter-Hansen", group="Greens/EFA", country="Denmark"),
        CuratedShadow(name="Arash Saeidi", group="The Left", country="France"),
    ],
    committee_notes=(
        "JURI is lead; ECON and EMPL give opinions; BUDG declined. In the 13-17 July 2026 "
        "committee week the file reaches all three active committees at once: JURI, ECON and "
        "EMPL each take it up on Wednesday 15 July 2026 (EMPL via a stakeholder exchange of "
        "views), the first time the file is worked in three committees the same week. The "
        "six shadows span the entire political spectrum, from EPP to The Left."
    ),
    timeline_highlights=[
        CuratedEvent(date="2025-12-17", event="EP own-initiative report A10-0269/2025 tabled (predecessor INL, 2025/2079(INL))."),
        CuratedEvent(date="2026-03-18", event="Commission tables the EU Inc. proposal, COM(2026) 321."),
        CuratedEvent(date="2026-04-23", event="René Repasi (S&D) appointed JURI rapporteur."),
        CuratedEvent(date="2026-05-04", event="First JURI exchange of views on the proposal."),
        CuratedEvent(date="2026-05-18", event="JURI committee referral announced in plenary (dossier JURI/10/05459)."),
        CuratedEvent(date="2026-06-03", event="ECON adopts the companion '28th tax regime' report (2025/2211(INI))."),
        CuratedEvent(date="2026-07-15", event="Committee week: EU Inc. on the agenda of JURI (lead), ECON (opinion) and EMPL (stakeholder exchange of views) the same day, the first concurrent three-committee activity on the file."),
        CuratedEvent(date="2026-12-31", event="Three-institution target to conclude negotiations."),
    ],
    key_debates=[
        CuratedDebate(
            date="2026-05-04",
            forum="JURI committee exchange of views",
            summary=(
                "Commissioner McGrath presented the framework (48h / EUR 100 / EUR 0 "
                "capital, BRIS, EU-ESO, simplified insolvency) and stressed it leaves "
                "labour rights, taxation and AML untouched, applying the employee-"
                "participation rules of the Member State of the registered office. "
                "Rapporteur Repasi welcomed it 'except for the name' and pressed for "
                "stronger guardrails against forum-shopping and harmful tax competition. "
                "ECR shadow Mantovani warned that fragmentation on tax and insolvency "
                "leaves scale-ups underserved; Renew shadow Canfin reaffirmed support and "
                "pressed on employee stock options and frictionless conversion."
            ),
            source_url="https://multimedia.europarl.europa.eu/en/webstreaming/committee-on-legal-affairs-ordinary-meeting_20260504-1545-COMMITTEE-JURI",
        ),
    ],
    political_dynamics=(
        "A broad pro-integration coalition (S&D rapporteur plus EPP, Renew and Greens) "
        "anchors the file, the same constellation that carried the 2025 own-initiative "
        "report. S&D pushes worker-protection and anti-circumvention guardrails; the "
        "Greens add tax-fairness conditions; ECR and PfE defend Member State sovereignty. "
        "The sharpest fault line sits on the companion tax track (2025/2211(INI)): the "
        "majority wants an optional tax module, some of it via qualified-majority voting "
        "or enhanced cooperation, while ECR and PfE defend tax unanimity. The EU Inc. "
        "corporate file itself is broadly supported; the contested ground is how far the "
        "'28th regime' extends beyond company law into tax and employee participation."
    ),
    related_procedures=[
        CuratedRelatedProcedure(
            reference="2025/2079(INL)",
            title="28th Regime: a new legal framework for innovative companies (EP own-initiative)",
            relationship="Predecessor own-initiative report (Repasi) that triggered the Commission proposal.",
            url="https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025/2079(INL)",
        ),
        CuratedRelatedProcedure(
            reference="2025/2211(INI)",
            title="Feasibility of a 28th tax regime and its potential to support EU competitiveness",
            relationship="Companion 'tax module' own-initiative (ECON, rapporteur Ódor, Renew), adopted in committee 3 June 2026.",
            url="https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025/2211(INI)",
        ),
        CuratedRelatedProcedure(
            reference="2025/0358(COD)",
            title="European Business Wallet",
            relationship="Complementary digital-identity infrastructure the EU Inc. central register builds on.",
            url="https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2025/0358(COD)",
        ),
    ],
    sources=[
        CuratedLink(label="EP Legislative Observatory (OEIL) procedure file", url="https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=2026/0074(COD)"),
        CuratedLink(label="European Commission - EU Inc.", url="https://commission.europa.eu/eu-inc-new-harmonised-corporate-legal-regime_en"),
        CuratedLink(label="Commission press release IP/26/614", url="https://ec.europa.eu/commission/presscorner/detail/en/ip_26_614"),
        CuratedLink(label="Brubru deep-dive (EN)", url=f"{_DEEP_DIVE_BASE}/index.html"),
    ],
    attribution=(
        "Curated and verified by Brubru (https://brubru.beresol.eu), an EU policy "
        "intelligence service by Beresol. Every fact in this overlay is cross-checked "
        "against the European Parliament Legislative Observatory and primary committee "
        "documents as of 4 June 2026. Reuse with attribution to Brubru."
    ),
)


# Registry keyed on the normalised OEIL procedure reference (whitespace stripped,
# upper-cased). Add further high-salience procedures here over time.
_CURATED: dict[str, BrubruCuration] = {
    "2026/0074(COD)": _EU_INC,
}


def _normalise_ref(reference: Optional[str]) -> str:
    return (reference or "").replace(" ", "").upper()


_CURATED_NORMALISED = {_normalise_ref(k): v for k, v in _CURATED.items()}


def get_curation(reference: Optional[str]) -> Optional[BrubruCuration]:
    """Return the Brubru curated overlay for a procedure reference, or None."""
    return _CURATED_NORMALISED.get(_normalise_ref(reference))
