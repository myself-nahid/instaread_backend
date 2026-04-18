from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt, JWTError

from app import models
from app.api import deps
from app.schemas import auth as auth_schemas
from app.models.user import User
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.utils.email import send_otp_email

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
# async def send_email_mock(email: str, otp: str, context: str):
#     print(f"[{context}] Sending OTP {otp} to {email}")

# 1. SIGN UP API
@router.post("/signup")
async def signup(payload: auth_schemas.SignupRequest, db: AsyncSession = Depends(get_db)):
    # 1. Check if user already exists
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    otp = security.generate_6_digit_otp()
    otp_expiry = datetime.utcnow() + timedelta(minutes=10)
    
    if user:
        # SCENARIO A: User exists and is already verified
        if user.is_verified:
            return standard_response(400, "User with this email already exists. Please log in.")
        
        # SCENARIO B: User exists but was NEVER verified (Abandoned signup)
        # Update the existing record with new info and a new OTP
        user.full_name = payload.name
        user.hashed_password = security.get_password_hash(payload.password)
        user.otp = otp
        user.otp_expire_at = otp_expiry
        
        await db.commit()
        await send_otp_email(payload.email, otp, subject="Verify Your Account")
        
        return standard_response(200, "Account registration restarted. A new OTP has been sent to your email.", {"email": payload.email})

    # SCENARIO C: New user signup
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
    
    await send_otp_email(payload.email, otp, subject="Verify Your Account")
    
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
        
    new_otp = security.generate_6_digit_otp()
    user.otp = new_otp
    user.otp_expire_at = datetime.utcnow() + timedelta(minutes=10)
    await db.commit()
    
    await send_otp_email(payload.email, new_otp, subject="Your New Verification Code")
    
    return standard_response(200, "A new OTP has been sent to your email.", {"otp": new_otp})

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
            "user_id": user.id,
            "user_type": "admin" if user.is_superuser else "regular"
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
        return standard_response(200, "If an account exists with that email, an OTP has been sent.")  
        
    otp = security.generate_6_digit_otp()
    user.otp = otp
    user.otp_expire_at = datetime.utcnow() + timedelta(minutes=15)
    await db.commit()
    
    await send_otp_email(payload.email, otp, subject="Password Reset Request")
    
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

# 10. DELETE ACCOUNT API
@router.delete("/delete-account")
async def delete_account(
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await db.delete(current_user)
    await db.commit()
    return standard_response(200, "Your account has been deleted successfully.")

# 11. ADMIN LOGIN API
@router.post("/admin/login")
async def admin_login(payload: auth_schemas.AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Handles login for admin users (superusers) only.
    """
    result = await db.execute(select(models.User).filter(models.User.email == payload.email))
    user = result.scalars().first()
    
    if not user:
        return standard_response(401, "Invalid email or password.")
        
    if not user.is_superuser:
        return standard_response(403, "Access Denied. This login is for administrators only.")
        
    if not security.verify_password(payload.password, user.hashed_password):
        return standard_response(401, "Invalid email or password.")
    
    access_token = security.create_access_token(subject=user.email)
    refresh_token = security.create_refresh_token(subject=user.email, expires_delta=timedelta(days=7))
    
    data = {
        "admin": {
            "name": user.full_name,
            "email": user.email,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        },
        "role": user.role if hasattr(user, "role") else "admin"
    }
    
    return standard_response(200, "Admin login successful", data)