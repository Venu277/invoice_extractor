from datetime import datetime, date
from sqlalchemy import Integer, BigInteger, Numeric, String, Text, Date, DateTime, ForeignKey, JSON, Index, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    business_id: Mapped[int] = mapped_column(Integer, ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    party_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("parties.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, unique=True)

    direction: Mapped[str] = mapped_column(String(20), default="purchase", nullable=False)  # purchase, sales, unknown
    source: Mapped[str] = mapped_column(String(20), default="extracted", nullable=False)     # extracted, generated

    invoice_no: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    supplier_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    buyer_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    place_of_supply_state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Money columns in INTEGER PAISE
    taxable: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cgst: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sgst: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    igst: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cess: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    amount_paid: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid", nullable=False)  # unpaid, partial, paid
    review_status: Mapped[str] = mapped_column(String(30), default="pending_review", nullable=False)  # pending_review, approved, rejected
    validation_status: Mapped[str] = mapped_column(String(20), default="ok", nullable=False)         # ok, warnings, errors
    validation_issues: Mapped[dict | list | None] = mapped_column(JSON, default=list, nullable=True)
    field_confidence: Mapped[dict | None] = mapped_column(JSON, default=dict, nullable=True)

    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    in_workspace: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    business = relationship("Business", back_populates="invoices")
    party = relationship("Party", back_populates="invoices")
    document = relationship("Document", back_populates="invoice")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_invoices_business_direction", "business_id", "direction"),
        Index("ix_invoices_business_review_status", "business_id", "review_status"),
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    hsn_sac: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(12, 4), default=1.0, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20), default="NOS", nullable=True)

    # Rates & Amounts in INTEGER PAISE
    rate: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    taxable: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    gst_rate: Mapped[float] = mapped_column(Numeric(5, 2), default=18.0, nullable=False)  # e.g. 18.0 for 18%
    cgst: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sgst: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    igst: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    invoice = relationship("Invoice", back_populates="items")
