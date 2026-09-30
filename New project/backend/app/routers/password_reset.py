import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/auth/password", tags=["auth"])


@router.post("/request")
def request_reset(payload: schemas.PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    # Always return the same response to avoid account enumeration.
    if not user:
        return {"message": "If the account exists, a reset token has been created."}
    raw_token = secrets.token_urlsafe(32)
    db.add(models.PasswordResetToken(
        user_id=user.id,
        token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    ))
    db.commit()
    response = {"message": "If the account exists, a reset token has been created."}
    if os.getenv("ALLOW_DEVELOPMENT_RESET_TOKEN", "false").lower() == "true":
        response["development_token"] = raw_token
    return response


@router.post("/confirm")
def confirm_reset(payload: schemas.PasswordResetConfirm, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hash == token_hash,
        models.PasswordResetToken.used_at.is_(None),
        models.PasswordResetToken.expires_at > datetime.now(timezone.utc),
    ).first()
    if not reset:
        return {"message": "Invalid or expired reset token."}
    reset.user.hashed_password = auth.hash_password(payload.password)
    reset.used_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Password updated."}