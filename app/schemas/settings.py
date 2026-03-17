from pydantic import BaseModel, Field, EmailStr
from typing import Optional

class AccountInfoUpdate(BaseModel):
    full_name: Optional[str] = None
    # If the user wants to change their password, they must provide the current one
    current_password: Optional[str] = None
    new_password: Optional[str] = Field(None, min_length=6, max_length=72)

class SubscriptionUpgradeRequest(BaseModel):
    plan_name: str = Field(..., description="'monthly' or 'annual'")