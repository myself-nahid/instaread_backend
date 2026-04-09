from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
import uuid
import os

from app import models
from app.api import deps
from app.core import security
from app.db.session import get_db
from app.schemas.settings import AccountInfoUpdate, SubscriptionUpgradeRequest
from app.utils.cloudinary_uploader import upload_profile_image

router = APIRouter()

def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    if status_code >= 400:
        status = "error"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "status_code": status_code, "message": message, "data": data or {}}
    )

# 1. GET SETTINGS PROFILE (Settings Main Page)
@router.get("/profile")
async def get_settings_profile(
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches user info and lifetime scan limits for the Settings dashboard."""
    
    # Count how many scans the user has made
    result = await db.execute(
        select(func.count(models.BookScan.id)).filter(models.BookScan.owner_id == current_user.id)
    )
    total_scans = result.scalar() or 0
    
    # Calculate limits based on plan
    max_scans = 100 if current_user.subscription_plan == "free" else "Unlimited"
    scans_remaining = (100 - total_scans) if current_user.subscription_plan == "free" else "Unlimited"
    
    # Ensure remaining isn't negative
    if isinstance(scans_remaining, int) and scans_remaining < 0:
        scans_remaining = 0

    user_role = "admin" if current_user.is_superuser else "user"

    data = {
        "user": {
            "name": current_user.full_name,
            "email": current_user.email,
            "profile_picture_url": current_user.profile_picture_url,
            "role": user_role
        },
        "subscription": {
            "current_plan": current_user.subscription_plan.capitalize() + " Tier",
            "lifetime_scans_used": total_scans,
            "lifetime_scans_max": max_scans,
            "scans_remaining": scans_remaining
        }
    }
    
    return standard_response(200, "Settings profile fetched successfully", data)

# 6. UPLOAD/CHANGE PROFILE PICTURE (Cloudinary)
@router.post("/profile-picture")
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Handles uploading a new profile picture for the user to Cloudinary."""
    
    # 1. Validate File Type
    if file.content_type not in ["image/jpeg", "image/png"]:
        return standard_response(400, "Invalid file type. Please upload a JPG or PNG image.")

    # 2. Upload to Cloudinary using our utility function
    public_file_url = await upload_profile_image(file, current_user.id)
    
    if not public_file_url:
        return standard_response(500, "Failed to upload profile picture.")

    # 3. Update the user's record in the database with the new Cloudinary URL
    current_user.profile_picture_url = public_file_url
    await db.commit()
    
    return standard_response(200, "Profile picture updated successfully", {
        "profile_picture_url": public_file_url
    })

# 2. UPDATE ACCOUNT INFO
@router.put("/account-info")
async def update_account_info(
    payload: AccountInfoUpdate,
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Updates user name and/or password."""
    
    # Update Name
    if payload.full_name:
        current_user.full_name = payload.full_name
        
    # Update Password
    if payload.new_password:
        if not payload.current_password:
            return standard_response(400, "Current password is required to set a new password.")
            
        if not security.verify_password(payload.current_password, current_user.hashed_password):
            return standard_response(400, "Incorrect current password.")
            
        current_user.hashed_password = security.get_password_hash(payload.new_password)
        
    await db.commit()
    await db.refresh(current_user)
    
    return standard_response(200, "Account info updated successfully", {
        "name": current_user.full_name,
        "email": current_user.email
    })

# 3. UPGRADE SUBSCRIPTION
@router.post("/subscription/upgrade")
async def upgrade_subscription(
    payload: SubscriptionUpgradeRequest,
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mocks upgrading a subscription to Monthly or Annual."""
    plan = payload.plan_name.lower()
    
    if plan not in ["monthly", "annual"]:
        return standard_response(400, "Invalid plan selected. Choose 'monthly' or 'annual'.")
        
    if current_user.subscription_plan == plan:
        return standard_response(400, f"You are already on the {plan} plan.")
        
    # In a real app, you would integrate Stripe/PayPal API here before updating the DB.
    current_user.subscription_plan = plan
    await db.commit()
    
    return standard_response(200, f"Successfully upgraded to the {plan.capitalize()} Plan.", {
        "current_plan": plan
    })

# 4. CANCEL SUBSCRIPTION
@router.post("/subscription/cancel")
async def cancel_subscription(
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancels active subscription and reverts to Free Plan."""
    if current_user.subscription_plan == "free":
        return standard_response(400, "You do not have an active premium subscription to cancel.")
        
    # In a real app, you would cancel the Stripe/PayPal recurring payment here.
    current_user.subscription_plan = "free"
    await db.commit()
    
    return standard_response(200, "Subscription cancelled successfully. You are now on the Free Tier.")

# # 5. GET LEGAL DOCUMENTS
# @router.get("/legal")
# async def get_legal_documents():
#     """Returns dynamic text for Privacy Policy and Terms of Agreement."""
#     data = {
#         "privacy_policy":[
#             {"title": " Information We Collect", "body": "Our app requires access to your device's camera to scan book covers or barcodes..."},
#         ],
#         "terms_and_agreement": {
#             "important_info": "This application provides AI-generated interpretations of book descriptions. These ratings are not definitive judgments.",
#             "parental_responsibility": "Parents remain fully responsible for determining the suitability of books for their children.",
#             "about_our_ratings": "The safety ratings provided by this app are generated by artificial intelligence based on publicly available book descriptions.",
#             "rating_system": {
#                 "Green": "Safe - Content appears appropriate for children",
#                 "Yellow": "Caution - May contain themes requiring parental guidance",
#                 "Red": "Concerning - Contains mature themes not suitable for young children"
#             }
#         }
#     }
#     return standard_response(200, "Legal documents fetched successfully", data)

# 5. GET LEGAL DOCUMENTS (Dynamic Text for Privacy Policy and Terms of Agreement)
@router.get("/legal")
async def get_legal_documents(db: AsyncSession = Depends(get_db)):
    """Fetches the latest Privacy Policy and Terms of Agreement from the database."""
    
    result = await db.execute(select(models.Policy))
    policies = result.scalars().all()
    
    data = {}
    for policy in policies:
        if "privacy" in policy.slug:
            data["privacy_policy"] = {"title": policy.title, "description": policy.description}
        elif "terms" in policy.slug:
            data["terms_and_agreement"] = {"title": policy.title, "description": policy.description}
    
    return standard_response(200, "Legal documents fetched successfully", data)