from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth, models
from ..database import get_db

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=List[dict])
def list_audit_events(db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_manager_or_above)):
    visible_ids = [user.id for user in auth.visible_user_filter(db.query(models.User), current_user).all()]
    events = db.query(models.AuditEvent).filter(
        (models.AuditEvent.actor_id.is_(None)) | models.AuditEvent.actor_id.in_(visible_ids)
    ).order_by(models.AuditEvent.created_at.desc()).limit(500).all()
    return [{
        "id": event.id, "actor_id": event.actor_id, "action": event.action,
        "target_type": event.target_type, "target_id": event.target_id,
        "details": event.details or {}, "created_at": event.created_at,
    } for event in events]