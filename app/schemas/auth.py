from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class SignupRequest(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=255)
    owner_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=6)
    gstin: str | None = Field(None, max_length=15)
    state_code: str | None = Field(None, max_length=2)


class SignupResponse(BaseModel):
    message: str
    business_id: int
    user_id: int
    email: str
    recovery_code: str  # One-time recovery code shown once at signup


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    business_id: int
    user_name: str


class PasswordResetRequest(BaseModel):
    email: EmailStr
    recovery_code: str
    new_password: str = Field(..., min_length=6)


class PasswordResetResponse(BaseModel):
    message: str
    new_recovery_code: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str
    email: str
    reset_url: str | None = None


class TokenPasswordResetRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class UserCreateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(..., pattern="^(accountant|staff)$")


class UserResponse(BaseModel):
    id: int
    business_id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BusinessProfileUpdate(BaseModel):
    name: str | None = None
    gstin: str | None = None
    state_code: str | None = None
    address: str | None = None
    phone: str | None = None
    email: EmailStr | None = None
    logo_path: str | None = None
    bank_name: str | None = None
    account_no: str | None = None
    ifsc: str | None = None
    upi_id: str | None = None
    invoice_prefix: str | None = None
    fy_start_month: int | None = Field(None, ge=1, le=12)
    default_payment_terms_days: int | None = Field(None, ge=0)


class BusinessResponse(BaseModel):
    id: int
    name: str
    gstin: str | None
    state_code: str | None
    address: str | None
    phone: str | None
    email: str | None
    logo_path: str | None
    bank_name: str | None
    account_no: str | None
    ifsc: str | None
    upi_id: str | None
    invoice_prefix: str
    fy_start_month: int
    default_payment_terms_days: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
