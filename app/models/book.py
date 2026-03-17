from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import relationship
from app.db.base import Base

class BookScan(Base):
    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String(13), index=True, nullable=False)
    title = Column(String)
    author = Column(String)
    cover_image_url = Column(String, nullable=True) # Added for UI
    scan_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # "Safe", "Caution", "Concern"
    rating = Column(String) 
    # e.g., 59 (for 59%)
    rating_score = Column(Integer, nullable=True)
    recommended_age = Column(String, nullable=True) # e.g., "10+"
    
    # JSON containing categories: violence, profanity, sexual_content, gender_identity
    # Each with a "level" (Mild, None, High) and "description"
    ai_insights = Column(JSON) 
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="scans")