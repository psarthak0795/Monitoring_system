from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..audit import record
from ..database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=schemas.SettingsOut)
def get_settings(
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.get_current_user),
):
    settings = db.query(models.AppSettings).first()
    if settings is None:
        return models.AppSettings(
            screenshot_interval_seconds=300,
            idle_timeout_seconds=300,
            retention_days=90,
            screenshot_masking_enabled=False,
        )
    return settings


@router.put("", response_model=schemas.SettingsOut)
def update_settings(
    payload: schemas.SettingsUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_admin),
):
    settings = db.query(models.AppSettings).first()
    if settings is None:
        settings = models.AppSettings()
        db.add(settings)

    settings.screenshot_interval_seconds = payload.screenshot_interval_seconds
    settings.idle_timeout_seconds = payload.idle_timeout_seconds
    settings.retention_days = payload.retention_days
    settings.screenshot_masking_enabled = payload.screenshot_masking_enabled
    record(db, _, "settings.updated", "app_settings", settings.id, {
        "retention_days": payload.retention_days,
        "screenshot_masking_enabled": payload.screenshot_masking_enabled,
    })
    db.commit()
    db.refresh(settings)
    return settings
