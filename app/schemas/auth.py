from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(..., max_length=72, min_length=6)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=72)
    remember_me: Optional[bool] = False

class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., max_length=72)

class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str

class ResendOTPRequest(BaseModel):
    email: EmailStr

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str = Field(..., max_length=72, min_length=6)

class RefreshTokenRequest(BaseModel):
    refresh_token: str