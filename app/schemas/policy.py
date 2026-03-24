from pydantic import BaseModel
from typing import Optional

class PolicyBase(BaseModel):
    title: str
    description: str

class PolicyCreate(PolicyBase):
    pass

class PolicyUpdate(PolicyBase):
    title: Optional[str] = None
    description: Optional[str] = None