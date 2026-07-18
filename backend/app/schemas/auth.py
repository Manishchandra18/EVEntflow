from pydantic import BaseModel, EmailStr, Field


class StudentOtpRequest(BaseModel):
    email: EmailStr


class AdminOtpRequest(BaseModel):
    superadmin_email: EmailStr


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    # Student flow: OTP sent to student's own email
    student_otp: str | None = Field(default=None, min_length=6, max_length=6)
    # Admin flow: OTP sent to superadmin's email; superadmin_email identifies which OTP record to check
    admin_otp: str | None = Field(default=None, min_length=6, max_length=6)
    superadmin_email: EmailStr | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    name: str
    email: EmailStr
    role: str
    is_superadmin: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
