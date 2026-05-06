"""
Comparator API — spreadsheet-style legislative-file comparison.

Top-level Brubru feature, peer of Amendator + Tenderator. Lets users build
grids where rows are legislative files (CELEX or OEIL refs) and columns are
aspects (rapporteur, status, amendments deadline, etc.). Each cell carries a
verifiable citation, so values can never be fabricated — when source data is
missing, the cell renders empty with a recorded reason.

Endpoints:
    GET    /api/comparator/catalog                 -- list canonical column defs + tier limits
    POST   /api/comparator/grids                   -- create grid
    GET    /api/comparator/grids                   -- list user's grids
    GET    /api/comparator/grids/{grid_id}         -- fetch grid + cells
    PATCH  /api/comparator/grids/{grid_id}         -- rename, add/remove rows or columns
    DELETE /api/comparator/grids/{grid_id}         -- delete grid + cells (cascade)
    POST   /api/comparator/grids/{grid_id}/compute -- (re)compute all cells

Tier gating (enforced inline, not in SQL):
    white  (free trial):  1 grid, 3 rows × 3 cols
    yellow (advocate):    3 grids, 5 rows × 6 cols
    blue   (professional, admin): unlimited grids, 10 rows × 6 cols
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from api.auth import get_current_user
from models.user import User
from schemas.comparator_schemas import (
    COLUMN_DEFS,
    COLUMN_KEYS,
    CatalogResponse,
    CellOut,
    ComputeResponse,
    GridColumn,
    GridCreate,
    GridDetail,
    GridList,
    GridPatch,
    GridSummary,
    ResolveRequest,
    ResolveResponse,
    SearchHit,
    SearchResponse,
)
from services.comparator.cell_extractors import EXTRACTORS, extract_cell
from services.comparator.file_search import (
    my_files_for_user,
    resolve_labels,
    search_files,
)


router = APIRouter(prefix="/api/comparator", tags=["Comparator"])


# ---------- Tier limits ----------

TIER_LIMITS: Dict[str, Dict[str, int]] = {
    "white":        {"max_grids": 1,    "max_rows": 3,  "max_cols": 3},
    "yellow":       {"max_grids": 3,    "max_rows": 5,  "max_cols": 6},
    "starter":      {"max_grids": 3,    "max_rows": 5,  "max_cols": 6},
    "advocate":     {"max_grids": 3,    "max_rows": 5,  "max_cols": 6},
    "blue":         {"max_grids": 9999, "max_rows": 10, "max_cols": 6},
    "professional": {"max_grids": 9999, "max_rows": 10, "max_cols": 6},
    "admin":        {"max_grids": 9999, "max_rows": 10, "max_cols": 6},
}
DEFAULT_LIMITS = TIER_LIMITS["white"]


def _tier_limits(user: User) -> Dict[str, int]:
    tier = (getattr(user, "subscription_tier", None) or "white").lower()
    return TIER_LIMITS.get(tier, DEFAULT_LIMITS)


def _enforce_grid_limits(
    db: Session,
    user: User,
    *,
    rows: int,
    cols: int,
    creating_new: bool,
) -> None:
    """Raise HTTPException(403) if a grid violates tier limits."""
    limits = _tier_limits(user)
    if rows > limits["max_rows"]:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Tier '{(user.subscription_tier or 'white')}' allows at most "
                f"{limits['max_rows']} rows per grid (got {rows}). Upgrade to add more files."
            ),
        )
    if cols > limits["max_cols"]:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Tier '{(user.subscription_tier or 'white')}' allows at most "
                f"{limits['max_cols']} columns per grid (got {cols})."
            ),
        )
    if creating_new:
        existing = db.execute(
            text("SELECT COUNT(*) FROM comparator_grids WHERE user_id = :uid"),
            {"uid": str(user.id)},
        ).scalar() or 0
        if existing >= limits["max_grids"]:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Tier '{(user.subscription_tier or 'white')}' allows at most "
                    f"{limits['max_grids']} grids (you have {existing}). Upgrade or delete an existing grid."
                ),
            )


# ---------- Helpers ----------

def _validate_columns(cols: List[GridColumn]) -> List[Dict[str, str]]:
    """Normalise + validate column list. Returns list of dicts ready for JSONB storage."""
    normalised: List[Dict[str, str]] = []
    for c in cols:
        if c.key not in COLUMN_KEYS:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown column key '{c.key}'. Allowed: {sorted(COLUMN_KEYS)}",
            )
        canonical = next(cd for cd in COLUMN_DEFS if cd["key"] == c.key)
        normalised.append({"key": c.key, "label": c.label or canonical["label"]})
    return normalised


def _grid_to_summary(row: Any, cell_count: int = 0) -> GridSummary:
    return GridSummary(
        id=row[0],
        name=row[1],
        file_refs=list(row[2] or []),
        columns=[GridColumn(**c) for c in (row[3] or [])],
        created_at=row[4],
        updated_at=row[5],
        cell_count=cell_count,
    )


def _fetch_grid_or_404(db: Session, grid_id: UUID, user: User) -> Any:
    row = db.execute(
        text(
            """
            SELECT id, name, file_refs, columns, created_at, updated_at
            FROM comparator_grids
            WHERE id = :gid AND user_id = :uid
            LIMIT 1
            """
        ),
        {"gid": str(grid_id), "uid": str(user.id)},
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Grid not found or not owned by user")
    return row


# ---------- Endpoints ----------

@router.get("/catalog", response_model=CatalogResponse)
def get_catalog():
    """Public column catalogue. The frontend column picker hits this once on mount."""
    return CatalogResponse(columns=COLUMN_DEFS)


@router.get("/search", response_model=SearchResponse)
def search(
    q: str,
    limit: int = 20,
    db: Session = Depends(get_db),
):
    """Search legislative files by alias (GDPR, AI Act), CELEX, OEIL ref, or title.

    Public — does not require auth. Used by the picker combobox.
    """
    if not q or not q.strip():
        return SearchResponse(query=q, hits=[])
    if limit < 1 or limit > 50:
        limit = 20
    raw = search_files(q.strip(), db, limit=limit)
    return SearchResponse(query=q, hits=[SearchHit(**h) for h in raw])


@router.get("/my-files", response_model=List[SearchHit])
def my_files(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """User's tracked files (My EU Bubble > My Files), ready to drop into a grid."""
    raw = my_files_for_user(str(user.id), db)
    return [SearchHit(**h) for h in raw]


@router.post("/resolve", response_model=ResolveResponse)
def resolve(
    body: ResolveRequest,
    db: Session = Depends(get_db),
):
    """Given file_refs, return human-readable display labels.

    Public — labels are derived from public data (eu_laws, legislative_carriages,
    alias resolver). Used by the editor when re-opening a saved grid.
    """
    md = resolve_labels(body.refs, db)
    return ResolveResponse(metadata={k: SearchHit(**v) for k, v in md.items()})


@router.get("/grids", response_model=GridList)
def list_grids(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all grids owned by the current user."""
    rows = db.execute(
        text(
            """
            SELECT g.id, g.name, g.file_refs, g.columns, g.created_at, g.updated_at,
                   COALESCE((SELECT COUNT(*) FROM comparator_cells c WHERE c.grid_id = g.id), 0) AS cell_count
            FROM comparator_grids g
            WHERE g.user_id = :uid
            ORDER BY g.updated_at DESC
            """
        ),
        {"uid": str(user.id)},
    ).fetchall()
    grids = [_grid_to_summary(r, cell_count=r[6]) for r in rows]
    return GridList(grids=grids, total=len(grids), tier_limits=_tier_limits(user))


@router.post("/grids", response_model=GridDetail, status_code=201)
def create_grid(
    body: GridCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new grid. Cells are created as 'pending' — call /compute to fill."""
    cols_norm = _validate_columns(body.columns)
    _enforce_grid_limits(
        db, user,
        rows=len(body.file_refs),
        cols=len(cols_norm),
        creating_new=True,
    )

    # SQLAlchemy can't bind JSONB lists transparently with `text()`; cast on the SQL side
    import json as _json
    row = db.execute(
        text(
            """
            INSERT INTO comparator_grids (user_id, name, file_refs, columns)
            VALUES (:uid, :name, CAST(:file_refs AS JSONB), CAST(:cols AS JSONB))
            RETURNING id, name, file_refs, columns, created_at, updated_at
            """
        ),
        {
            "uid": str(user.id),
            "name": body.name,
            "file_refs": _json.dumps(body.file_refs),
            "cols": _json.dumps(cols_norm),
        },
    ).fetchone()
    db.commit()
    summary = _grid_to_summary(row, cell_count=0)
    return GridDetail(**summary.model_dump(), cells=[])


@router.get("/grids/{grid_id}", response_model=GridDetail)
def get_grid(
    grid_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Fetch a grid + all its cells, with per-file display labels resolved."""
    row = _fetch_grid_or_404(db, grid_id, user)
    cell_rows = db.execute(
        text(
            """
            SELECT file_ref, column_key, value_text, citation,
                   computation_status, computation_error, computed_at
            FROM comparator_cells
            WHERE grid_id = :gid
            ORDER BY file_ref, column_key
            """
        ),
        {"gid": str(grid_id)},
    ).fetchall()
    cells = [
        CellOut(
            file_ref=c[0], column_key=c[1], value_text=c[2], citation=c[3],
            computation_status=c[4], computation_error=c[5], computed_at=c[6],
        )
        for c in cell_rows
    ]
    summary = _grid_to_summary(row, cell_count=len(cells))
    file_metadata = resolve_labels(list(row[2] or []), db)
    return GridDetail(
        **summary.model_dump(),
        cells=cells,
        file_metadata=file_metadata,
    )


@router.patch("/grids/{grid_id}", response_model=GridDetail)
def patch_grid(
    grid_id: UUID,
    body: GridPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Rename, change rows, or change columns. Existing cells outside the new
    (rows × cols) intersection are deleted; cells in the intersection survive."""
    row = _fetch_grid_or_404(db, grid_id, user)
    new_name = body.name if body.name is not None else row[1]
    new_refs = body.file_refs if body.file_refs is not None else list(row[2] or [])
    if body.columns is not None:
        new_cols = _validate_columns(body.columns)
    else:
        new_cols = list(row[3] or [])

    _enforce_grid_limits(
        db, user,
        rows=len(new_refs),
        cols=len(new_cols),
        creating_new=False,
    )

    # Delete cells whose (file_ref, column_key) no longer belong to the grid
    keep_keys = {c["key"] for c in new_cols}
    keep_refs = set(new_refs)
    if keep_keys and keep_refs:
        db.execute(
            text(
                """
                DELETE FROM comparator_cells
                WHERE grid_id = :gid
                  AND (file_ref NOT IN :refs OR column_key NOT IN :keys)
                """
            ).bindparams(
            ),
            {"gid": str(grid_id), "refs": tuple(keep_refs), "keys": tuple(keep_keys)},
        )
    else:
        db.execute(
            text("DELETE FROM comparator_cells WHERE grid_id = :gid"),
            {"gid": str(grid_id)},
        )

    import json as _json
    db.execute(
        text(
            """
            UPDATE comparator_grids
            SET name = :name,
                file_refs = CAST(:refs AS JSONB),
                columns = CAST(:cols AS JSONB)
            WHERE id = :gid AND user_id = :uid
            """
        ),
        {
            "name": new_name,
            "refs": _json.dumps(new_refs),
            "cols": _json.dumps(new_cols),
            "gid": str(grid_id),
            "uid": str(user.id),
        },
    )
    db.commit()
    return get_grid(grid_id=grid_id, user=user, db=db)


@router.delete("/grids/{grid_id}", status_code=204)
def delete_grid(
    grid_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res = db.execute(
        text("DELETE FROM comparator_grids WHERE id = :gid AND user_id = :uid"),
        {"gid": str(grid_id), "uid": str(user.id)},
    )
    db.commit()
    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Grid not found or not owned by user")


@router.post("/grids/{grid_id}/compute", response_model=ComputeResponse)
def compute_grid(
    grid_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run all 6 cell extractors over every (file_ref, column_key) in the grid.

    Synchronous in MVP. Worst-case 60 cells × ~50ms each = 3s for a 10×6 grid;
    most cells finish in <20ms because they reuse a single SELECT against
    legislative_carriages cached by the OEIL ref. If the grid is bigger or the
    extractors get slower, we can move this to a background task later.
    """
    row = _fetch_grid_or_404(db, grid_id, user)
    file_refs: List[str] = list(row[2] or [])
    cols: List[Dict[str, str]] = list(row[3] or [])

    started = time.time()
    computed = 0
    failed = 0
    import json as _json
    for ref in file_refs:
        for col in cols:
            key = col["key"]
            try:
                res = extract_cell(key, ref, db)
                value = res.get("value")
                citation = res.get("citation")
                status = "computed" if value is not None else "computed"  # null cell is still "computed"
                error: Optional[str] = res.get("_reason") if value is None else None
                # Upsert
                db.execute(
                    text(
                        """
                        INSERT INTO comparator_cells
                            (grid_id, file_ref, column_key, value_text, citation,
                             computation_status, computation_error, computed_at)
                        VALUES (:gid, :ref, :key, :value, CAST(:cite AS JSONB),
                                :status, :err, NOW())
                        ON CONFLICT (grid_id, file_ref, column_key) DO UPDATE
                        SET value_text = EXCLUDED.value_text,
                            citation = EXCLUDED.citation,
                            computation_status = EXCLUDED.computation_status,
                            computation_error = EXCLUDED.computation_error,
                            computed_at = EXCLUDED.computed_at
                        """
                    ),
                    {
                        "gid": str(grid_id),
                        "ref": ref,
                        "key": key,
                        "value": value,
                        "cite": _json.dumps(citation) if citation is not None else None,
                        "status": status,
                        "err": error,
                    },
                )
                computed += 1
            except Exception as e:
                failed += 1
                db.execute(
                    text(
                        """
                        INSERT INTO comparator_cells
                            (grid_id, file_ref, column_key, value_text, citation,
                             computation_status, computation_error, computed_at)
                        VALUES (:gid, :ref, :key, NULL, NULL, 'failed', :err, NOW())
                        ON CONFLICT (grid_id, file_ref, column_key) DO UPDATE
                        SET value_text = NULL,
                            citation = NULL,
                            computation_status = 'failed',
                            computation_error = EXCLUDED.computation_error,
                            computed_at = NOW()
                        """
                    ),
                    {"gid": str(grid_id), "ref": ref, "key": key, "err": f"{type(e).__name__}: {e}"},
                )
    db.commit()
    return ComputeResponse(
        grid_id=grid_id,
        cells_computed=computed,
        cells_failed=failed,
        duration_seconds=round(time.time() - started, 2),
    )
