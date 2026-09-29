from datetime import datetime, timezone
from typing import Optional 
from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator
 
from .models import UserRole, TimeEntryStatus
 
 
def _as_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    """SQLite drops timezone info on read, but every timestamp we write is
    computed in UTC. Stamp UTC back on before serializing so the frontend's
    `new Date(...)` knows to convert it to the browser's local time instead
    of treating the naive value as already-local."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
 
 
# ---- Auth ----
 
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
 
 
# ---- User ----

class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Department name cannot be empty.")
        return value


class DepartmentUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Department name cannot be empty.")
        return value


class DepartmentOut(BaseModel):
    id: int
    name: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DepartmentName(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True
 
class UserCreate(BaseModel):
        name: str
        email: EmailStr
        password: str
        role: UserRole = UserRole.user
        department_id: int = Field(gt=0)
        parent_id:Optional[int] = Field(
        default=None,
        description=(
            "ID of the specific person directly above this user. "
            "Required and must match the role: admin -> a superadmin's id, "
            "manager -> a specific admin's id, tl -> a specific manager's id, "
            "user -> a specific tl's id. Omit only when role is 'superadmin'."
        ),
    )

model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Noise",
                    "email": "noise@example.com",
                    "password": "change-this-password",
                    "role": "tl",
                    "parent_id": 3,
                }
            ]
        }
    }


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    department_id: Optional[int] = Field(default=None, gt=0)
    parent_id: Optional[int] = Field(
        default=None,
        description=(
            "ID of the specific person this user reports to. Required whenever "
            "role is being changed to admin/manager/tl/user, or whenever you "
            "want to reassign an existing user to a different parent."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"name": "Noise", "role": "tl", "is_active": True, "parent_id": 3},
                {"name": "Root Admin", "role": "superadmin", "is_active": True},
            ]
        }
    }


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    parent_id: Optional[int] = None
    department_id: Optional[int] = None
    department: Optional[DepartmentName] = None

    class Config:
        from_attributes = True
 
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
 
 
class ProjectOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
 
    class Config:
        from_attributes = True
 
 
# ---- Time entries ----
 
class TimeEntryStart(BaseModel):
    project_id: Optional[int] = None
    ip_address: str
 
 
class TimeEntryOut(BaseModel):
    id: int
    user_id: int
    project_id: Optional[int]
    start_time: datetime
    end_time: Optional[datetime]
    duration_seconds: int
    status: TimeEntryStatus
    start_ip_address: Optional[str] = None
    last_seen_at: Optional[datetime] = None   # NEW
    is_idle: bool = False                     # NEW
 
    class Config:
        from_attributes = True
 
    @field_serializer("start_time", "end_time")
    def serialize_dt(self, dt: Optional[datetime], _info):
        return _as_utc_iso(dt)
    
    # NEW — sent by the tracking client every N seconds while a session is active
class TimeEntryHeartbeat(BaseModel):
    is_idle: bool = False
 
 
# ---- Screenshots ----
 
class ScreenshotOut(BaseModel):
    id: int
    time_entry_id: int
    user_id: int
    file_path: str
    ip_address: str
    activity_level: Optional[float]
    captured_at: datetime

    class Config:
        from_attributes = True

    @field_serializer("captured_at")
    def serialize_dt(self, dt: datetime, _info):
        return _as_utc_iso(dt)


class SettingsOut(BaseModel):
    screenshot_interval_seconds: int
    idle_timeout_seconds: int

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    screenshot_interval_seconds: int = Field(ge=30, le=3600)
    idle_timeout_seconds: int = Field(ge=30, le=3600)