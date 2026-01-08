"""
Chat Example Prompts API

Public: fetch examples for the chat interface and track usage.
Admin: CRUD and reorder example prompts.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.core.database import get_db
from backend.models.chat_example_prompt import ChatExamplePrompt
from backend.api.admin_auth import get_current_admin_user
from backend.models.user import User


public_router = APIRouter(prefix="/api/chat/examples", tags=["Chat Examples"])
admin_router = APIRouter(prefix="/api/admin/chat-examples", tags=["Chat Examples (Admin)"])


# ======================
# Pydantic Schemas
# ======================

class ExamplePrompt(BaseModel):
    id: UUID
    text: str
    locale: Optional[str]
    scope: str
    subscription_tiers: Optional[List[str]]
    is_active: bool
    sort_order: int
    usage_count: int


class ExamplePromptCreate(BaseModel):
    text: str = Field(..., min_length=3, max_length=500)
    locale: Optional[str] = Field(None, description="e.g., 'en' or 'en-GB'")
    scope: str = Field("main_chat")
    subscription_tiers: Optional[List[str]] = None
    is_active: bool = True
    sort_order: Optional[int] = 0


class ExamplePromptUpdate(BaseModel):
    text: Optional[str] = Field(None, min_length=3, max_length=500)
    locale: Optional[str] = None
    scope: Optional[str] = None
    subscription_tiers: Optional[List[str]] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class ReorderRequest(BaseModel):
    # list of prompt IDs in the desired order
    ordered_ids: List[UUID]


# ======================
# Public Endpoints
# ======================

@public_router.get("", response_model=List[ExamplePrompt])
def get_examples(
    db: Session = Depends(get_db),
    locale: Optional[str] = Query(None),
    scope: str = Query("main_chat"),
    tier: Optional[str] = Query(None),
    limit: int = Query(4, ge=1, le=12),
):
    """
    Fetch active example prompts for the chat interface.
    Filters by scope, optional locale, and subscription tier.
    """
    q = db.query(ChatExamplePrompt).filter(
        and_(
            ChatExamplePrompt.is_active == True,
            ChatExamplePrompt.scope == scope,
        )
    )

    # Filter by locale if provided
    if locale:
        # Match exact locale or language prefix (e.g., 'en' matches 'en-GB') or no locale (agnostic)
        lang = locale.split("-")[0]
        q = q.filter(
            or_(
                ChatExamplePrompt.locale == locale,
                ChatExamplePrompt.locale == lang,
                ChatExamplePrompt.locale.is_(None),
            )
        )

    # Filter by subscription tier if provided
    if tier:
        # include prompts where subscription_tiers is null (all) or contains the tier
        q = q.filter(
            or_(
                ChatExamplePrompt.subscription_tiers.is_(None),
                ChatExamplePrompt.subscription_tiers.contains([tier]),
            )
        )

    items = (
        q.order_by(ChatExamplePrompt.sort_order.asc(), ChatExamplePrompt.created_at.asc())
        .limit(limit)
        .all()
    )

    return [ExamplePrompt(**i.to_dict()) for i in items]


@public_router.post("/{prompt_id}/track", status_code=status.HTTP_204_NO_CONTENT)
def track_prompt_click(prompt_id: UUID, db: Session = Depends(get_db)):
    """Increment usage_count for analytics. No auth required."""
    item = db.query(ChatExamplePrompt).filter(ChatExamplePrompt.id == prompt_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")
    item.usage_count = (item.usage_count or 0) + 1
    db.add(item)
    db.commit()
    return None


# ======================
# Admin Endpoints
# ======================

@admin_router.get("", response_model=List[ExamplePrompt])
def admin_list_examples(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
    locale: Optional[str] = Query(None),
    scope: Optional[str] = Query(None),
    active_only: bool = Query(False),
):
    q = db.query(ChatExamplePrompt)
    if locale:
        q = q.filter(ChatExamplePrompt.locale == locale)
    if scope:
        q = q.filter(ChatExamplePrompt.scope == scope)
    if active_only:
        q = q.filter(ChatExamplePrompt.is_active == True)

    items = q.order_by(ChatExamplePrompt.sort_order.asc(), ChatExamplePrompt.created_at.asc()).all()
    return [ExamplePrompt(**i.to_dict()) for i in items]


@admin_router.post("", response_model=ExamplePrompt, status_code=status.HTTP_201_CREATED)
def admin_create_example(
    payload: ExamplePromptCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    item = ChatExamplePrompt(
        text=payload.text,
        locale=payload.locale,
        scope=payload.scope or "main_chat",
        subscription_tiers=payload.subscription_tiers,
        is_active=payload.is_active,
        sort_order=payload.sort_order or 0,
        created_by=admin.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return ExamplePrompt(**item.to_dict())


@admin_router.patch("/{prompt_id}", response_model=ExamplePrompt)
def admin_update_example(
    prompt_id: UUID,
    updates: ExamplePromptUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    item = db.query(ChatExamplePrompt).filter(ChatExamplePrompt.id == prompt_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")

    data = updates.dict(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)

    db.add(item)
    db.commit()
    db.refresh(item)
    return ExamplePrompt(**item.to_dict())


@admin_router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_example(
    prompt_id: UUID,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    item = db.query(ChatExamplePrompt).filter(ChatExamplePrompt.id == prompt_id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")

    db.delete(item)
    db.commit()
    return None


@admin_router.patch("/reorder", response_model=List[ExamplePrompt])
def admin_reorder_examples(
    body: ReorderRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    # Apply new sort_order according to list position
    id_to_order = {pid: idx for idx, pid in enumerate(body.ordered_ids)}
    items = db.query(ChatExamplePrompt).filter(ChatExamplePrompt.id.in_(body.ordered_ids)).all()

    for item in items:
        new_order = id_to_order.get(item.id)
        if new_order is not None:
            item.sort_order = int(new_order)
            db.add(item)

    db.commit()

    updated = (
        db.query(ChatExamplePrompt)
        .filter(ChatExamplePrompt.id.in_(body.ordered_ids))
        .order_by(ChatExamplePrompt.sort_order.asc())
        .all()
    )
    return [ExamplePrompt(**i.to_dict()) for i in updated]

