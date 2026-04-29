from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models
from app.core.config import settings
from app.db.session import get_db
from app.schemas.payment import AppSubscriptionWebhook
from fastapi import Request  

router = APIRouter()

def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    if status_code >= 400: status = "error"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "status_code": status_code, "message": message, "data": data or {}}
    )

@router.post("/webhooks/app-subscription")
async def app_subscription_webhook(
    request: Request, # Accept the raw request to bypass strict schema validation
    x_webhook_secret: str = Header(None), 
    authorization: str = Header(None), # RevenueCat often uses the Authorization header
    db: AsyncSession = Depends(get_db)
):
    """
    Secure Webhook to process RevenueCat Subscription Events.
    """
    # 1. Extract raw JSON payload
    try:
        payload = await request.json()
    except Exception:
        return standard_response(400, "Invalid JSON payload")

    print("\n" + "="*50)
    print("🚨 INCOMING REVENUECAT WEBHOOK 🚨")
    print(f"PAYLOAD DATA: {payload}")
    print("="*50 + "\n")

    # 2. SECURITY CHECK
    # RevenueCat lets developers set custom headers. We will check both our custom one
    # and the standard Authorization Bearer token they usually use.
    secret_provided = x_webhook_secret or (authorization.replace("Bearer ", "") if authorization else None)
    
    if secret_provided != settings.APP_WEBHOOK_SECRET:
        print(f"❌ FAILED: Invalid Webhook Secret! Received: {secret_provided}")
        return standard_response(401, "Unauthorized: Invalid Webhook Secret")

    # 3. Parse RevenueCat Event Data
    event = payload.get("event", {})
    if not event:
        return standard_response(400, "No event data found in payload")

    rc_event_type = event.get("type") # e.g., INITIAL_PURCHASE, RENEWAL, CANCELLATION, EXPIRATION
    app_user_id = event.get("app_user_id") # The user's ID
    product_id = event.get("product_id", "unknown") # e.g., monthly_plan
    price = event.get("price", 0.0)
    store = event.get("store", "Unknown") # APP_STORE, PLAY_STORE

    if not app_user_id or not app_user_id.isdigit():
        print(f"❌ FAILED: Invalid app_user_id: {app_user_id}")
        # Return 200 so RevenueCat stops retrying, but we log the failure
        return standard_response(200, "Ignored: Invalid or missing app_user_id")

    # 4. Find the user
    result = await db.execute(select(models.User).filter(models.User.id == int(app_user_id)))
    user = result.scalars().first()

    if not user:
        print(f"❌ FAILED: User ID {app_user_id} not found in database.")
        return standard_response(200, "Ignored: User not found")

    # 5. Handle the RevenueCat Event
    message = ""
    # Map their product ID to our internal plans
    plan = "annual" if "annual" in product_id.lower() or "year" in product_id.lower() else "monthly"

    if rc_event_type in["INITIAL_PURCHASE", "RENEWAL", "UNCANCELLATION"]:
        user.subscription_plan = plan
        
        # Log the transaction
        new_transaction = models.Transaction(
            user_id=user.id,
            amount=float(price),
            provider=f"RevenueCat ({store})",
            status="Completed"
        )
        db.add(new_transaction)
        message = f"User {user.id} upgraded to {plan} via RevenueCat"
        print(f"✅ SUCCESS: {message}")

    elif rc_event_type in["CANCELLATION", "EXPIRATION"]:
        user.subscription_plan = "free"
        message = f"User {user.id} subscription downgraded to free via RevenueCat"
        print(f"✅ SUCCESS: {message}")
        
    else:
        message = f"Ignored RevenueCat event type: {rc_event_type}"
        print(f"⚠️ {message}")

    # 6. Save to Database
    await db.commit()
    
    # Return 200 OK so RevenueCat marks the webhook as delivered successfully
    return standard_response(200, message)