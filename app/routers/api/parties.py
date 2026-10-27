from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.parties import PartyResponse, PartyUpdate
from app.services.party_service import list_parties, get_party, update_party

router = APIRouter(prefix="/parties", tags=["Parties (Vendors & Customers)"])


@router.get("", response_model=list[PartyResponse])
def get_parties(
    type: str | None = Query(None, description="vendor, customer, or all"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return list_parties(db, current_user.business_id, party_type=type)


@router.get("/{party_id}", response_model=PartyResponse)
def get_party_detail(
    party_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_party(db, current_user.business_id, party_id)


@router.put("/{party_id}", response_model=PartyResponse)
def edit_party(
    party_id: int,
    data: PartyUpdate,
    current_user: User = Depends(require_role("owner", "accountant")),
    db: Session = Depends(get_db)
):
    return update_party(db, current_user.business_id, party_id, data)
