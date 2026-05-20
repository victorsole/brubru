"""
Action Router for Brubru Chat

Computes deterministic action buttons from entities and intent already
detected by the context builder. Pure function, no API calls, no DB queries.

Actions appear as clickable buttons below AI chat responses, enabling
users to track files, launch Document Generator, open Amendator, etc.
"""

import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Set

logger = logging.getLogger(__name__)

MAX_ACTIONS = 3


@dataclass
class ChatAction:
    """A single executable action button shown below an AI chat response."""
    action_type: str   # "track_file" | "generate_document" | "open_amendator" | "view_prediction" | "view_calendar"
    label: str         # e.g. "Track 2021/0106(COD)"
    icon: str          # MDI icon class, e.g. "mdi-star-outline"
    colour: str        # Hex colour for the button
    route: Optional[str] = None           # Frontend route to navigate to
    params: dict = field(default_factory=dict)
    requires_auth: bool = True
    pre_user_label: Optional[str] = None  # CTA label for pre-users

    def to_dict(self) -> dict:
        return asdict(self)


def compute_actions(
    entities,
    drafting_intent,
    has_train_match: bool,
    is_pre_user: bool,
    tracked_refs: Set[str],
) -> List[ChatAction]:
    """
    Compute up to MAX_ACTIONS action buttons from context data.

    Args:
        entities: ExtractedEntities from context_builder
        drafting_intent: DraftingIntent from context_builder (or None)
        has_train_match: Whether legislative train files were found in DB
        is_pre_user: Whether user is anonymous (not signed up)
        tracked_refs: Set of procedure refs the user already tracks

    Returns:
        List of ChatAction (max 3), priority-ordered.
    """
    actions: List[ChatAction] = []

    proc_refs = getattr(entities, 'procedure_references', []) or []
    celex_nums = getattr(entities, 'celex_numbers', []) or []
    article_refs = getattr(entities, 'article_references', []) or []
    committee_codes = getattr(entities, 'committee_codes', []) or []
    # Phase 4: Tenderator bridge entities
    funding_topic_ids = getattr(entities, 'funding_topic_ids', []) or []
    funding_programmes = getattr(entities, 'funding_programmes', []) or []

    is_drafting = drafting_intent and getattr(drafting_intent, 'is_drafting_query', False)

    # --- Priority 1: Track file ---
    for ref in proc_refs:
        if len(actions) >= MAX_ACTIONS:
            break
        if ref in tracked_refs:
            continue  # Already tracking
        actions.append(ChatAction(
            action_type="track_file",
            label=f"Track {ref}",
            icon="mdi-star-outline",
            colour="#9b51e0",
            params={"procedure_ref": ref},
            requires_auth=True,
            pre_user_label="Sign up to track legislation",
        ))

    # --- Priority 2: Generate document (drafting intent) ---
    if is_drafting and len(actions) < MAX_ACTIONS:
        doc_type = getattr(drafting_intent, 'document_type', '') or 'position_paper'
        topic = getattr(drafting_intent, 'topic', '') or ''

        # Map legacy / chat-side names to the wizard's document types.
        # The wizard handles: position_paper, mep_briefing, talking_points,
        # resolution, ep_question. Any other intent falls back to position_paper.
        wizard_aliases = {
            'briefing': 'mep_briefing',
            'mep_briefing': 'mep_briefing',
            'talking_points': 'talking_points',
            'resolution': 'resolution',
            'ep_question': 'ep_question',
            'position_paper': 'position_paper',
        }
        wizard_type = wizard_aliases.get(doc_type, 'position_paper')

        doc_type_labels = {
            'position_paper': 'Position paper',
            'mep_briefing': 'MEP briefing',
            'talking_points': 'Talking points',
            'resolution': 'EP resolution',
            'ep_question': 'EP question',
        }
        label = f"Generate {doc_type_labels.get(wizard_type, wizard_type.replace('_', ' '))}"

        # Route directly into the Documents tab with the wizard pre-opened so
        # the chat hand-off does not land on a dead /main state.
        route = (
            f"/my-eu-bubble?tab=documents&openWizard=1"
            f"&docType={wizard_type}"
            + (f"&topic={topic}" if topic else "")
        )

        actions.append(ChatAction(
            action_type="generate_document",
            label=label,
            icon="mdi-file-edit-outline",
            colour="#0693e3",
            route=route,
            params={"document_type": wizard_type, "topic": topic},
            requires_auth=True,
            pre_user_label="Sign up to generate documents",
        ))

    # --- Priority 3a: Open Amendator (CELEX detected, not drafting).
    # Previously gated behind article_refs, which produced an empty actions
    # strip whenever the user cited a CELEX without naming an article. The
    # Amendator opens fine on the whole act, so the gate is unnecessary
    # and was actively dropping value on the floor.
    if not is_drafting and celex_nums and len(actions) < MAX_ACTIONS:
        celex = celex_nums[0]
        article_hint = article_refs[0] if article_refs else None
        label = f"Open Article {article_hint}" if article_hint else f"Open in Amendator"
        params = {"celex": celex}
        route = f"/amendator?celex={celex}"
        if article_hint:
            params["article"] = article_hint
            route = f"/amendator?celex={celex}&article={article_hint}"
        actions.append(ChatAction(
            action_type="open_amendator",
            label=label,
            icon="mdi-scale-balance",
            colour="#059669",
            route=route,
            params=params,
            requires_auth=True,
            pre_user_label="Sign up to use Amendator",
        ))

    # --- Priority 3b: View prediction (proc refs + legislative train match) ---
    if proc_refs and has_train_match and len(actions) < MAX_ACTIONS:
        ref = proc_refs[0]
        actions.append(ChatAction(
            action_type="view_prediction",
            label="View prediction",
            icon="mdi-chart-timeline-variant",
            colour="#9b51e0",
            route=f"/my-eu-bubble?tab=predictions&ref={ref}",
            params={"procedure_ref": ref},
            requires_auth=True,
            pre_user_label="Sign up for predictions",
        ))

    # --- Priority 3c: Open Tenderator when funding context is detected ---
    # If the user mentioned a topic_id or a programme acronym, the action
    # router surfaces a deep link straight into the Tenderator. The link
    # carries a `q=` query so the dashboard pre-filters the unified feed.
    if (funding_topic_ids or funding_programmes) and len(actions) < MAX_ACTIONS:
        if funding_topic_ids:
            q_token = funding_topic_ids[0]
            label = f"Open {q_token[:32]}{'...' if len(q_token) > 32 else ''} in Tenderator"
        else:
            q_token = funding_programmes[0]
            label = f"Open {q_token} in Tenderator"
        actions.append(ChatAction(
            action_type="open_tenderator",
            label=label,
            icon="mdi-piggy-bank-outline",
            colour="#d97706",
            route=f"/tenderator?q={q_token}",
            params={"q": q_token, "programme": funding_programmes[0] if funding_programmes else None},
            requires_auth=True,
            pre_user_label="Sign up to use the Tenderator",
        ))

    # --- Priority 4: View calendar (committee codes, only if room) ---
    if committee_codes and len(actions) < MAX_ACTIONS:
        code = committee_codes[0]
        actions.append(ChatAction(
            action_type="view_calendar",
            label=f"View {code} calendar",
            icon="mdi-calendar",
            colour="#d97706",
            route=f"/my-eu-bubble?tab=calendar&committee={code}",
            params={"committee_code": code},
            requires_auth=True,
            pre_user_label="Sign up for EU Calendar",
        ))

    # For pre-users, swap labels
    if is_pre_user:
        for action in actions:
            if action.pre_user_label:
                action.label = action.pre_user_label
                action.route = "/subscription"
                action.params = {}

    logger.info(f"[ACTION_ROUTER] Computed {len(actions)} actions: "
                f"{[a.action_type for a in actions]}")

    return actions[:MAX_ACTIONS]
