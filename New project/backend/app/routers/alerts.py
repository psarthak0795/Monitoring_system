from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db
from ..audit import record

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/telemetry", response_model=schemas.AlertOut)
def submit_telemetry(
    payload: schemas.AlertCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Accept a client signal and deduplicate noisy repeated detections."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    recent = (
        db.query(models.Alert)
        .filter(
            models.Alert.user_id == current_user.id,
            models.Alert.alert_type == payload.alert_type,
            models.Alert.created_at >= cutoff,
            models.Alert.status != models.AlertStatus.resolved,
        )
        .first()
    )
    if recent:
        recent.evidence = payload.evidence
        db.commit()
        db.refresh(recent)
        return recent

    alert = models.Alert(
        user_id=current_user.id,
        alert_type=payload.alert_type,
        severity=payload.severity,
        message=payload.message,
        evidence=payload.evidence,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.get("", response_model=List[schemas.AlertOut])
def list_alerts(
    status: Optional[models.AlertStatus] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_manager_or_above),
):
    visible_ids = [user.id for user in auth.visible_user_filter(db.query(models.User), current_user).all()]
    query = db.query(models.Alert).filter(models.Alert.user_id.in_(visible_ids))
    if status is not None:
        query = query.filter(models.Alert.status == status)
    return query.order_by(models.Alert.created_at.desc()).all()


@router.post("/{alert_id}/acknowledge", response_model=schemas.AlertOut)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_manager_or_above),
):
    visible_ids = [user.id for user in auth.visible_user_filter(db.query(models.User), current_user).all()]
    alert = db.query(models.Alert).filter(
        models.Alert.id == alert_id,
        models.Alert.user_id.in_(visible_ids),
    ).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = models.AlertStatus.acknowledged
    alert.acknowledged_at = datetime.now(timezone.utc)
    record(db, current_user, "alert.acknowledged", "alert", alert.id)
    db.commit()
    db.refresh(alert)
    return alert