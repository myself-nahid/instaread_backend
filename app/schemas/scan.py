from pydantic import BaseModel, Field

class ManualScanRequest(BaseModel):
    isbn: str = Field(..., min_length=8, description="10 or 13 digit ISBN barcode")