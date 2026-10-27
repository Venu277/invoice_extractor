from collections.abc import Callable
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.user import User
from app.services.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_token_from_request(
    request: Request,
    auth_header: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)
) -> str | None:
    # 1. Bearer Token in Authorization header
    if auth_header and auth_header.credentials:
        return auth_header.credentials

    # 2. HttpOnly Cookie session
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # If stored with Bearer prefix, strip it
        if cookie_token.startswith("Bearer "):
            return cookie_token[7:]
        return cookie_token

    return None


def get_current_user(
    request: Request,
    token: str | None = Depends(get_token_from_request),
    db: Session = Depends(get_db)
) -> User:
    if not token:
        # Check if this is an API call or Web call
        if request.url.path.startswith("/api/"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # Web routes will redirect to /login
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or not logged in"
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token"
        )

    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    # Attach tenant context to request state for audit & isolation
    request.state.current_user = user
    request.state.business_id = user.business_id

    return user


def require_role(*roles: str) -> Callable[[User], User]:
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Requires one of roles: {', '.join(roles)}"
            )
        return current_user
    return role_checker
