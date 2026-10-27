import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Response, Request, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.auth import (
    SignupRequest,
    SignupResponse,
    LoginRequest,
    TokenResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    TokenPasswordResetRequest,
    UserCreateRequest,
    UserResponse
)
from app.services.auth_service import (
    signup_business,
    authenticate_user,
    reset_password_with_recovery_code,
    create_team_member,
    list_team_members
)
from app.services.security import hash_password, create_access_token
from app.services.share_service import send_password_reset_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(req: SignupRequest, db: Session = Depends(get_db)):
    biz, user, recovery_code = signup_business(db, req)
    return SignupResponse(
        message="Business and owner account created successfully.",
        business_id=biz.id,
        user_id=user.id,
        email=user.email,
        recovery_code=recovery_code
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user, token = authenticate_user(db, req.email, req.password)

    # Set 12-hour HttpOnly cookie for web browsing
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        max_age=12 * 3600,
        httponly=True,
        samesite="lax",
        secure=False  # Allow local HTTP testing; set True over HTTPS
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        business_id=user.business_id,
        user_name=user.name
    )


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.post("/recovery-reset", response_model=PasswordResetResponse)
def recovery_reset(req: PasswordResetRequest, db: Session = Depends(get_db)):
    new_recovery = reset_password_with_recovery_code(
        db, req.email, req.recovery_code, req.new_password
    )
    return PasswordResetResponse(
        message="Password has been reset successfully. Please store your new recovery code.",
        new_recovery_code=new_recovery
    )


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(req: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    email_clean = req.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No account found with email '{email_clean}'."
        )

    token = secrets.token_urlsafe(32)
    user.reset_token = token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()

    base_url = str(request.base_url).rstrip("/")
    reset_url = f"{base_url}/auth/reset-password?token={token}"

    send_password_reset_email(user.email, reset_url)

    return ForgotPasswordResponse(
        message="Password reset link generated and sent to registered email.",
        email=user.email,
        reset_url=reset_url
    )


@router.post("/reset-password", response_model=TokenResponse)
def reset_password(req: TokenPasswordResetRequest, response: Response, db: Session = Depends(get_db)):
    if len(req.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters."
        )

    user = db.query(User).filter(
        User.reset_token == req.token,
        User.reset_token_expires > datetime.utcnow()
    ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset link is invalid or has expired."
        )

    # Update password in company database
    user.password_hash = hash_password(req.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()

    # Generate token and log user in immediately
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
        "business_id": user.business_id,
        "user_name": user.name
    })

    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        max_age=12 * 3600,
        httponly=True,
        samesite="lax",
        secure=False
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        business_id=user.business_id,
        user_name=user.name
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/team", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def add_team_member(
    req: UserCreateRequest,
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db)
):
    new_member = create_team_member(db, current_user, req)
    return new_member


@router.get("/team", response_model=list[UserResponse])
def get_team(
    current_user: User = Depends(require_role("owner")),
    db: Session = Depends(get_db)
):
    return list_team_members(db, current_user)
