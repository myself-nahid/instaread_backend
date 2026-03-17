from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt, JWTError

from app import models
from app.schemas import auth as auth_schemas
from app.core import security
from app.core.config import settings
from app.db.session import get_db

router = APIRouter()

# Helper function for standard responses
def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    if status_code >= 400:
        status = "error"
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "status_code": status_code,
            "message": message,
            "data": data or {}
        }
    )

# Helper function to mock sending emails 
async def send_email_mock(email: str, otp: str, context: str):
    print(f"[{context}] Sending OTP {otp} to {email}")

# 1. SIGN UP API
@router.post("/signup")
async def signup(payload: auth_schemas.SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    if user:
        return standard_response(400, "User with this email already exists.")
    
    otp = security.generate_4_digit_otp()
    otp_expiry = datetime.utcnow() + timedelta(minutes=10) # OTP valid for 10 mins
    
    new_user = models.User(
        full_name=payload.name,
        email=payload.email,
        hashed_password=security.get_password_hash(payload.password),
        is_verified=False,
        otp=otp,
        otp_expire_at=otp_expiry
    )
    db.add(new_user)
    await db.commit()
    
    await send_email_mock(payload.email, otp, "Signup Verification")
    
    return standard_response(201, "Signup successful. Please verify your email.", {"email": payload.email})

# 2. VERIFY OTP (For Signup)
@router.post("/verify-otp")
async def verify_otp(payload: auth_schemas.OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    if not user:
        return standard_response(404, "User not found.")
    
    if user.is_verified:
        return standard_response(400, "Email is already verified.")
        
    if user.otp != payload.otp:
        return standard_response(400, "Invalid OTP.")
        
    # Python relies on naive datetimes by default unless configured; ensure matching timezone info
    if user.otp_expire_at.replace(tzinfo=None) < datetime.utcnow():
        return standard_response(400, "OTP has expired. Please request a new one.")
        
    # Success
    user.is_verified = True
    user.otp = None
    user.otp_expire_at = None
    await db.commit()
    
    return standard_response(200, "Email successfully verified. You can now log in.")

# 3. RESEND OTP API
@router.post("/resend-otp")
async def resend_otp(payload: auth_schemas.ResendOTPRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    if not user:
        return standard_response(404, "User not found.")
        
    new_otp = security.generate_4_digit_otp()
    user.otp = new_otp
    user.otp_expire_at = datetime.utcnow() + timedelta(minutes=10)
    await db.commit()
    
    await send_email_mock(payload.email, new_otp, "Resend OTP")
    
    return standard_response(200, "A new OTP has been sent to your email.")

# 4. LOGIN API
@router.post("/login")
async def login(payload: auth_schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    if not user or not security.verify_password(payload.password, user.hashed_password):
        return standard_response(401, "Invalid email or password.")
        
    if not user.is_verified:
        return standard_response(403, "Email is not verified. Please verify your email first.")
    
    # Generate Tokens
    access_token = security.create_access_token(subject=user.email)
    
    # If "Remember Me" is true, want to issue a longer-lived refresh token
    refresh_token_expiry = timedelta(days=30) if payload.remember_me else timedelta(days=7)
    refresh_token = security.create_refresh_token(subject=user.email, expires_delta=refresh_token_expiry)
    
    data = {
        "user": {
            "name": user.full_name,
            "email": user.email,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    }
    
    return standard_response(200, "Login successful", data)

# 5. REFRESH TOKEN API
@router.post("/refresh")
async def refresh_token(payload: auth_schemas.RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    try:
        # Decode the refresh token
        decoded = jwt.decode(payload.refresh_token, settings.SECRET_KEY, algorithms=[security.ALGORITHM])
        
        # Verify it's actually a refresh token
        if decoded.get("type") != "refresh":
            return standard_response(401, "Invalid token type.")
            
        email = decoded.get("sub")
        if not email:
            return standard_response(401, "Invalid token payload.")
            
        # Ensure user still exists and is active
        result = await db.execute(select(models.User).filter(models.User.email == email))
        user = result.scalars().first()
        if not user or not user.is_active:
            return standard_response(401, "User is no longer active.")
            
        # Generate new access token
        new_access_token = security.create_access_token(subject=user.email)
        
        return standard_response(200, "Token refreshed successfully", {
            "access_token": new_access_token,
            "token_type": "bearer"
        })
        
    except JWTError:
        return standard_response(401, "Invalid or expired refresh token. Please log in again.")

# 6. FORGOT PASSWORD API (Sends OTP)
@router.post("/forgot-password")
async def forgot_password(payload: auth_schemas.ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    if not user:
        # Return success even if user doesn't exist to prevent email enumeration attacks
        return standard_response(200, "If an account exists with that email, an OTP has been sent.")
        
    otp = security.generate_4_digit_otp()
    user.otp = otp
    user.otp_expire_at = datetime.utcnow() + timedelta(minutes=15)
    await db.commit()
    
    await send_email_mock(payload.email, otp, "Forgot Password Reset")
    
    return standard_response(200, "If an account exists with that email, an OTP has been sent.")

# 7. VERIFY FORGOT PASSWORD OTP
@router.post("/verify-forgot-password-otp")
async def verify_forgot_password_otp(payload: auth_schemas.OTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    if not user or user.otp != payload.otp:
        return standard_response(400, "Invalid or expired OTP.")
        
    if user.otp_expire_at.replace(tzinfo=None) < datetime.utcnow():
        return standard_response(400, "OTP has expired. Please request a new one.")
        
    # We do NOT clear the OTP here. We wait for the actual Reset Password step to consume it.
    return standard_response(200, "OTP verified successfully. You may now reset your password.")

# 8. RESET PASSWORD API
@router.post("/reset-password")
async def reset_password(payload: auth_schemas.ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    # Strict check to ensure OTP matches before allowing password reset
    if not user or user.otp != payload.otp:
        return standard_response(400, "Invalid request. Please restart the password reset process.")
        
    if user.otp_expire_at.replace(tzinfo=None) < datetime.utcnow():
        return standard_response(400, "OTP has expired. Please request a new one.")
        
    # Hash new password and clear OTP
    user.hashed_password = security.get_password_hash(payload.new_password)
    user.otp = None
    user.otp_expire_at = None
    await db.commit()
    
    return standard_response(200, "Password has been successfully reset. You can now log in.")

# 9. LOGOUT API
@router.post("/logout")
async def logout():
    """
    Since we are using stateless JWTs, true logout happens client-side 
    (by deleting the access/refresh tokens from mobile storage).
    This endpoint exists to fulfill the UI action and return a standard response.
    """
    return standard_response(200, "Successfully logged out.")