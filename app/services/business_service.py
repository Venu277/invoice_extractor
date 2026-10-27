from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.business import Business
from app.models.user import User
from app.schemas.auth import BusinessProfileUpdate


def get_business_by_id(db: Session, business_id: int) -> Business:
    biz = db.query(Business).filter(Business.id == business_id).first()
    if not biz:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business not found."
        )
    return biz


def update_business_profile(
    db: Session, business_id: int, current_user: User, data: BusinessProfileUpdate
) -> Business:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners can update the business profile."
        )

    biz = get_business_by_id(db, business_id)

    update_dict = data.model_dump(exclude_unset=True)
    if "gstin" in update_dict and update_dict["gstin"]:
        gstin = update_dict["gstin"].strip().upper()
        update_dict["gstin"] = gstin
        if len(gstin) >= 2 and not update_dict.get("state_code"):
            update_dict["state_code"] = gstin[:2]

    for key, value in update_dict.items():
        setattr(biz, key, value)

    db.commit()
    db.refresh(biz)
    return biz
