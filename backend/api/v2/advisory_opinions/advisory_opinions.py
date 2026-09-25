"""/api/v2/opinions — thin delegation to v1, as the other folders do.

The handlers live in api/v1/advisory_opinions.py; this publishes them under v2 with the same contract
so a v2 client never has to know which version implemented a route first.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from api.v1 import advisory_opinions as _v1
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1.advisory_opinions import OpinionItem
from core.database import get_db
from models.user import User

router = APIRouter(prefix="/advisory-opinions")

_ALL = next(r for r in _v1.router.routes if r.path == "/advisory-opinions/all")
_EESC = next(r for r in _v1.router.routes if r.path == "/advisory-opinions/eesc")
_EESC_ITEM = next(r for r in _v1.router.routes if r.path == "/advisory-opinions/eesc/{item_id}")
_COR = next(r for r in _v1.router.routes if r.path == "/advisory-opinions/cor")
_COR_ITEM = next(r for r in _v1.router.routes if r.path == "/advisory-opinions/cor/{item_id}")


@router.get("/all", response_model=PaginatedResponse[OpinionItem], tags=["v2-opinions"],
            summary=_ALL.summary, description=_ALL.description)
async def list_all_opinions(
    request: Request,
    body: Optional[Literal["eesc", "cor"]] = Query(None),
    q: Optional[str] = Query(None),
    from_: Optional[date] = Query(None, alias="from"),
    to: Optional[date] = Query(None),
    related_celex: Optional[str] = Query(None),
    has_body: Optional[bool] = Query(None),
    include_body: bool = Query(False),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[OpinionItem]:
    return await _ALL.endpoint(request=request, body=body, q=q, from_=from_, to=to,
                               related_celex=related_celex, has_body=has_body,
                               include_body=include_body, limit=limit, page=page,
                               user=user, db=db)


def _register(code: str, list_route, item_route):
    @router.get(f"/{code}", response_model=PaginatedResponse[OpinionItem], tags=["v2-opinions"],
                summary=list_route.summary, description=list_route.description)
    async def _list(
        request: Request,
        q: Optional[str] = Query(None),
        from_: Optional[date] = Query(None, alias="from"),
        to: Optional[date] = Query(None),
        related_celex: Optional[str] = Query(None),
        has_body: Optional[bool] = Query(None),
        include_body: bool = Query(False),
        limit: int = Query(25, ge=1, le=100),
        page: int = Query(1, ge=1),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> PaginatedResponse[OpinionItem]:
        return await list_route.endpoint(request=request, q=q, from_=from_, to=to,
                                         related_celex=related_celex, has_body=has_body,
                                         include_body=include_body, limit=limit, page=page,
                                         user=user, db=db)

    @router.get(f"/{code}/{{item_id}}", response_model=OpinionItem, tags=["v2-opinions"],
                summary=item_route.summary, description=item_route.description)
    async def _item(
        item_id: int,
        request: Request,
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> OpinionItem:
        return await item_route.endpoint(item_id=item_id, request=request, user=user, db=db)


_register("eesc", _EESC, _EESC_ITEM)
_register("cor", _COR, _COR_ITEM)
