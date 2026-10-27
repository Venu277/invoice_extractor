from datetime import date
from sqlalchemy import Integer, String, Boolean, Date, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class RecurringTemplate(Base):
    __tablename__ = "recurring_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    party_id: Mapped[int] = mapped_column(Integer, ForeignKey("parties.id", ondelete="CASCADE"), nullable=False)
    items: Mapped[list | dict] = mapped_column(JSON, default=list, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)  # weekly, monthly, quarterly, yearly
    next_run: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_invoice_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("invoices.id", ondelete="SET NULL"), nullable=True)

    business = relationship("Business", back_populates="recurring_templates")
    party = relationship("Party")
