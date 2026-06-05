"""
"General Publications" domain — /api/v2/general-publications/*.
EU Publications Office general publications (brochures, reports, studies).
LIVE delegate to v1. Scope: read:publications.
"""
from fastapi import APIRouter
from . import general_publications as _gp
router = APIRouter()
router.include_router(_gp.router)
