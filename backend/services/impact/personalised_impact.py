"""
Personalised impact composer.

Inputs
------
- user           ``models.user.User`` — drives personalisation (policy
                 interests, sectors, role_title, organisation, country).
- carriage       ``models.legislative_train.LegislativeCarriage`` — drives
                 the factual layer (title, current status, lead committee,
                 procedure ref, policy areas, ai_summary if any).

Output
------
``ImpactBlock`` — a structured briefing with four sections:
  * ``what_it_is``           One paragraph factually describing the file.
  * ``why_it_touches_you``   One paragraph linking the file's policy areas
                             to the user's interests / sectors.
  * ``what_to_watch``        One paragraph naming the next likely milestone
                             based on status + days in status.
  * ``actions_you_can_take`` Four concrete next actions.

Never fabricates: if no policy overlap, ``why_it_touches_you`` returns an
honest "we have no direct match for your profile" sentence and a
profile-completion CTA. If a field is missing on the carriage, the
sentence using it is dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from models.legislative_train import LegislativeCarriage
from models.user import User


_STATUS_NEXT_STEP = {
    "announced": "tabling by the Commission",
    "legislative_initiative": "tabling of the legislative proposal",
    "tabled": "committee report adoption",
    "close_to_adoption": "plenary vote and Council adoption",
    "completed": "publication in the Official Journal",
    "adopted": "the start of the compliance / transposition window",
    "blocked": "any sign of movement; the file has not progressed in 9+ months",
    "withdrawn": "no further parliamentary action; the file was withdrawn",
}


@dataclass
class ActionLink:
    label: str
    path: str
    rationale: str = ""


@dataclass
class ImpactBlock:
    procedure_ref: Optional[str]
    title: str
    headline: str
    what_it_is: str
    why_it_touches_you: str
    what_to_watch: str
    actions_you_can_take: List[ActionLink] = field(default_factory=list)
    matched_policy_areas: List[str] = field(default_factory=list)
    matched_sectors: List[str] = field(default_factory=list)
    user_profile_was_partial: bool = False

    def to_dict(self) -> dict:
        return {
            "procedure_ref": self.procedure_ref,
            "title": self.title,
            "headline": self.headline,
            "what_it_is": self.what_it_is,
            "why_it_touches_you": self.why_it_touches_you,
            "what_to_watch": self.what_to_watch,
            "actions_you_can_take": [
                {
                    "label": a.label,
                    "path": a.path,
                    "rationale": a.rationale,
                }
                for a in self.actions_you_can_take
            ],
            "matched_policy_areas": self.matched_policy_areas,
            "matched_sectors": self.matched_sectors,
            "user_profile_was_partial": self.user_profile_was_partial,
        }


def _policy_interests_for(user: User) -> List[str]:
    interests = user.policy_interests_list
    if not interests:
        return []
    return [str(x).strip() for x in interests if x and str(x).strip()]


def _sectors_for(user: User) -> List[str]:
    raw = getattr(user, "sectors", None) or []
    if isinstance(raw, str):
        try:
            import json as _json

            raw = _json.loads(raw)
        except Exception:
            raw = []
    return [str(s).strip() for s in raw if s and str(s).strip()]


def _status_str(value) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _compose_what_it_is(carriage: LegislativeCarriage) -> str:
    status_raw = _status_str(carriage.current_status)
    status_text = status_raw.replace("_", " ") if status_raw else None

    parts: List[str] = []
    if status_text:
        parts.append(
            f"This legislative file is currently {status_text}."
        )
    if carriage.lead_committee:
        parts.append(
            f"The lead committee is {carriage.lead_committee} in the European Parliament."
        )
    if carriage.oeil_procedure_ref:
        parts.append(
            f"OEIL procedure reference: {carriage.oeil_procedure_ref}."
        )
    if not parts:
        parts.append("Brubru does not yet have structured status information on this file.")
    return " ".join(parts)


def _compose_why_it_touches_you(
    user: User,
    carriage: LegislativeCarriage,
    matched_policy_areas: Sequence[str],
    matched_sectors: Sequence[str],
) -> tuple[str, bool]:
    """
    Returns ``(why_paragraph, profile_was_partial)``. When the user has
    neither policy interests nor sectors, the paragraph is an honest
    "we can't personalise this yet" sentence and ``profile_was_partial``
    is ``True``.
    """
    interests = _policy_interests_for(user)
    sectors = _sectors_for(user)

    role = (getattr(user, "role_title", None) or "").strip()
    org = (user.organization or "").strip()

    if not interests and not sectors:
        message = (
            "We do not yet know which policy areas and sectors you follow, so "
            "we cannot tell you specifically how this file affects you. "
            "Fill in your profile and Brubru will personalise this section."
        )
        return message, True

    if matched_policy_areas:
        areas = ", ".join(matched_policy_areas[:3])
        head = (
            f"This file touches the policy areas you follow ({areas})."
        )
    else:
        head = (
            "This file does not directly overlap with the policy areas you "
            "follow today."
        )

    middle = ""
    if matched_sectors:
        middle = (
            " It is also relevant to your sector(s): "
            + ", ".join(matched_sectors[:3])
            + "."
        )

    tail = ""
    if role and org:
        tail = (
            f" As {role} at {org}, you may want to track this file to anticipate "
            "obligations and opportunities."
        )
    elif role:
        tail = f" As {role}, you may want to track this file."
    elif org:
        tail = f" As part of {org}, you may want to track this file."

    return f"{head}{middle}{tail}", False


def _compose_what_to_watch(carriage: LegislativeCarriage) -> str:
    status_raw = _status_str(carriage.current_status)
    next_step = _STATUS_NEXT_STEP.get(
        status_raw.lower() if status_raw else "",
        "the next procedural step",
    )
    parts: List[str] = [f"The next thing to watch is {next_step}."]

    days = getattr(carriage, "days_in_current_status", None)
    if days is not None:
        parts.append(
            f"The file has spent {days} days in its current status."
        )
    if getattr(carriage, "is_blocked", False):
        parts.append(
            "It has been flagged as blocked because there has been no progress "
            "in nine months or more."
        )
    return " ".join(parts)


def _suggest_actions(
    user: User, carriage: LegislativeCarriage
) -> List[ActionLink]:
    procedure_ref = carriage.oeil_procedure_ref or ""
    actions: List[ActionLink] = []

    actions.append(
        ActionLink(
            label="Track this file",
            path="/my-eu-bubble?tab=my_files",
            rationale="Brubru will alert you to status changes and amendments.",
        )
    )
    actions.append(
        ActionLink(
            label="Draft an amendment",
            path=f"/amendator?procedure_ref={procedure_ref}" if procedure_ref else "/amendator",
            rationale="Open this file in the Amendator to draft amendments.",
        )
    )

    status_raw = _status_str(carriage.current_status).lower()
    if status_raw in {"adopted", "completed", "close_to_adoption"}:
        actions.append(
            ActionLink(
                label="Run an EU Law Comply check",
                path="/eulawcomply",
                rationale=(
                    "The file is close to adoption or already adopted — run a "
                    "compliance gap analysis on your organisation."
                ),
            )
        )
    else:
        actions.append(
            ActionLink(
                label="Run a position analysis",
                path="/my-eu-bubble?tab=position_analysis",
                rationale="See where Parliament, Council and Commission stand.",
            )
        )

    actions.append(
        ActionLink(
            label="See predictions",
            path="/my-eu-bubble?tab=predictions",
            rationale="Brubru's forecast for the outcome and timeline.",
        )
    )

    return actions


def compose_impact_for_carriage(
    user: User, carriage: LegislativeCarriage
) -> ImpactBlock:
    """Compose the impact block for a given user/carriage pair."""

    user_interests = _policy_interests_for(user)
    user_sectors = _sectors_for(user)

    carriage_policy_areas = list(carriage.policy_areas or [])
    matched_policy_areas = [
        a for a in carriage_policy_areas if a in user_interests
    ]
    # For now sectors share the same column with policy areas in many
    # files; we compute the intersection on the *user's* sector slugs and
    # treat any case-insensitive substring match against the file's policy
    # areas as a sector hit (best-effort grounding, never fabricated).
    matched_sectors: List[str] = []
    if user_sectors and carriage_policy_areas:
        lowered_areas = " ".join(carriage_policy_areas).lower()
        for slug in user_sectors:
            keywords = slug.replace("_", " ").split()
            if any(k in lowered_areas for k in keywords):
                matched_sectors.append(slug)

    why_touches_you, profile_partial = _compose_why_it_touches_you(
        user,
        carriage,
        matched_policy_areas,
        matched_sectors,
    )

    headline_bits = []
    status_str = _status_str(carriage.current_status).replace("_", " ")
    if status_str:
        headline_bits.append(status_str.capitalize())
    if carriage.lead_committee:
        headline_bits.append(carriage.lead_committee)
    headline = " · ".join(headline_bits) if headline_bits else "Active file"

    return ImpactBlock(
        procedure_ref=carriage.oeil_procedure_ref,
        title=carriage.title,
        headline=headline,
        what_it_is=_compose_what_it_is(carriage),
        why_it_touches_you=why_touches_you,
        what_to_watch=_compose_what_to_watch(carriage),
        actions_you_can_take=_suggest_actions(user, carriage),
        matched_policy_areas=matched_policy_areas,
        matched_sectors=matched_sectors,
        user_profile_was_partial=profile_partial,
    )
