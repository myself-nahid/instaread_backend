import stripe
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app import models
from app.api import deps
from app.core.config import settings
from app.db.session import get_db

stripe.api_key = settings.STRIPE_SECRET_KEY

router = APIRouter()

STRIPE_PRICE_ID_MAP = {
    "monthly": "price_1SNnG4CA7xIZZJGSBYEkD37N",
    "annual": "price_1SNnHtCA7xIZZJGSp3YRq0JA"
}

def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    if status_code >= 400: status = "error"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "status_code": status_code, "message": message, "data": data or {}}
    )

@router.post("/create-checkout-session")
async def create_checkout_session(
    plan_name: str,
    current_user: models.User = Depends(deps.get_current_user)
):
    """
    Creates a Stripe Checkout session with line_items expanded for the webhook.
    """
    plan = plan_name.lower()
    if plan not in STRIPE_PRICE_ID_MAP:
        return standard_response(400, "Invalid plan selected. Choose 'monthly' or 'annual'.")

    price_id = STRIPE_PRICE_ID_MAP[plan]

    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[{"price": price_id, "quantity": 1}],
            mode='subscription',
            client_reference_id=str(current_user.id),
            success_url='https://safe-read.netlify.app?session_id={CHECKOUT_SESSION_ID}',
            cancel_url='https://safe-read.netlify.app/cancel',
            expand=['line_items'], 
        )
        return standard_response(200, "Checkout session created.", {"checkout_url": checkout_session.url})

    except Exception as e:
        return standard_response(500, f"Error creating Stripe session: {str(e)}")


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Listens for events from Stripe and updates the user's subscription on successful payment.
    """
    try:
        payload = await request.body()
        event = stripe.Webhook.construct_event(
            payload=payload, 
            sig_header=stripe_signature, 
            secret=settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        return standard_response(400, f"Webhook signature verification failed: {str(e)}")

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        try:
            session_with_line_items = stripe.checkout.Session.retrieve(
                session.id,
                expand=["line_items"]
            )
            line_items = session_with_line_items.line_items
            if not line_items or not line_items.data:
                print(f"ERROR: Could not retrieve line_items for session {session.id}")
                return JSONResponse(content={'status': 'error', 'message': 'Could not retrieve line_items'}, status_code=200)
        except Exception as e:
            print(f"ERROR retrieving session from Stripe: {str(e)}")
            return JSONResponse(content={'status': 'error', 'message': 'Stripe API error'}, status_code=200)

        user_id = session['client_reference_id']
        amount_total = session['amount_total']
        payment_provider = "Stripe"
        
        if not user_id:
            return standard_response(400, "Webhook received without a client_reference_id.")

        result = await db.execute(select(models.User).filter(models.User.id == int(user_id)))
        user = result.scalars().first()

        if user:
            plan_id = line_items['data'][0]['price']['id']
            new_plan_status = "monthly" if plan_id == STRIPE_PRICE_ID_MAP["monthly"] else "annual"

            user.subscription_plan = new_plan_status
            
            new_transaction = models.Transaction(
                user_id=user.id,
                amount=amount_total / 100.0,
                provider=payment_provider,
                status="Completed"
            )
            db.add(new_transaction)
            
            await db.commit()
            print(f"Successfully updated user {user.id} to {new_plan_status} plan.")

    return JSONResponse(content={'status': 'received'}, status_code=200)