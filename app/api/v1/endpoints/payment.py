from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models
from app.core.config import settings
from app.db.session import get_db

router = APIRouter()

def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    """Formats all API responses consistently."""
    if status_code >= 400: status = "error"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "status_code": status_code, "message": message, "data": data or {}}
    )

@router.post("/webhooks/app-subscription")
async def app_subscription_webhook(
    request: Request, 
    x_webhook_secret: str = Header(None), 
    authorization: str = Header(None), 
    db: AsyncSession = Depends(get_db)
):
    """
    Secure Webhook to process RevenueCat Subscription Events (Using Email as ID).
    """
    # 1. Extract raw JSON payload
    try:
        payload = await request.json()
    except Exception:
        return standard_response(400, "Invalid JSON payload")

    # --- PRINT THE INCOMING DATA TO THE TERMINAL/RENDER LOGS ---
    print("\n" + "="*50)
    print("🚨 INCOMING REVENUECAT WEBHOOK 🚨")
    print(f"PAYLOAD DATA: {payload}")
    print("="*50 + "\n")

    # 2. SECURITY CHECK
    # RevenueCat uses the Authorization header (e.g., "Bearer your_secret")
    secret_provided = x_webhook_secret or (authorization.replace("Bearer ", "") if authorization else None)
    
    if secret_provided != settings.APP_WEBHOOK_SECRET:
        print(f"❌ FAILED: Invalid Webhook Secret! Received: {secret_provided}")
        return standard_response(401, "Unauthorized: Invalid Webhook Secret")

    # 3. Parse RevenueCat Event Data
    event = payload.get("event", {})
    if not event:
        return standard_response(400, "No event data found in payload")

    rc_event_type = event.get("type") 
    app_user_email = event.get("app_user_id") # RevenueCat appUserID is mapped to email
    product_id = event.get("product_id", "unknown") 
    price = event.get("price") 
    store = event.get("store", "Unknown") 
    
    # Safe float conversion (test webhooks sometimes send price as None)
    price_val = float(price) if price is not None else 0.0

    # 4. HANDLE REVENUECAT 'TEST' EVENT BUTTON
    if rc_event_type == "TEST":
        print("✅ SUCCESS: RevenueCat Test Webhook received and verified!")
        return standard_response(200, "Test webhook received successfully")

    if not app_user_email:
        print("❌ FAILED: Missing app_user_id (Email)")
        return standard_response(200, "Ignored: Missing app_user_id")

    # 5. FIND THE USER BY EMAIL
    # We use .ilike() for case-insensitive matching to be safe
    result = await db.execute(select(models.User).filter(models.User.email.ilike(app_user_email)))
    user = result.scalars().first()

    if not user:
        print(f"❌ FAILED: User email '{app_user_email}' not found in database.")
        return standard_response(200, f"Ignored: User {app_user_email} not found")

    # 6. Handle the RevenueCat Event logic
    message = ""
    plan = "annual" if "annual" in product_id.lower() or "year" in product_id.lower() else "monthly"

    if rc_event_type in["INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION"]:
        user.subscription_plan = plan
        
        # Log the transaction
        new_transaction = models.Transaction(
            user_id=user.id,
            amount=price_val,
            provider=f"RevenueCat ({store})",
            status="Completed"
        )
        db.add(new_transaction)
        message = f"User {user.email} upgraded to {plan} via RevenueCat"
        print(f"✅ SUCCESS: {message}")

    elif rc_event_type in ["CANCELLATION", "EXPIRATION"]:
        user.subscription_plan = "free"
        message = f"User {user.email} subscription downgraded to free via RevenueCat"
        print(f"✅ SUCCESS: {message}")
        
    else:
        message = f"Ignored RevenueCat event type: {rc_event_type}"
        print(f"⚠️ {message}")

    # 7. Save to Database
    await db.commit()
    
    return standard_response(200, message)