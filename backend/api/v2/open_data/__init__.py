"""
"Open Data" domain — /api/v2/open-data/*.

The EU Publications Office open-data portal (data.europa.eu) as a top-level
domain. Sources mirrored verbatim from v1:
    /datasets             search EU datasets (DCAT) with direct download links
    /high-value-datasets  the High-Value Datasets subset (Open Data Directive)
    /catalogues           the ~90 EU + member-state data catalogues (incl. ELDS, PPDS)

Same contract as the rest of v2 (auth + scope + 60 req/min + per-call euro debit,
PaginatedResponse envelope, canonical error shapes, 5-section Markdown
descriptions). LIVE endpoints delegate to the v1 handlers. Scope: read:publications.
"""

from fastapi import APIRouter

from . import open_data as _open_data
from . import jrc_datasets as _jrc_datasets
from . import cohesion_datasets as _cohesion_datasets
from . import eurostat_series as _eurostat_series

router = APIRouter(prefix="/open-data")
router.include_router(_open_data.datasets_router)
router.include_router(_open_data.hvd_router)
router.include_router(_open_data.catalogues_router)
router.include_router(_jrc_datasets.router)
router.include_router(_cohesion_datasets.router)
router.include_router(_eurostat_series.router)
