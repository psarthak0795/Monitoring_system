from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=List[schemas.OrganizationOut])
def list_organizations(db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_admin)):
    if current_user.role == models.UserRole.super_admin:
        return db.query(models.Department).order_by(models.Department.name).all()
    if current_user.department_id is None:
        return []
    return db.query(models.Department).filter(models.Department.id == current_user.department_id).all()


@router.post("", response_model=schemas.OrganizationOut)
def create_organization(payload: schemas.OrganizationCreate, db: Session = Depends(get_db), _: models.User = Depends(auth.require_super_admin)):
    if db.query(models.Department).filter(models.Department.name == payload.name).first():
        raise HTTPException(status_code=400, detail="Organization already exists")
    organization = models.Department(name=payload.name)
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


@router.get("/{organization_id}/members", response_model=List[schemas.UserOut])
def list_members(organization_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(auth.require_admin)):
    if current_user.role != models.UserRole.super_admin and current_user.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="Organization access denied")
    return db.query(models.User).filter(models.User.department_id == organization_id).order_by(models.User.name).all()