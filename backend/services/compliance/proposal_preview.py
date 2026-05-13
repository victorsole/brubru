"""
Future-Comply preview.

Surfaces, for an in-flight legislative proposal, a structured "what you
should prepare for if this passes as drafted" block. Built entirely from
real carriage data (status, policy_areas, ai_summary, lead_committee,
days_in_current_status). When the file is already adopted, the composer
points the user at the existing gap-analysis flow rather than fabricating
a preview.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from models.legislative_train import LegislativeCarriage
from models.user import User


PROPOSAL_STAGES = {
    "announced",
    "legislative_initiative",
    "tabled",
    "close_to_adoption",
}
ADOPTED_STAGES = {"adopted", "completed"}


@dataclass
class PreviewObligation:
    label: str
    rationale: str


@dataclass
class FutureComplyPreview:
    procedure_ref: Optional[str]
    title: str
    stage: str  # "proposal" | "adopted" | "other"
    status: str
    headline: str
    summary: str
    likely_obligation_areas: List[PreviewObligation] = field(default_factory=list)
    recommended_next_steps: List[PreviewObligation] = field(default_factory=list)
    deferred_to_adopted_flow: bool = False
    matched_policy_areas: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "procedure_ref": self.procedure_ref,
            "title": self.title,
            "stage": self.stage,
            "status": self.status,
            "headline": self.headline,
            "summary": self.summary,
            "likely_obligation_areas": [
                {"label": o.label, "rationale": o.rationale}
                for o in self.likely_obligation_areas
            ],
            "recommended_next_steps": [
                {"label": s.label, "rationale": s.rationale}
                for s in self.recommended_next_steps
            ],
            "deferred_to_adopted_flow": self.deferred_to_adopted_flow,
            "matched_policy_areas": self.matched_policy_areas,
        }


def _status_str(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _policy_interests_for(user: User) -> List[str]:
    interests = user.policy_interests_list
    if not interests:
        return []
    return [str(x).strip() for x in interests if x and str(x).strip()]


def _classify_stage(status: str) -> str:
    s = status.lower() if status else ""
    if s in PROPOSAL_STAGES:
        return "proposal"
    if s in ADOPTED_STAGES:
        return "adopted"
    return "other"


def compose_future_comply_preview(
    user: User, carriage: LegislativeCarriage
) -> FutureComplyPreview:
    status_str = _status_str(carriage.current_status)
    stage = _classify_stage(status_str)
    user_interests = _policy_interests_for(user)
    carriage_policy_areas = list(carriage.policy_areas or [])
    matched = [a for a in carriage_policy_areas if a in user_interests]

    if stage == "adopted":
        return FutureComplyPreview(
            procedure_ref=carriage.oeil_procedure_ref,
            title=carriage.title,
            stage="adopted",
            status=status_str,
            headline="This file is already adopted",
            summary=(
                "The proposal has been adopted. Run a full EU Law Comply gap "
                "analysis to map specific obligations against your "
                "organisation's existing controls."
            ),
            deferred_to_adopted_flow=True,
            matched_policy_areas=matched,
        )

    if stage == "other":
        return FutureComplyPreview(
            procedure_ref=carriage.oeil_procedure_ref,
            title=carriage.title,
            stage="other",
            status=status_str,
            headline="No future-comply preview available",
            summary=(
                "This file is in a status that does not lend itself to a "
                "future-comply preview (it may be withdrawn or blocked)."
            ),
            matched_policy_areas=matched,
        )

    # stage == "proposal"
    headline_bits = [status_str.replace("_", " ").capitalize() if status_str else "Proposal"]
    if carriage.lead_committee:
        headline_bits.append(carriage.lead_committee)
    headline = " · ".join(headline_bits)

    summary_parts: List[str] = []
    if getattr(carriage, "ai_summary", None):
        summary_parts.append(
            "Brubru's reading of the proposal: "
            + str(carriage.ai_summary).strip()
        )
    else:
        summary_parts.append(
            "Brubru does not yet have a structured AI summary for this file."
        )
    if carriage.days_in_current_status is not None:
        summary_parts.append(
            f"It has been in its current stage for "
            f"{carriage.days_in_current_status} days."
        )
    summary = " ".join(summary_parts)

    obligations: List[PreviewObligation] = []
    if matched:
        for area in matched[:3]:
            obligations.append(
                PreviewObligation(
                    label=f"New obligations in {area}",
                    rationale=(
                        f"This proposal sits in {area}, a policy area you follow. "
                        "Expect new reporting, governance or product-level "
                        "obligations if it passes as drafted."
                    ),
                )
            )
    elif carriage_policy_areas:
        for area in carriage_policy_areas[:3]:
            obligations.append(
                PreviewObligation(
                    label=f"Obligations in {area}",
                    rationale=(
                        "This is not a policy area you currently follow, but the "
                        "proposal may still introduce obligations for your sector."
                    ),
                )
            )
    else:
        obligations.append(
            PreviewObligation(
                label="Obligations to be confirmed",
                rationale=(
                    "Brubru has not yet classified the policy areas of this "
                    "proposal. Once committee work begins they will be added."
                ),
            )
        )

    steps: List[PreviewObligation] = [
        PreviewObligation(
            label="Track this file",
            rationale=(
                "Add it to My Files so Brubru alerts you the moment its "
                "status changes or amendments are tabled."
            ),
        ),
        PreviewObligation(
            label="Run a position analysis",
            rationale=(
                "See where Parliament, Council and Commission stand so you "
                "know which obligations are likely to survive trilogue."
            ),
        ),
        PreviewObligation(
            label="Draft a Brubru position paper",
            rationale=(
                "Use the Documents tab to draft a position you can share with "
                "rapporteurs and shadows."
            ),
        ),
    ]

    return FutureComplyPreview(
        procedure_ref=carriage.oeil_procedure_ref,
        title=carriage.title,
        stage="proposal",
        status=status_str,
        headline=headline,
        summary=summary,
        likely_obligation_areas=obligations,
        recommended_next_steps=steps,
        matched_policy_areas=matched,
    )
