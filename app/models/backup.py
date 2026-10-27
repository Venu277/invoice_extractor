from datetime import datetime
from sqlalchemy import Integer, BigInteger, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db import Base


class Backup(Base):
    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # manual, scheduled
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
