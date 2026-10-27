from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models.user import User
from app.models.backup import Backup
from app.services.backup_service import create_backup, restore_backup

router = APIRouter(prefix="/backups", tags=["Backups & Restore"])


@router.get("")
def list_backups(
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db)
):
    return db.query(Backup).order_by(Backup.created_at.desc()).all()


@router.post("", status_code=status.HTTP_201_CREATED)
def trigger_backup(
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db)
):
    b = create_backup(db, kind="manual")
    return {"message": "Backup created successfully", "id": b.id, "path": b.path, "size_bytes": b.size_bytes}


@router.post("/{backup_id}/restore")
def do_restore(
    backup_id: int,
    confirm: bool = Query(..., description="Must explicitly confirm database restoration"),
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db)
):
    if not confirm:
        return {"error": "Restoration aborted: Confirmation parameter 'confirm=true' required."}
    restore_backup(db, backup_id, current_user)
    return {"message": "Database and uploads restored successfully from backup."}
