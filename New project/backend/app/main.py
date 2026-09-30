import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import models
from .database import engine, migrate_schema, migrate_security_schema
from .routers import (
    alerts,
    audit,
    auth,
    compliance,
    departments,
    password_reset,
    screenshots,
    settings,
    time_entries,
    users,
)

migrate_security_schema()
models.Base.metadata.create_all(bind=engine)
migrate_schema()

STORAGE_DIR = os.getenv("SCREENSHOT_STORAGE_DIR", "./storage/screenshots")
os.makedirs(STORAGE_DIR, exist_ok=True)

app = FastAPI(title="Org Activity Tracker API")

# Comma-separated list of origins allowed to call this API, e.g.
#   ALLOWED_ORIGINS=https://tracker.yourcompany.com,http://localhost:5173
# Defaults to "*" (any origin) for zero-config local testing — set this to
# your real dashboard URL(s) before exposing the backend beyond localhost.
_allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = (
    ["*"] if _allowed_origins_raw.strip() == "*"
    else [o.strip() for o in _allowed_origins_raw.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(departments.router)
app.include_router(time_entries.router)
app.include_router(screenshots.router)
app.include_router(settings.router)
app.include_router(alerts.router)
app.include_router(compliance.router)
app.include_router(password_reset.router)
app.include_router(audit.router)


@app.on_event("startup")
def cleanup_expired_screenshots():
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import delete
    from .database import SessionLocal

    db = SessionLocal()
    try:
        settings = db.query(models.AppSettings).first()
        retention_days = settings.retention_days if settings else 90
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        old = db.query(models.Screenshot).filter(models.Screenshot.captured_at < cutoff).all()
        for screenshot in old:
            try:
                os.remove(screenshot.file_path)
            except OSError:
                pass
            db.delete(screenshot)
        if old:
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}
