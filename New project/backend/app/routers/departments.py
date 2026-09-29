from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/departments", tags=["departments"])


def _normalize_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="Department name cannot be empty.")
    return normalized


def _ensure_unique_name(db: Session, name: str, exclude_id: int | None = None) -> None:
    query = db.query(models.Department).filter(func.lower(models.Department.name) == name.lower())
    if exclude_id is not None:
        query = query.filter(models.Department.id != exclude_id)
    if query.first():
        raise HTTPException(status_code=409, detail="A department with this name already exists.")


@router.get("", response_model=List[schemas.DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    query = db.query(models.Department)
    if current_user.role != models.UserRole.superadmin:
        visible_ids = auth.get_visible_department_ids(db, current_user)
        if not visible_ids:
            return []
        query = query.filter(models.Department.id.in_(visible_ids))
    return query.order_by(models.Department.name).all()


@router.post("", response_model=schemas.DepartmentOut, status_code=201)
def create_department(
    payload: schemas.DepartmentCreate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_superadmin),
):
    name = _normalize_name(payload.name)
    _ensure_unique_name(db, name)
    department = models.Department(name=name)
    db.add(department)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A department with this name already exists.") from exc
    db.refresh(department)
    return department


@router.patch("/{department_id}", response_model=schemas.DepartmentOut)
def update_department(
    department_id: int,
    payload: schemas.DepartmentUpdate,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_superadmin),
):
    department = db.query(models.Department).filter(models.Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found.")
    name = _normalize_name(payload.name)
    _ensure_unique_name(db, name, exclude_id=department_id)
    department.name = name
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A department with this name already exists.") from exc
    db.refresh(department)
    return department


@router.delete("/{department_id}", status_code=204)
def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    _: models.User = Depends(auth.require_superadmin),
):
    department = db.query(models.Department).filter(models.Department.id == department_id).first()
    if not department:
        raise HTTPException(status_code=404, detail="Department not found.")
    assigned_count = db.query(models.User.id).filter(models.User.department_id == department_id).count()
    if assigned_count:
        raise HTTPException(
            status_code=409,
            detail=f"Department is assigned to {assigned_count} member(s). Reassign them before deleting it.",
        )
    db.delete(department)
    db.commit()