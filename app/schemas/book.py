from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class BookScanBase(BaseModel):
    isbn: str
    title: Optional[str] = None
    author: Optional[str] = None

class BookScanCreate(BookScanBase):
    pass

class BookScanUpdate(BookScanBase):
    pass

class BookScanInDBBase(BookScanBase):
    id: int
    owner_id: int
    scan_date: datetime
    rating: Optional[str] = None
    ai_insights: Optional[Dict[str, Any]] = None

    class Config:
        orm_mode = True

class BookScan(BookScanInDBBase):
    pass