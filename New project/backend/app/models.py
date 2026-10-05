import enum
from sqlalchemy import JSON

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Enum, Float, Boolean, Index, func
)
from sqlalchemy.orm import relationship, synonym
from sqlalchemy.sql import func

from .database import Base


class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    manager = "manager"
    tl = "tl"
    user = "user"
    employee = "user"


ROLE_HIERARCHY = {
    UserRole.superadmin: None,
    UserRole.admin: UserRole.superadmin,
    UserRole.manager: UserRole.admin,
    UserRole.tl: UserRole.manager,
    UserRole.user: UserRole.tl,
}


ROLES_CREATABLE_BY = {
    UserRole.superadmin: {UserRole.admin, UserRole.manager, UserRole.tl, UserRole.user},
    UserRole.admin: {UserRole.manager, UserRole.tl, UserRole.user},
    UserRole.manager: {UserRole.tl, UserRole.user},
    UserRole.tl: {UserRole.user},
    UserRole.user: set(),
}


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    __table_args__ = (
        Index(
            "uq_departments_owner_name_lower",
            "created_by_id",
            func.lower(name),
            unique=True,
            postgresql_where=created_by_id.is_not(None),
            sqlite_where=created_by_id.is_not(None),
        ),
        Index(
            "uq_departments_unowned_name_lower",
            func.lower(name),
            unique=True,
            postgresql_where=created_by_id.is_(None),
            sqlite_where=created_by_id.is_(None),
        ),
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

    users = relationship("User", back_populates="department", foreign_keys="User.department_id")
    created_by = relationship("User", foreign_keys=[created_by_id])
    consents = relationship("ConsentRecord", back_populates="department")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    parent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    organization_id = synonym("department_id")
    parent = relationship("User", remote_side=[id], foreign_keys=[parent_id], backref="direct_reports")
    department = relationship("Department", back_populates="users", foreign_keys=[department_id])

    time_entries = relationship("TimeEntry", back_populates="user")
    manager = relationship("User", remote_side=[id], foreign_keys=[manager_id], back_populates="reports")
    reports = relationship("User", foreign_keys=[manager_id], back_populates="manager")
    audit_events = relationship("AuditEvent", back_populates="actor")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    time_entries = relationship("TimeEntry", back_populates="project")


class TimeEntryStatus(str, enum.Enum):
    active = "active"
    stopped = "stopped"


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)

    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, default=0)
    status = Column(Enum(TimeEntryStatus), default=TimeEntryStatus.active)

    start_ip_address = Column(String, nullable=True)
    
     # NEW — real idle tracking instead of guessing from screenshots
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    is_idle = Column(Boolean, default=False)

    user = relationship("User", back_populates="time_entries")
    project = relationship("Project", back_populates="time_entries")
    screenshots = relationship("Screenshot", back_populates="time_entry")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id = Column(Integer, primary_key=True, index=True)
    time_entry_id = Column(Integer, ForeignKey("time_entries.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    file_path = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)
    activity_level = Column(Float, nullable=True)  # optional: mouse/keyboard activity %
    captured_at = Column(DateTime(timezone=True), server_default=func.now())

    time_entry = relationship("TimeEntry", back_populates="screenshots")
    user = relationship("User")


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True)
    screenshot_interval_seconds = Column(Integer, nullable=False, default=300)
    idle_timeout_seconds = Column(Integer, nullable=False, default=300)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    retention_days = Column(Integer, nullable=False, default=90)
    screenshot_masking_enabled = Column(Boolean, nullable=False, default=False)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, nullable=False, index=True)
    target_type = Column(String, nullable=False)
    target_id = Column(String, nullable=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    actor = relationship("User", back_populates="audit_events")


class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    organization_id = synonym("department_id")
    policy_version = Column(String, nullable=False)
    accepted_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String, nullable=True)

    user = relationship("User")
    department = relationship("Department", back_populates="consents")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")


class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class AlertStatus(str, enum.Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    alert_type = Column(String, nullable=False, index=True)
    severity = Column(Enum(AlertSeverity), default=AlertSeverity.warning, nullable=False)
    status = Column(Enum(AlertStatus), default=AlertStatus.open, nullable=False, index=True)
    message = Column(String, nullable=False)
    evidence = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
