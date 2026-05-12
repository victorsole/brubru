"""
/api/v1/predictions — legislative procedure outcome + timeline predictions.

Wraps the existing predictions service (`backend/services/predictions/`) which
combines XGBoost ML models with baseline heuristics over OEIL data.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from ._deps import api_user_with_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predictions", tags=["v1-predictions"])


class TimelinePrediction(BaseModel):
    procedure_ref: str
    current_status: Optional[str] = None
    days_in_status: Optional[int] = None
    predicted_days_remaining: Optional[int] = None
    confidence: Optional[float] = None
    lower_bound_25: Optional[int] = None
    upper_bound_75: Optional[int] = None
    model_version: Optional[str] = None
    prediction_method: Optional[str] = None


class OutcomeProbability(BaseModel):
    outcome: str
    probability: float


class OutcomePrediction(BaseModel):
    procedure_ref: str
    current_status: Optional[str] = None
    outcomes: list[OutcomeProbability] = Field(default_factory=list)
    most_likely_outcome: Optional[str] = None
    confidence: Optional[float] = None
    model_version: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints. A prediction is derived analytical
    # content — public_url is the OEIL procedure-file page (where partners
    # can see the underlying data the prediction reads); body_txt and
    # body_html summarise the outcome probabilities in human form; document_date
    # is null (a prediction has no publication date); creation_date is when
    # the model produced this response.
    public_url: Optional[str] = Field(None, description="OEIL procedure-file URL for the underlying procedure.")
    body_txt: Optional[str] = Field(None, description="Plain-text summary of the predicted outcomes + probabilities.")
    body_html: Optional[str] = Field(None, description="HTML rendering of the prediction breakdown.")
    document_date: Optional[date] = Field(None, description="Null — predictions are not dated documents.")
    creation_date: Optional[datetime] = Field(None, description="Time the prediction was generated.")


@router.get(
    "/{procedure_ref:path}/timeline",
    response_model=TimelinePrediction,
    summary="Predicted days remaining to adoption/closure",
    description=(
        "**What it does:** given an OEIL procedure reference, predicts how many days "
        "remain until the procedure closes (adopted, rejected, or withdrawn). Combines "
        "an XGBoost ML model with a baseline heuristic. Confidence is `[0.0, 1.0]`.\n\n"
        "**How to obtain a `procedure_ref`:** call `/api/v1/procedures` (or `/api/v1/laws`) "
        "and grab the `oeil_procedure_ref` field from any item. Format: `YYYY/NNNN(COD)`, "
        "`(CNS)`, `(APP)`, etc.\n\n"
        "**Try it:** `GET /api/v1/predictions/2025/0232(COD)/timeline` (Workers from "
        "carcinogens directive — close to adoption).\n\n"
        "**Service status (2 May 2026):** XGBoost model loading on Railway is currently "
        "degraded — calls may return 502 with `reason_code=upstream_error`. As a "
        "workaround, `GET /api/v1/procedures/{ref}` returns the same upstream OEIL data "
        "(`current_status`, `oeil_key_events`, `expected_completion`) without the ML layer."
    ),
)
async def get_timeline(
    procedure_ref: str,
    use_ml: bool = Query(True),
    user: User = Depends(api_user_with_rate_limit),
) -> TimelinePrediction:
    try:
        if use_ml:
            from services.predictions import get_ml_timeline_predictor
            predictor = get_ml_timeline_predictor()
            pred = await predictor.predict_with_ml(procedure_ref)
            return TimelinePrediction(
                procedure_ref=pred.procedure_ref,
                current_status=pred.current_status,
                days_in_status=pred.days_in_status,
                predicted_days_remaining=pred.predicted_days_remaining,
                confidence=pred.confidence,
                lower_bound_25=pred.lower_bound_25,
                upper_bound_75=pred.upper_bound_75,
                model_version=pred.model_version,
                prediction_method="ml_xgboost" if not pred.used_fallback else (pred.fallback_reason or "fallback"),
            )
        from services.predictions import get_timeline_predictor
        predictor = get_timeline_predictor()
        pred = await predictor.predict_timeline(procedure_ref)
        if not pred:
            raise HTTPException(status_code=404, detail={"error": "Procedure not found or no data", "reason_code": "not_found", "resource": "procedure", "id": procedure_ref})
        return TimelinePrediction(
            procedure_ref=pred.procedure_ref,
            current_status=pred.current_status,
            days_in_status=pred.days_in_status,
            predicted_days_remaining=pred.predicted_days_remaining or 0,
            confidence=pred.confidence,
            model_version="baseline",
            prediction_method=pred.based_on,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"timeline prediction failed for {procedure_ref}: {exc}")
        raise HTTPException(
            status_code=502,
            detail={"error": "Prediction service error", "reason_code": "upstream_error", "source": "brubru-predictions"},
        )


@router.get(
    "/{procedure_ref:path}/outcome",
    response_model=OutcomePrediction,
    summary="Predicted outcome probabilities (adopted / rejected / withdrawn / pending)",
    description=(
        "**What it does:** predicts the probability of each possible outcome for an "
        "ongoing legislative procedure: adopted, rejected, withdrawn, pending.\n\n"
        "**How to obtain a `procedure_ref`:** see `/timeline` above — same identifier.\n\n"
        "**Try it:** `GET /api/v1/predictions/2025/0232(COD)/outcome`.\n\n"
        "**Service status (2 May 2026):** as with `/timeline`, the ML layer is currently "
        "degraded on Railway. Workaround: `GET /api/v1/procedures/{ref}` returns the live "
        "OEIL state (status, key events) without the predicted probabilities."
    ),
)
async def get_outcome(
    procedure_ref: str,
    user: User = Depends(api_user_with_rate_limit),
) -> OutcomePrediction:
    try:
        from services.predictions import get_outcome_predictor
        predictor = get_outcome_predictor()
        pred = await predictor.predict_outcome(procedure_ref)
        if not pred:
            raise HTTPException(status_code=404, detail={"error": "Procedure not found", "reason_code": "not_found", "resource": "procedure", "id": procedure_ref})
        # The OutcomePredictor return type uses `probabilities` / `predicted_outcome`,
        # not `outcomes` / `most_likely_outcome`. Tolerate either spelling so an
        # ML upgrade that renames fields back doesn't break the v1 surface.
        outcomes_src = getattr(pred, "outcomes", None) or getattr(pred, "probabilities", None) or []
        most_likely = getattr(pred, "most_likely_outcome", None) or getattr(pred, "predicted_outcome", None)
        probs = [OutcomeProbability(outcome=o.outcome, probability=o.probability) for o in outcomes_src]
        # Compose a human body summarising the prediction
        lines_txt = [f"Outcome prediction for {pred.procedure_ref}"]
        if pred.current_status:
            lines_txt.append(f"Current status: {pred.current_status}")
        if most_likely:
            lines_txt.append(f"Most likely outcome: {most_likely}")
        if pred.confidence is not None:
            lines_txt.append(f"Confidence: {pred.confidence:.2%}")
        if probs:
            lines_txt.append("Probabilities:")
            for op in probs:
                lines_txt.append(f"  - {op.outcome}: {op.probability:.2%}")
        body_txt = "\n".join(lines_txt)
        body_html = (
            "<article>"
            f"<h2>Outcome prediction for {pred.procedure_ref}</h2>"
            + (f"<p><strong>Current status:</strong> {pred.current_status}</p>" if pred.current_status else "")
            + (f"<p><strong>Most likely outcome:</strong> {most_likely}</p>" if most_likely else "")
            + (f"<p><strong>Confidence:</strong> {pred.confidence:.2%}</p>" if pred.confidence is not None else "")
            + ("<h3>Probabilities</h3><ul>"
                + "".join(f"<li><strong>{op.outcome}:</strong> {op.probability:.2%}</li>" for op in probs)
                + "</ul>" if probs else "")
            + "</article>"
        )
        # OEIL procedure-file URL as the canonical citizen URL
        oeil_url = f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={pred.procedure_ref}"
        return OutcomePrediction(
            procedure_ref=pred.procedure_ref,
            current_status=pred.current_status,
            outcomes=probs,
            most_likely_outcome=most_likely,
            confidence=pred.confidence,
            model_version=getattr(pred, "model_version", "baseline"),
            # 5 mandatory datapoints
            public_url=oeil_url,
            body_txt=body_txt,
            body_html=body_html,
            creation_date=datetime.utcnow(),
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"outcome prediction failed for {procedure_ref}: {exc}")
        raise HTTPException(
            status_code=502,
            detail={"error": "Prediction service error", "reason_code": "upstream_error", "source": "brubru-predictions"},
        )
