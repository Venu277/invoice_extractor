from datetime import datetime
from sqlalchemy import Integer, BigInteger, String, Boolean, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Party(Base):
    __tablename__ = "parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    type: Mapped[str] = mapped_column(String(20), default="vendor", nullable=False)  # vendor, customer, both
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_terms_days: Mapped[int | None] = mapped_column(Integer, default=30, nullable=True)
    credit_limit_paise: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    auto_created: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    business = relationship("Business", back_populates="parties")
    invoices = relationship("Invoice", back_populates="party")

    __table_args__ = (
        Index("ix_parties_business_gstin", "business_id", "gstin"),
    )
