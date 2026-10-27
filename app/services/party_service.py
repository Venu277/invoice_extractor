from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.party import Party
from app.schemas.parties import PartyCreate, PartyUpdate
from app.gst.rules import get_gstin_state_code


def get_or_create_party_from_invoice(
    db: Session,
    business_id: int,
    name: str | None,
    gstin: str | None,
    state_code: str | None,
    direction: str = "purchase"
) -> Party:
    """
    Suppliers and customers are created automatically from extracted invoices:
    Matched by GSTIN, then by normalised name.
    """
    clean_name = (name or "Unknown Party").strip()
    clean_gstin = gstin.strip().upper() if gstin else None

    # Determine party type: customer if sales, otherwise vendor
    party_type = "customer" if direction == "sales" else "vendor"

    party = None
    # 1. Match by GSTIN within tenant
    if clean_gstin:
        party = db.query(Party).filter(
            Party.business_id == business_id,
            Party.gstin == clean_gstin
        ).first()

    # 2. Match by normalized name
    if not party and clean_name:
        party = db.query(Party).filter(
            Party.business_id == business_id,
            Party.name.ilike(clean_name)
        ).first()

    if party:
        # If party was vendor and now has sales invoice, update to 'both'
        if party.type != party_type and party.type != "both":
            party.type = "both"
            db.commit()
            db.refresh(party)
        return party

    # 3. Create new party
    derived_state = state_code or get_gstin_state_code(clean_gstin)
    new_party = Party(
        business_id=business_id,
        name=clean_name,
        gstin=clean_gstin,
        state_code=derived_state,
        type=party_type,
        auto_created=True,
        payment_terms_days=30,
        credit_limit_paise=0
    )
    db.add(new_party)
    db.commit()
    db.refresh(new_party)
    return new_party


def list_parties(
    db: Session, business_id: int, party_type: str | None = None
) -> list[Party]:
    query = db.query(Party).filter(Party.business_id == business_id)
    if party_type and party_type != "all":
        query = query.filter(Party.type.in_([party_type, "both"]))
    return query.order_by(Party.name.asc()).all()


def get_party(db: Session, business_id: int, party_id: int) -> Party:
    party = db.query(Party).filter(
        Party.id == party_id,
        Party.business_id == business_id
    ).first()
    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Party not found."
        )
    return party


def update_party(
    db: Session, business_id: int, party_id: int, data: PartyUpdate
) -> Party:
    party = get_party(db, business_id, party_id)
    update_dict = data.model_dump(exclude_unset=True)

    if "gstin" in update_dict and update_dict["gstin"]:
        gstin = update_dict["gstin"].strip().upper()
        update_dict["gstin"] = gstin
        if not update_dict.get("state_code"):
            update_dict["state_code"] = get_gstin_state_code(gstin)

    for k, v in update_dict.items():
        setattr(party, k, v)

    db.commit()
    db.refresh(party)
    return party
