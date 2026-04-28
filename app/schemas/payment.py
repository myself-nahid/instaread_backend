from pydantic import BaseModel
from typing import Optional

class AppSubscriptionWebhook(BaseModel):
    user_id: int
    plan_name: str          # e.g., "monthly", "annual", "free"
    event_type: str         # e.g., "purchase", "renewal", "cancellation"
    provider: str           # e.g., "Apple", "Google", "RevenueCat"
    transaction_id: str     # Unique receipt ID from Apple/Google
    amount: float = 0.0     # (Optional) How much they paid