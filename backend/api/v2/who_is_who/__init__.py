"""
"Who is Who" domain — /api/v2/who-is-who/*.

The EU's official interinstitutional directory (op.europa.eu/web/who-is-who) as a
top-level domain. Sources mirrored verbatim from v1:
    /departments  organisational units (DGs, directorates, units) across the EU
    /officials    named officials (name + position + department)

Same contract as the rest of v2. LIVE endpoints delegate to the v1 handlers.
Scope: read:publications.
"""

from fastapi import APIRouter

from . import who_is_who as _who_is_who

router = APIRouter(prefix="/who-is-who")
router.include_router(_who_is_who.departments_router)
router.include_router(_who_is_who.officials_router)
