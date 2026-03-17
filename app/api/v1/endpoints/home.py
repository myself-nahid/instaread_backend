from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, desc
from typing import Optional
from datetime import datetime

from app import models
from app.api import deps
from app.db.session import get_db

router = APIRouter()

def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    if status_code >= 400:
        status = "error"
    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "status_code": status_code,
            "message": message,
            "data": data or {}
        }
    )

def get_time_of_day_greeting():
    hour = datetime.now().hour
    if hour < 12: return "Good Morning"
    elif 12 <= hour < 17: return "Good Noon"
    elif 17 <= hour < 20: return "Good Evening"
    else: return "Good Night"

# 1. HOME DASHBOARD API
@router.get("/home")
async def get_home_dashboard(
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(models.BookScan)
        .filter(models.BookScan.owner_id == current_user.id)
        .order_by(desc(models.BookScan.scan_date))
        .limit(2)
    )
    recent_scans = result.scalars().all()
    
    history_data =[]
    for scan in recent_scans:
        highest_insight = "None"
        if scan.ai_insights:
            for category, details in scan.ai_insights.items():
                if details.get("level") in ["Mild", "High", "Moderate"]:
                    highest_insight = details.get("level")
                    break

        history_data.append({
            "id": scan.id,
            "title": scan.title,
            "author": scan.author,
            "cover_image_url": scan.cover_image_url,
            "scan_date": scan.scan_date.strftime("%b %d"),
            "scan_time": scan.scan_date.strftime("%I:%M%p"),
            "rating": scan.rating,
            "highest_insight_level": highest_insight,
            "recommended_age": scan.recommended_age or "N/A" 
        })

    first_name = current_user.full_name.split(" ")[0] if current_user.full_name else "User"

    data = {
        "greeting": f"Hello! {first_name}",
        "time_of_day": get_time_of_day_greeting(),
        "recent_history": history_data
    }
    
    return standard_response(200, "Home dashboard fetched successfully", data)

# 2. SCAN HISTORY API
@router.get("/history")
async def get_scan_history(
    search: Optional[str] = Query(None, description="Search by title or author"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(models.BookScan).filter(models.BookScan.owner_id == current_user.id)
    
    if search:
        query = query.filter(
            or_(
                models.BookScan.title.ilike(f"%{search}%"),
                models.BookScan.author.ilike(f"%{search}%")
            )
        )
        
    offset = (page - 1) * limit
    query = query.order_by(desc(models.BookScan.scan_date)).offset(offset).limit(limit)
    
    result = await db.execute(query)
    scans = result.scalars().all()
    
    history_data =[]
    for scan in scans:
        highest_insight = "None"
        if scan.ai_insights:
            for category, details in scan.ai_insights.items():
                if details.get("level") in ["Mild", "High", "Moderate"]:
                    highest_insight = details.get("level")
                    break

        history_data.append({
            "id": scan.id,
            "title": scan.title,
            "author": scan.author,
            "cover_image_url": scan.cover_image_url,
            "scan_date": scan.scan_date.strftime("%b %d"),
            "scan_time": scan.scan_date.strftime("%I:%M%p"),
            "rating": scan.rating,
            "highest_insight_level": highest_insight,
            "recommended_age": scan.recommended_age or "N/A" 
        })
        
    return standard_response(200, "Scan history fetched successfully", {
        "page": page,
        "limit": limit,
        "history": history_data
    })

# 3. SINGLE SCAN DETAILS API
@router.get("/history/{scan_id}")
async def get_scan_details(
    scan_id: int,
    current_user: models.User = Depends(deps.get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(models.BookScan)
        .filter(models.BookScan.id == scan_id, models.BookScan.owner_id == current_user.id)
    )
    scan = result.scalars().first()
    
    if not scan:
        return standard_response(404, "Scan record not found.")
        
    data = {
        "id": scan.id,
        "isbn": scan.isbn,
        "title": scan.title,
        "author": scan.author,
        "cover_image_url": scan.cover_image_url,
        "rating": scan.rating,
        "rating_score": scan.rating_score, 
        "recommended_age": scan.recommended_age or "N/A", 
        "overall_summary": f"Rated {scan.rating} : This book contains AI interpreted sensitive content.", 
        "ai_insights": scan.ai_insights 
    }
    
    return standard_response(200, "Scan details fetched successfully", data)