from typing import Optional

from sqlalchemy.orm import Session

from . import models


def record(db: Session, actor: Optional[models.User], action: str, target_type: str, target_id=None, details=None):
    db.add(models.AuditEvent(
        actor_id=actor.id if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details or {},
    ))