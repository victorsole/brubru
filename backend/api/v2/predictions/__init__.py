"""
Predictions domain — /api/v2/predictions/*.

AI-predicted timeline and outcome for an ongoing EU legislative procedure.
Ported from the v1 surface via the canonical v1-delegation pattern: the body
delegates to the working v1 handlers (one implementation, no drift); only the
folder path + example URLs are rehomed to /api/v2/predictions/*. Response models
already carry the 5 mandatory datapoints (public_url = OEIL procedure-file URL).
Tag v2-predictions → grouped in the "Predictions" Postman folder.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1 import predictions as _v1
from api.v1.predictions import TimelinePrediction, OutcomePrediction

router = APIRouter(prefix="/predictions")


@router.get(
    "/{procedure_ref:path}/timeline",
    response_model=TimelinePrediction,
    tags=["v2-predictions"],
    summary="Predicted days until a legislative procedure adopts, rejects, or withdraws",
    description="""**What it does**
Predicts how many days remain until a legislative procedure closes (adopted / rejected / withdrawn), combining an XGBoost model trained on historical procedure timelines with a baseline heuristic. Returns the predicted days, a confidence in `[0.0, 1.0]`, and a 25th-75th percentile range for the uncertainty.

**When to use it**
For advocacy timing — knowing whether a file is ~30 days from adoption vs ~9 months tells you whether to push amendments now or wait. Read confidence + range together: high confidence + narrow range = trustworthy; low confidence or wide range = rough estimate.

**Input**
- `procedure_ref` (path) — procedure reference, e.g. `2025/0232(COD)` (`YYYY/NNNN(COD|CNS|APP|...)`). Get one from `/api/v2/legislative/procedures` or `/api/v2/legislative/laws`.
- `use_ml` — boolean (default true); set false for baseline-only.

**Try it**
```
GET /api/v2/predictions/2025/0232(COD)/timeline
GET /api/v2/predictions/2024/0079(COD)/timeline?use_ml=false
```

**You get back**
A `TimelinePrediction` with `current_status`, `days_in_status`, `predicted_days_remaining`, `confidence`, `lower_bound_25`, `upper_bound_75`, `model_version`, `prediction_method`, plus the 5 datapoints (`public_url` = the OEIL procedure-file URL).

**Data freshness**
Computed on-demand from the live OEIL state at request time; the model is retrained quarterly (version in `model_version`).""",
)
async def predicted_timeline(
    procedure_ref: str,
    use_ml: bool = Query(True),
    user: User = Depends(api_user_with_rate_limit),
) -> TimelinePrediction:
    return await _v1.get_timeline(procedure_ref=procedure_ref, use_ml=use_ml, user=user)


@router.get(
    "/{procedure_ref:path}/outcome",
    response_model=OutcomePrediction,
    tags=["v2-predictions"],
    summary="Predicted outcome probabilities — adopted, rejected, withdrawn, pending",
    description="""**What it does**
Predicts the probability of each possible outcome for an ongoing legislative procedure (adopted / rejected / withdrawn / pending) as a distribution that sums to 1.0, plus the highest-probability outcome as the headline.

**When to use it**
For risk assessment — a 70% rejected probability tells you to invest amendment energy elsewhere; a 90% adopted probability says focus on the final form. Combine with `/timeline` for a what + when picture.

**Input**
- `procedure_ref` (path) — procedure reference (same identifier as `/timeline`).

**Try it**
```
GET /api/v2/predictions/2025/0232(COD)/outcome
```

**You get back**
An `OutcomePrediction` with `outcome_probabilities` (outcome → probability), `predicted_outcome`, `confidence`, plus the 5 datapoints.

**Data freshness**
Computed on-demand from the live OEIL state at request time.""",
)
async def predicted_outcome(
    procedure_ref: str,
    user: User = Depends(api_user_with_rate_limit),
) -> OutcomePrediction:
    return await _v1.get_outcome(procedure_ref=procedure_ref, user=user)
