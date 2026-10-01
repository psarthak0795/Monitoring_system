import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models
from .database import get_db

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user


def require_admin(user: models.User = Depends(get_current_user)) -> models.User:
    # Broadened on purpose: Super Admin has every Admin permission too.
    if user.role not in (models.UserRole.superadmin, models.UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_can_manage_users(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role == models.UserRole.user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have permission to manage users")
    return user

# ---------------------------------------------------------------------
# Role hierarchy
# ---------------------------------------------------------------------

# Which roles each role is allowed to create. A role can only ever create
# roles strictly below it in the chain — nobody can create a peer or a
# superior, and Users can't create anyone.
CREATABLE_ROLES = models.ROLES_CREATABLE_BY


def require_superadmin(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role != models.UserRole.superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Super Admin access required")
    return user


def require_role(*allowed_roles: models.UserRole):
    """Generic dependency factory: Depends(require_role(UserRole.manager, UserRole.tl))"""
    def dependency(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user
    return dependency


def require_manager_or_above(user: models.User = Depends(get_current_user)) -> models.User:
    if user.role not in (models.UserRole.superadmin, models.UserRole.admin, models.UserRole.manager):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")
    return user


def get_descendant_ids(db: Session, root_id: int) -> set:
    """All user IDs anywhere below root_id in the parent chain
    (children, grandchildren, etc. — the whole subtree), NOT including
    root_id itself."""
    descendants = set()
    frontier = {root_id}
    while frontier:
        rows = (
            db.query(models.User.id)
            .filter(or_(models.User.parent_id.in_(frontier), models.User.manager_id.in_(frontier)))
            .all()
        )
        next_frontier = {r[0] for r in rows} - descendants
        if not next_frontier:
            break
        descendants |= next_frontier
        frontier = next_frontier
    return descendants


def get_visible_member_ids(db: Session, current_user: models.User) -> Optional[set]:
    """Return the member IDs visible to a user; None means unrestricted access."""
    if current_user.role == models.UserRole.superadmin:
        return None

    if current_user.role == models.UserRole.admin:
        if current_user.department_id is None:
            return {current_user.id}
        department_members = (
            db.query(models.User.id)
            .filter(models.User.department_id == current_user.department_id)
            .all()
        )
        return {member_id for (member_id,) in department_members}

    visible_roles = {
        models.UserRole.admin: {models.UserRole.manager, models.UserRole.tl, models.UserRole.user},
        models.UserRole.manager: {models.UserRole.tl, models.UserRole.user},
        models.UserRole.tl: {models.UserRole.user},
    }.get(current_user.role, set())
    descendant_ids = get_descendant_ids(db, current_user.id)
    visible_descendants = (
        db.query(models.User.id)
        .filter(
            models.User.id.in_(descendant_ids),
            models.User.role.in_(visible_roles),
        )
        .all()
    ) if descendant_ids and visible_roles else []
    return {current_user.id, *(member_id for (member_id,) in visible_descendants)}


def get_dashboard_visible_member_ids(db: Session, current_user: models.User) -> set:
    """Members visible on dashboard views, including assigned parent summaries."""
    visible_ids = set(get_visible_member_ids(db, current_user) or set())
    if current_user.role == models.UserRole.tl:
        manager_ids = {user_id for user_id in (current_user.parent_id, current_user.manager_id) if user_id is not None}
        if manager_ids:
            managers = (
                db.query(models.User)
                .filter(
                    models.User.id.in_(manager_ids),
                    models.User.role == models.UserRole.manager,
                )
                .all()
            )
            visible_ids.update(manager.id for manager in managers)
    if current_user.role == models.UserRole.manager and current_user.parent_id is not None:
        parent_admin = (
            db.query(models.User)
            .filter(
                models.User.id == current_user.parent_id,
                models.User.role == models.UserRole.admin,
            )
            .first()
        )
        if parent_admin:
            visible_ids.add(parent_admin.id)
    return visible_ids


def visible_user_filter(query, current_user: models.User):
    """Restrict a user query to the members visible to the current user."""
    visible_ids = get_visible_member_ids(query.session, current_user)
    if visible_ids is None:
        return query
    return query.filter(models.User.id.in_(visible_ids))


def get_visible_department_ids(db: Session, current_user: models.User) -> Optional[set]:
    """Departments referenced by members visible to this user."""
    visible_member_ids = get_visible_member_ids(db, current_user)
    if visible_member_ids is None:
        return None
    if not visible_member_ids:
        return set()
    rows = (
        db.query(models.User.department_id)
        .filter(
            models.User.id.in_(visible_member_ids),
            models.User.department_id.is_not(None),
        )
        .distinct()
        .all()
    )
    return {department_id for (department_id,) in rows}


def can_manage(db: Session, current_user: models.User, target_user_id: int) -> bool:
    """Whether current_user is allowed to view/edit target_user_id: Super
    Admin can manage anyone; anyone else can manage themselves and anyone
    in their own subtree (people they created, directly or indirectly)."""
    if current_user.role == models.UserRole.superadmin:
        return True
    return target_user_id in get_visible_member_ids(db, current_user)
