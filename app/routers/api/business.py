from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.auth import BusinessProfileUpdate, BusinessResponse
from app.services.business_service import get_business_by_id, update_business_profile

router = APIRouter(prefix="/business", tags=["Business Profile"])


@router.get("/profile", response_model=BusinessResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    biz = get_business_by_id(db, current_user.business_id)
    return biz


@router.put("/profile", response_model=BusinessResponse)
def update_profile(
    data: BusinessProfileUpdate,
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db)
):
    biz = update_business_profile(db, current_user.business_id, current_user, data)
    return biz
