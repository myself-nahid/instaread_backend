from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base

class User(Base):
    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    profile_picture_url = Column(String, nullable=True)
    
    # OTP and Verification Fields
    is_verified = Column(Boolean, default=False)
    otp = Column(String(6), nullable=True)
    otp_expire_at = Column(DateTime(timezone=True), nullable=True)
    
    join_date = Column(DateTime(timezone=True), server_default=func.now())
    last_active = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    subscription_plan = Column(String, default="free")
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    scans = relationship("BookScan", back_populates="owner", cascade="all, delete-orphan")