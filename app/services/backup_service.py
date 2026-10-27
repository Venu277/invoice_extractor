import os
import shutil
import sqlite3
import json
import zipfile
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.config import settings
from app.models.backup import Backup
from app.models.user import User


def create_backup(db: Session, kind: str = "manual") -> Backup:
    """
    Creates a consistent ZIP backup of the SQLite database (using sqlite3 backup API)
    and the uploads directory, with a JSON manifest.
    Retains only the latest 7 backups.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}_{kind}.zip"
    backup_path = settings.backup_path / backup_filename

    # 1. Consistent SQLite snapshot
    temp_db_path = settings.backup_path / f"temp_{timestamp}.db"
    db_source_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_source_path.startswith("./"):
        db_source_path = db_source_path[2:]

    real_db_file = Path(db_source_path)

    if real_db_file.exists():
        src_conn = sqlite3.connect(str(real_db_file))
        dst_conn = sqlite3.connect(str(temp_db_path))
        with dst_conn:
            src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

    # 2. Package ZIP
    manifest = {
        "app": settings.APP_NAME,
        "timestamp": datetime.utcnow().isoformat(),
        "kind": kind,
        "database_file": "app.db",
        "uploads_count": len(list(settings.upload_path.glob("*")))
    }

    with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as z:
        if temp_db_path.exists():
            z.write(str(temp_db_path), arcname="data/app.db")
            os.remove(temp_db_path)

        for up_file in settings.upload_path.glob("*"):
            if up_file.is_file():
                z.write(str(up_file), arcname=f"uploads/{up_file.name}")

        z.writestr("manifest.json", json.dumps(manifest, indent=2))

    size_bytes = backup_path.stat().st_size

    # Record in database
    rec = Backup(
        path=str(backup_path),
        size_bytes=size_bytes,
        kind=kind
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)

    # Rotation: Keep last 7 backups
    all_backups = db.query(Backup).order_by(Backup.created_at.desc()).all()
    if len(all_backups) > 7:
        to_delete = all_backups[7:]
        for b in to_delete:
            p = Path(b.path)
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
            db.delete(b)
        db.commit()

    return rec


def restore_backup(db: Session, backup_id: int, current_user: User) -> None:
    """
    Owner-only database & uploads restore.
    First takes an automatic safety backup before overwriting.
    """
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners can restore backups."
        )

    b = db.query(Backup).filter(Backup.id == backup_id).first()
    if not b or not Path(b.path).exists():
        raise HTTPException(status_code=404, detail="Backup file not found.")

    # 1. Automatic safety backup
    create_backup(db, kind="pre_restore_safety")

    # 2. Extract backup ZIP
    db_source_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_source_path.startswith("./"):
        db_source_path = db_source_path[2:]
    target_db = Path(db_source_path)

    with zipfile.ZipFile(b.path, "r") as z:
        for member in z.namelist():
            if member == "data/app.db":
                z.extract(member, path=".")
            elif member.startswith("uploads/"):
                z.extract(member, path=".")
