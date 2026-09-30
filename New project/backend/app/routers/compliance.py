from typing import List

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..audit import record
from ..database import get_db

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/consent", response_model=schemas.ConsentOut)
def accept_consent(payload: schemas.ConsentCreate, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    consent = models.ConsentRecord(
        user_id=current_user.id,
        department_id=current_user.department_id,
        policy_version=payload.policy_version,
        ip_address=request.client.host if request.client else None,
    )
    db.add(consent)
    record(db, current_user, "consent.accepted", "consent", details={"policy_version": payload.policy_version})
    db.commit()
    db.refresh(consent)
    return consent


@router.get("/consent", response_model=List[schemas.ConsentOut])
def list_consent(db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_manager_or_above)):
    visible_ids = [user.id for user in auth.visible_user_filter(db.query(models.User), current_user).all()]
    return db.query(models.ConsentRecord).filter(models.ConsentRecord.user_id.in_(visible_ids)).order_by(models.ConsentRecord.accepted_at.desc()).all()