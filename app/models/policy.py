from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.db.base import Base

class Policy(Base):
    id = Column(Integer, primary_key=True, index=True)
    # The slug will be our public identifier, e.g., "privacy-policy"
    slug = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())