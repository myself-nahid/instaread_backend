from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from app import db, models
from app.api import deps
from app.db.session import get_db
from app.schemas.scan import ManualScanRequest
from app.services.ai_client import ai_client

router = APIRouter()

def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    if status_code >= 400:
        status = "error"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "status_code": status_code, "message": message, "data": data or {}}
    )

async def check_scan_limits(current_user: models.User, db: AsyncSession):
    """Checks if the user has reached their scan limit based on the Free Plan UI."""
    if current_user.subscription_plan == "free":
        # Count user's total scans
        result = await db.execute(
            select(func.count(models.BookScan.id)).filter(models.BookScan.owner_id == current_user.id)
        )
        total_scans = result.scalar()
        
        # strictly says "You've reached your 100 free scans."
        if total_scans >= 100:
            raise HTTPException(
                status_code=403, 
                detail="You've reached your 100 free scans. Upgrade to continue scanning."
            )

async def save_scan_to_db(user_id: int, ai_data: dict, db: AsyncSession, original_isbn: str = None):
    """Saves the AI result to the database by safely mapping the AI Developer's specific JSON structure."""

    print("AI Data Received:", ai_data)  
    
    overall_score = ai_data.get("overall_score", {})
    raw_isbn = ai_data.get("detected_isbn") or ai_data.get("isbn") or original_isbn or "Unknown"
    
    # Remove any accidental spaces, and slice it [:13]
    safe_isbn = str(raw_isbn).strip()[:13]

    new_scan = models.BookScan(
        owner_id=user_id,
        
        # The AI didn't return an ISBN in their JSON! 
        # So we MUST use the 'original_isbn' that the user typed into the app.
        isbn=safe_isbn,
        
        # Exact match
        title=ai_data.get("title", "Unknown Title"),
        
        # Map AI's "authors" to DB's "author"
        author=ai_data.get("authors", "Unknown Author"),
        
        # Map AI's "cover_image" to DB's "cover_image_url"
        cover_image_url=ai_data.get("cover_image"),
        
        # Map AI's nested "text" (e.g., "Caution") to DB's "rating"
        rating=overall_score.get("text", "Pending"),
        
        # Map AI's nested "percentage" (e.g., 59) to DB's "rating_score"
        rating_score=overall_score.get("percentage"),
        
        # Map AI's "age_recommendation" to DB's "recommended_age"
        recommended_age=ai_data.get("age_recommendation", "N/A"),
        
        # The insights block matches perfectly
        ai_insights=ai_data.get("ai_insights", {})
    )
    
    db.add(new_scan)
    await db.commit()
    await db.refresh(new_scan)
    
    return new_scan

# 1. SCAN BARCODE IMAGE (Camera Upload)
@router.post("/image")
async def scan_barcode_image(
    file: UploadFile = File(...),
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check Limits First
    await check_scan_limits(current_user, db)
    
    # 2. Read image bytes
    image_bytes = await file.read()
    
    ai_result = await ai_client.analyze_barcode_image(image_bytes)
    saved_scan = await save_scan_to_db(current_user.id, ai_result, db, original_isbn="Unknown")
    
    # 5. Return structured data to the mobile app
    return standard_response(200, "Book successfully analyzed.", {
        "scan_id": saved_scan.id,
        "analysis": ai_result
    })

# 2. SCAN MANUAL ISBN
@router.post("/isbn")
async def scan_manual_isbn(
    payload: ManualScanRequest,
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check Limits First
    await check_scan_limits(current_user, db)
    
    ai_result = await ai_client.analyze_manual_isbn(payload.isbn)
    saved_scan = await save_scan_to_db(current_user.id, ai_result, db, original_isbn=payload.isbn)
    
    # 4. Return structured data
    return standard_response(200, "Book successfully analyzed.", {
        "scan_id": saved_scan.id,
        "analysis": ai_result
    })