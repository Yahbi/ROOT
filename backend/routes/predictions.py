"""
Routes for Prediction Ledger — tracks predictions from MiRo, Swarm, and
Directive Engine with calibration scoring per source + confidence bucket.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


# ── Request Models ───────────────────────────────────────────────

class PredictionRequest(BaseModel):
    source: str = Field(..., min_length=1, max_length=100)
    prediction: str = Field(..., min_length=1, max_length=2000)
    confidence: float = Field(..., ge=0.0, le=1.0)
    deadline: Optional[str] = None
    category: str = Field(default="general", max_length=50)


class ResolveRequest(BaseModel):
    actual_outcome: str = Field(..., min_length=1, max_length=2000)
    accurate: bool


# ── List Predictions ─────────────────────────────────────────────

@router.get("")
async def list_predictions(
    request: Request,
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """List predictions with optional filters."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    if status == "pending":
        predictions = ledger.get_pending()
    else:
        predictions = ledger.get_history(source=source, limit=limit)

    return {
        "predictions": [
            {
                "id": p.id,
                "source": p.source,
                "symbol": p.symbol,
                "direction": p.direction,
                "confidence": p.confidence,
                "target_price": p.target_price,
                "deadline": p.deadline,
                "hit": p.hit,
                "resolved_at": p.resolved_at,
                "created_at": p.created_at,
            }
            for p in predictions[:limit]
        ],
    }


# ── Calibration ──────────────────────────────────────────────────

@router.get("/calibration")
async def calibration_scores(
    request: Request,
    source: Optional[str] = None,
):
    """Calibration scores by source."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    buckets = ledger.get_calibration(source=source)
    return {
        "calibration": [
            {
                "source": b.source,
                "confidence_bucket": b.confidence_bucket,
                "total_predictions": b.total_predictions,
                "correct_predictions": b.correct_predictions,
                "calibration_score": b.calibration_score,
                "updated_at": b.updated_at,
            }
            for b in buckets
        ],
    }


# ── Stats ────────────────────────────────────────────────────────

@router.get("/stats")
async def prediction_stats(request: Request):
    """Overall prediction stats."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")
    return ledger.stats()


# ── Single Prediction ────────────────────────────────────────────

@router.get("/{prediction_id}")
async def get_prediction(prediction_id: str, request: Request):
    """Get a single prediction by ID."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    # Search in history for the specific prediction
    all_preds = ledger.get_history(limit=1000)
    prediction = next((p for p in all_preds if p.id == prediction_id), None)
    if not prediction:
        raise HTTPException(404, "Prediction not found")

    return {
        "id": prediction.id,
        "source": prediction.source,
        "symbol": prediction.symbol,
        "direction": prediction.direction,
        "confidence": prediction.confidence,
        "target_price": prediction.target_price,
        "deadline": prediction.deadline,
        "reasoning": prediction.reasoning,
        "actual_direction": prediction.actual_direction,
        "actual_price": prediction.actual_price,
        "resolved_at": prediction.resolved_at,
        "hit": prediction.hit,
        "created_at": prediction.created_at,
    }


# ── Record Prediction ────────────────────────────────────────────

@router.post("")
async def record_prediction(req: PredictionRequest, request: Request):
    """Record a new prediction."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    try:
        deadline_hours = 24
        if req.deadline:
            try:
                deadline_hours = int(req.deadline)
            except ValueError:
                deadline_hours = 24

        prediction_id = ledger.record_prediction(
            source=req.source,
            symbol=req.source.upper(),
            direction="hold",
            confidence=req.confidence,
            reasoning=req.prediction,
            deadline_hours=deadline_hours,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {"id": prediction_id, "source": req.source, "confidence": req.confidence}


# ── Resolve Prediction ────────────────────────────────────────────

@router.post("/{prediction_id}/resolve")
async def resolve_prediction(
    prediction_id: str, req: ResolveRequest, request: Request,
):
    """Resolve a prediction with actual outcome."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    try:
        actual_direction = "long" if req.accurate else "short"
        hit = ledger.resolve_prediction(
            prediction_id=prediction_id,
            actual_direction=actual_direction,
            actual_price=0.0,
        )
    except ValueError as exc:
        raise HTTPException(404, str(exc))

    return {
        "prediction_id": prediction_id,
        "accurate": req.accurate,
        "hit": hit,
        "actual_outcome": req.actual_outcome,
    }


# ── Manual Prediction (full fields) ─────────────────────────────

class ManualPredictionRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    direction: str = Field(pattern=r"^(long|short|hold)$")
    confidence: float = Field(ge=0.0, le=1.0)
    target_price: Optional[float] = Field(default=None, ge=0.0)
    reasoning: str = Field(min_length=1, max_length=2000)
    deadline_hours: int = Field(default=24, ge=1, le=720)
    source: str = Field(default="manual", pattern=r"^(miro|swarm|directive|manual)$")


@router.post("/manual")
async def create_manual_prediction(req: ManualPredictionRequest, request: Request):
    """Create a prediction with full manual control over all fields."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    # Extend valid sources to include 'manual'
    try:
        prediction_id = ledger.record_prediction(
            source=req.source,
            symbol=req.symbol.upper(),
            direction=req.direction,
            confidence=req.confidence,
            reasoning=req.reasoning,
            deadline_hours=req.deadline_hours,
            target_price=req.target_price,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    return {
        "id": prediction_id,
        "symbol": req.symbol.upper(),
        "direction": req.direction,
        "confidence": req.confidence,
        "source": req.source,
    }


# ── Confidence Adjustment ────────────────────────────────────────

class ConfidenceUpdateRequest(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)


@router.patch("/{prediction_id}/confidence")
async def update_confidence(
    prediction_id: str, req: ConfidenceUpdateRequest, request: Request,
):
    """Adjust confidence on an unresolved prediction."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    row = ledger.conn.execute(
        "SELECT * FROM predictions WHERE id = ?", (prediction_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Prediction not found")
    if row["resolved_at"] is not None:
        raise HTTPException(400, "Cannot adjust confidence on resolved prediction")

    ledger.conn.execute(
        "UPDATE predictions SET confidence = ? WHERE id = ?",
        (req.confidence, prediction_id),
    )
    ledger.conn.commit()

    return {"prediction_id": prediction_id, "confidence": req.confidence}


# ── Tournament (source vs source comparison) ─────────────────────

@router.get("/tournament")
async def prediction_tournament(request: Request):
    """Compare prediction sources head-to-head."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    sources = ["miro", "swarm", "directive", "manual"]
    tournament = {}
    for src in sources:
        accuracy_30d = ledger.get_accuracy(src, 30)
        accuracy_7d = ledger.get_accuracy(src, 7)
        cal = ledger.get_calibration(source=src)

        # Count total predictions for this source
        row = ledger.conn.execute(
            "SELECT COUNT(*) as c FROM predictions WHERE source = ?", (src,),
        ).fetchone()
        total = row["c"] if row else 0

        tournament[src] = {
            "total_predictions": total,
            "accuracy_7d": accuracy_7d,
            "accuracy_30d": accuracy_30d,
            "calibration_buckets": [
                {
                    "bucket": c.confidence_bucket,
                    "total": c.total_predictions,
                    "correct": c.correct_predictions,
                    "score": c.calibration_score,
                }
                for c in cal
            ],
        }

    return {"tournament": tournament}


# ── Calibration Trend (weekly) ────────────────────────────────────

@router.get("/calibration/trend")
async def calibration_trend(
    request: Request,
    source: Optional[str] = None,
    weeks: int = Query(default=8, ge=1, le=52),
):
    """Weekly calibration trend over time."""
    ledger = getattr(request.app.state, "prediction_ledger", None)
    if not ledger:
        raise HTTPException(503, "Prediction ledger not available")

    from datetime import datetime, timedelta, timezone

    trend = []
    now = datetime.now(timezone.utc)

    for week_offset in range(weeks):
        week_end = now - timedelta(weeks=week_offset)
        week_start = week_end - timedelta(weeks=1)

        query = """SELECT COUNT(*) as total,
                          SUM(CASE WHEN hit = 1 THEN 1 ELSE 0 END) as hits
                   FROM predictions
                   WHERE resolved_at IS NOT NULL AND hit IS NOT NULL
                         AND created_at >= ? AND created_at < ?"""
        params: list = [week_start.isoformat(), week_end.isoformat()]

        if source:
            query += " AND source = ?"
            params.append(source)

        row = ledger.conn.execute(query, params).fetchone()
        total = row["total"] if row else 0
        hits = row["hits"] if row and row["hits"] else 0

        trend.append({
            "week_start": week_start.isoformat()[:10],
            "week_end": week_end.isoformat()[:10],
            "total": total,
            "hits": hits,
            "accuracy": round(hits / total, 4) if total > 0 else 0.0,
        })

    trend.reverse()
    return {"trend": trend, "source": source or "all"}
