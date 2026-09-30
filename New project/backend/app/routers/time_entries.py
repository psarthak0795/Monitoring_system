from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/time-entries", tags=["time-entries"])


@router.post("/start", response_model=schemas.TimeEntryOut)
def start_tracking(
    payload: schemas.TimeEntryStart,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    existing = (
        db.query(models.TimeEntry)
        .filter(
            models.TimeEntry.user_id == current_user.id,
            models.TimeEntry.status == models.TimeEntryStatus.active,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="A tracking session is already active")

    entry = models.TimeEntry(
        user_id=current_user.id,
        project_id=payload.project_id,
        start_ip_address=payload.ip_address,
        status=models.TimeEntryStatus.active,
        last_seen_at=datetime.now(timezone.utc),
        is_idle=False,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/{entry_id}/stop", response_model=schemas.TimeEntryOut)
def stop_tracking(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    entry = (
        db.query(models.TimeEntry)
        .filter(models.TimeEntry.id == entry_id, models.TimeEntry.user_id == current_user.id)
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    if entry.status == models.TimeEntryStatus.stopped:
        return entry

    now = datetime.now(timezone.utc)
    entry.end_time = now
    entry.status = models.TimeEntryStatus.stopped
    start_time = entry.start_time
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    entry.duration_seconds = int((now - start_time).total_seconds())

    db.commit()
    db.refresh(entry)
    return entry


@router.get("/active", response_model=Optional[schemas.TimeEntryOut])
def get_active_entry(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.TimeEntry)
        .filter(
            models.TimeEntry.user_id == current_user.id,
            models.TimeEntry.status == models.TimeEntryStatus.active,
        )
        .first()
    )


@router.get("", response_model=List[schemas.TimeEntryOut])
def list_time_entries(
    user_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.TimeEntry)
    if current_user.role in (models.UserRole.superadmin, models.UserRole.admin, models.UserRole.manager):
        if user_id is not None:
            query = query.filter(models.TimeEntry.user_id == user_id)
        visible_ids = [user.id for user in auth.visible_user_filter(db.query(models.User), current_user).all()]
        query = query.filter(models.TimeEntry.user_id.in_(visible_ids))
    else:
        visible_ids = auth.get_visible_member_ids(db, current_user)

    if user_id is not None and current_user.role != models.UserRole.superadmin:
        if not auth.can_manage(db, current_user, user_id):
            raise HTTPException(status_code=404, detail="User not found")

    if visible_ids is not None:
        query = query.filter(models.TimeEntry.user_id.in_(visible_ids))
    if user_id is not None:
        query = query.filter(models.TimeEntry.user_id == user_id)

    if start_date is not None:
        range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
        query = query.filter(
            or_(models.TimeEntry.end_time.is_(None), models.TimeEntry.end_time >= range_start)
        )

    if end_date is not None:
        range_end = datetime.combine(end_date, datetime.max.time(), tzinfo=timezone.utc)
        query = query.filter(models.TimeEntry.start_time <= range_end)

    return query.order_by(models.TimeEntry.start_time.desc()).all()

@router.post("/{entry_id}/heartbeat", response_model=schemas.TimeEntryOut)
def heartbeat(
    entry_id: int,
    payload: schemas.TimeEntryHeartbeat,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    entry = (
        db.query(models.TimeEntry)
        .filter(
            models.TimeEntry.id == entry_id,
            models.TimeEntry.user_id == current_user.id,
            models.TimeEntry.status == models.TimeEntryStatus.active,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Active time entry not found")

    entry.last_seen_at = datetime.now(timezone.utc)
    entry.is_idle = payload.is_idle
    db.commit()
    db.refresh(entry)
    return entry