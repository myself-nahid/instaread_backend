from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import relationship

from app.db.base import Base

class BookScan(Base):
    id = Column(Integer, primary_key=True, index=True)
    isbn = Column(String(13), index=True, nullable=False)
    title = Column(String)
    author = Column(String)
    scan_date = Column(DateTime(timezone=True), server_default=func.now())
    rating = Column(String) # "SAFE", "CAUTION", "CONCERN"
    ai_insights = Column(JSON) # Store the detailed AI report here
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    owner = relationship("User", back_populates="scans")