from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, func
from sqlalchemy.orm import relationship
from app.db.base import Base

class Transaction(Base):
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    transaction_date = Column(DateTime(timezone=True), server_default=func.now())
    amount = Column(Float, nullable=False)
    provider = Column(String) # "Stripe", "PayPal", etc.
    status = Column(String, default="Completed")
    
    user = relationship("User")