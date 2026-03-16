from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app import crud, models, schemas
from app.db.session import get_db
from app.services.book_scanner import book_scanner

# For a real app, you would have a dependency to get the current user from the token
# from app.api.deps import get_current_active_user

router = APIRouter()

# Mock current user for demonstration
async def get_mock_current_user():
    # In a real app, this would decode the JWT token.
    # Here we just return a mock user object.
    return models.User(id=1, email="user@example.com")


@router.post("/scan", response_model=schemas.BookScan)
async def scan_book(
    *,
    db: AsyncSession = Depends(get_db),
    isbn: str,
    current_user: models.User = Depends(get_mock_current_user) # Replace with real dependency
):
    """
    Scan a new book by its ISBN.
    """
    # 1. Fetch metadata from external APIs
    book_data = await book_scanner.fetch_book_data(isbn)
    if not book_data:
        raise HTTPException(status_code=404, detail="Book with this ISBN not found.")
        
    # 2. Call AI service for content analysis
    analysis_result = await book_scanner.analyze_content(book_data)
    
    # 3. Create BookScan entry in the database
    book_scan_in = schemas.BookScanCreate(
        isbn=isbn,
        title=book_data.get("title"),
        author=book_data.get("author")
    )
    
    created_scan = await crud.book.create_with_owner(db, obj_in=book_scan_in, owner_id=current_user.id)
    
    # 4. Update the scan with AI results (could be combined)
    created_scan.rating = analysis_result.get("rating")
    created_scan.ai_insights = analysis_result.get("ai_insights")
    db.add(created_scan)
    await db.commit()
    await db.refresh(created_scan)
    
    return created_scan


@router.get("/history", response_model=List[schemas.BookScan])
async def read_scan_history(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: models.User = Depends(get_mock_current_user) # Replace with real dependency
):
    """
    Retrieve the current user's scan history.
    """
    history = await crud.book.get_multi_by_owner(db, owner_id=current_user.id, skip=skip, limit=limit)
    return history