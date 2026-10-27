from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.business import Business
from app.models.user import User
from app.schemas.auth import SignupRequest, UserCreateRequest
from app.services.security import (
    hash_password,
    verify_password,
    generate_recovery_code,
    create_access_token
)


def signup_business(db: Session, req: SignupRequest) -> tuple[Business, User, str]:
    email_clean = req.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists."
        )

    # Derive state code from GSTIN if available
    state_code = req.state_code
    gstin = req.gstin.strip().upper() if req.gstin else None
    if gstin and len(gstin) >= 2 and not state_code:
        state_code = gstin[:2]

    biz = Business(
        name=req.business_name.strip(),
        gstin=gstin,
        state_code=state_code,
    )
    db.add(biz)
    db.flush()

    recovery_code = generate_recovery_code()
    user = User(
        business_id=biz.id,
        name=req.owner_name.strip(),
        email=email_clean,
        password_hash=hash_password(req.password),
        role="owner",
        recovery_hash=hash_password(recovery_code),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(biz)
    db.refresh(user)

    return biz, user, recovery_code


def authenticate_user(db: Session, email: str, password: str) -> tuple[User, str]:
    email_clean = email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    now = datetime.utcnow()
    if user.locked_until and now < user.locked_until:
        remaining_secs = int((user.locked_until - now).total_seconds())
        mins = max(1, remaining_secs // 60)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account locked due to 5 failed attempts. Please retry after {mins} minute(s)."
        )

    if not verify_password(password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= 5:
            user.locked_until = now + timedelta(minutes=5)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Success: reset lockout
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()

    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "business_id": user.business_id,
        "user_name": user.name
    })

    return user, token


def reset_password_with_recovery_code(
    db: Session, email: str, recovery_code: str, new_password: str
) -> str:
    email_clean = email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user or not user.recovery_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or recovery code."
        )

    if not verify_password(recovery_code.strip(), user.recovery_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid recovery code."
        )

    # Set new password and generate a fresh recovery code
    new_recovery = generate_recovery_code()
    user.password_hash = hash_password(new_password)
    user.recovery_hash = hash_password(new_recovery)
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()

    return new_recovery


def create_team_member(
    db: Session, current_user: User, req: UserCreateRequest
) -> User:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners can add team members."
        )

    email_clean = req.email.strip().lower()
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists."
        )

    recovery_code = generate_recovery_code()
    user = User(
        business_id=current_user.business_id,
        name=req.name.strip(),
        email=email_clean,
        password_hash=hash_password(req.password),
        role=req.role,
        recovery_hash=hash_password(recovery_code),
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_team_members(db: Session, current_user: User) -> list[User]:
    if current_user.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners can view team members."
        )
    return db.query(User).filter(User.business_id == current_user.business_id).all()
