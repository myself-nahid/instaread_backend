from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models
from app.core.config import settings
from app.db.session import get_db
from app.schemas.payment import AppSubscriptionWebhook 

router = APIRouter()

def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    if status_code >= 400: status = "error"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "status_code": status_code, "message": message, "data": data or {}}
    )

@router.post("/webhooks/app-subscription")
async def app_subscription_webhook(
    payload: AppSubscriptionWebhook,
    x_webhook_secret: str = Header(None), # The App developer must pass this in the Headers
    db: AsyncSession = Depends(get_db)
):
    """
    Secure Webhook for the Mobile App to update user subscription status.
    """
    # 1. SECURITY CHECK: Verify the secret key matches
    if x_webhook_secret != settings.APP_WEBHOOK_SECRET:
        return standard_response(401, "Unauthorized: Invalid Webhook Secret")

    # 2. Find the user
    result = await db.execute(select(models.User).filter(models.User.id == payload.user_id))
    user = result.scalars().first()

    if not user:
        return standard_response(404, "User not found")

    # 3. Handle the Event
    event = payload.event_type.lower()
    plan = payload.plan_name.lower()

    if event in["purchase", "renewal"]:
        # Upgrade the user
        user.subscription_plan = plan
        
        # Log the transaction
        new_transaction = models.Transaction(
            user_id=user.id,
            amount=payload.amount,
            provider=payload.provider,
            status="Completed"
            # (If you added a transaction_id column to your model, you can save it here too)
        )
        db.add(new_transaction)
        message = f"User {user.id} upgraded to {plan}"

    elif event == "cancellation":
        # Downgrade the user back to free
        user.subscription_plan = "free"
        message = f"User {user.id} subscription cancelled"
        
    else:
        return standard_response(400, f"Unknown event_type: {event}")

    # 4. Save to Database
    await db.commit()
    
    # Return a 200 OK so the App Developer knows it succeeded
    return standard_response(200, message)