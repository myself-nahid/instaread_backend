from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship

from app.db.base import Base

class User(Base):
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    join_date = Column(DateTime(timezone=True), server_default=func.now())
    subscription_plan = Column(String, default="free") # e.g., "free", "monthly", "annual"
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    scans = relationship("BookScan", back_populates="owner", cascade="all, delete-orphan")