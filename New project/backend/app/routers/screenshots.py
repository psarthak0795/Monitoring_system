import os
import uuid
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from PIL import Image, ImageFilter

from .. import models, schemas, auth
from ..database import get_db

load_dotenv()

STORAGE_DIR = os.getenv("SCREENSHOT_STORAGE_DIR", "./storage/screenshots")

router = APIRouter(prefix="/screenshots", tags=["screenshots"])


@router.post("", response_model=schemas.ScreenshotOut)
def upload_screenshot(
    time_entry_id: int = Form(...),
    ip_address: str = Form(...),
    activity_level: Optional[float] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    entry = (
        db.query(models.TimeEntry)
        .filter(
            models.TimeEntry.id == time_entry_id,
            models.TimeEntry.user_id == current_user.id,
            models.TimeEntry.status == models.TimeEntryStatus.active,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")

    user_dir = os.path.join(STORAGE_DIR, str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)

    ext = os.path.splitext(file.filename or "screenshot.jpg")[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(user_dir, filename)

    with open(dest_path, "wb") as out:
        out.write(file.file.read())

    settings = db.query(models.AppSettings).first()
    if settings and settings.screenshot_masking_enabled:
        with Image.open(dest_path) as image:
            masked = image.convert("RGB").filter(ImageFilter.GaussianBlur(radius=10))
            masked.save(dest_path, format="JPEG", quality=70)

    screenshot = models.Screenshot(
        time_entry_id=time_entry_id,
        user_id=current_user.id,
        file_path=dest_path,
        ip_address=ip_address,
        activity_level=activity_level,
    )
    db.add(screenshot)
    db.commit()
    db.refresh(screenshot)
    return screenshot


@router.get("", response_model=List[schemas.ScreenshotOut])
def list_screenshots(
    user_id: Optional[int] = None,
    time_entry_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.Screenshot)

    if current_user.role in (models.UserRole.super_admin, models.UserRole.admin, models.UserRole.manager):
        if user_id is not None:
            query = query.filter(models.Screenshot.user_id == user_id)
        visible_ids = [user.id for user in auth.visible_user_filter(db.query(models.User), current_user).all()]
        query = query.filter(models.Screenshot.user_id.in_(visible_ids))
    else:
        visible_ids = auth.get_visible_member_ids(db, current_user)

    if current_user.role != models.UserRole.superadmin:
        if user_id is not None and not auth.can_manage(db, current_user, user_id):
            raise HTTPException(status_code=404, detail="User not found")
        if time_entry_id is not None:
            entry = db.query(models.TimeEntry).filter(models.TimeEntry.id == time_entry_id).first()
            if not entry or not auth.can_manage(db, current_user, entry.user_id):
                raise HTTPException(status_code=404, detail="Time entry not found")

    if visible_ids is not None:
        query = query.filter(models.Screenshot.user_id.in_(visible_ids))
    if user_id is not None:
        query = query.filter(models.Screenshot.user_id == user_id)

    if time_entry_id is not None:
        query = query.filter(models.Screenshot.time_entry_id == time_entry_id)

    return query.order_by(models.Screenshot.captured_at.desc()).all()


@router.get("/{screenshot_id}/file")
def get_screenshot_file(
    screenshot_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    screenshot = db.query(models.Screenshot).filter(models.Screenshot.id == screenshot_id).first()
    if not screenshot or not auth.can_manage(db, current_user, screenshot.user_id):
        raise HTTPException(status_code=404, detail="Screenshot not found")

    storage_root = os.path.realpath(STORAGE_DIR)
    file_path = os.path.realpath(screenshot.file_path)
    try:
        is_within_storage = os.path.commonpath([storage_root, file_path]) == storage_root
    except ValueError:
        is_within_storage = False
    if not is_within_storage or not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Screenshot file not found")
    return FileResponse(file_path)
