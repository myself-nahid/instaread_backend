from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, Date, cast
from datetime import datetime, timedelta

from app import models
from app.api import deps
from app.db.session import get_db
from sqlalchemy.orm import aliased
from sqlalchemy import or_
from typing import Optional

router = APIRouter()

def standard_response(status_code: int, message: str, data: dict = None, status: str = "success"):
    if status_code >= 400:
        status = "error"
    return JSONResponse(
        status_code=status_code,
        content={"status": status, "status_code": status_code, "message": message, "data": data or {}}
    )

# Dashboard Overview
@router.get("/dashboard/overview")
async def get_dashboard_overview(
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches aggregated data for the Admin Dashboard Overview.
    Includes summary metrics, 7-day chart data, and top scanned books.
    """
    
    # 1. SUMMARY METRICS
    
    # Active Users
    active_users_result = await db.execute(select(func.count(models.User.id)).filter(models.User.is_active == True))
    total_active_users = active_users_result.scalar() or 0
    
    # Total Scans
    total_scans_result = await db.execute(select(func.count(models.BookScan.id)))
    total_scans = total_scans_result.scalar() or 0
    
    # Total Earnings (Mocked based on premium users for now, until transaction table is built)
    premium_users_result = await db.execute(select(func.count(models.User.id)).filter(models.User.subscription_plan != "free"))
    premium_users = premium_users_result.scalar() or 0
    mock_earnings = premium_users * 2.99 # Assuming monthly plan price

    # 2. CHART DATA (Last 7 Days Activity)
    today = datetime.utcnow().date()
    seven_days_ago = today - timedelta(days=6) # 7 days inclusive
    
    # Query to group scans by date and count unique users and total scans per day
    chart_query = (
        select(
            cast(models.BookScan.scan_date, Date).label('date'),
            func.count(models.BookScan.id).label('total_scans'),
            func.count(func.distinct(models.BookScan.owner_id)).label('unique_users')
        )
        .filter(models.BookScan.scan_date >= seven_days_ago)
        .group_by(cast(models.BookScan.scan_date, Date))
        .order_by(cast(models.BookScan.scan_date, Date))
    )
    
    chart_result = await db.execute(chart_query)
    chart_rows = chart_result.all()
    
    # Format chart data into a dictionary for easy date matching
    chart_data_map = {
        row.date.strftime("%b %-d"): {"total_scans": row.total_scans, "unique_users": row.unique_users} 
        for row in chart_rows
    }
    
    # Fill in missing days with 0 so the frontend chart doesn't break
    final_chart_data =[]
    for i in range(7):
        current_date = (seven_days_ago + timedelta(days=i)).strftime("%b %-d")
        if current_date in chart_data_map:
            final_chart_data.append({
                "date": current_date,
                "total_scans": chart_data_map[current_date]["total_scans"],
                "unique_users": chart_data_map[current_date]["unique_users"]
            })
        else:
            final_chart_data.append({"date": current_date, "total_scans": 0, "unique_users": 0})

    # 3. TOP SCANNED BOOKS
    top_books_query = (
        select(
            models.BookScan.title,
            models.BookScan.rating,
            func.count(models.BookScan.id).label('scan_count')
        )
        .group_by(models.BookScan.title, models.BookScan.rating)
        .order_by(desc('scan_count'))
        .limit(5)
    )
    
    top_books_result = await db.execute(top_books_query)
    top_books_rows = top_books_result.all()
    
    top_books_list =[]
    for index, row in enumerate(top_books_rows):
        top_books_list.append({
            "rank": index + 1,
            "title": row.title,
            "rating": row.rating, # e.g., "CAUTION", "CONCERN", "SAFE"
            "scans": row.scan_count
        })

    # 4. CONSTRUCT FINAL RESPONSE
    data = {
        "summary_metrics": {
            "total_earnings": {
                "value": f"${mock_earnings:,.0f}", # Formats as $12,456
                "trend": "+12% this month"         # Mocked trend
            },
            "active_users": {
                "value": f"{total_active_users:,}",
                "trend": "+8.3%"
            },
            "total_scans": {
                "value": f"{total_scans:,}",
                "trend": "+12.5%"
            }
        },
        "charts": {
            "last_7_days": final_chart_data
        },
        "top_scanned_books": top_books_list
    }

    return standard_response(200, "Dashboard overview fetched successfully", data)

# 2. BOOKS MANAGEMENT 
@router.get("/books")
async def get_books_management(
    search: Optional[str] = Query(None, description="Search by title, author, or ISBN"),
    rating_filter: Optional[str] = Query(None, alias="rating", description="Filter by 'Safe', 'Caution', or 'Concern'"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetches aggregated data and a paginated list of all book scans
    for the Admin Books Management page.
    """
    
    # 1. SUMMARY METRICS
    total_scans_result = await db.execute(select(func.count(models.BookScan.id)))
    safe_scans_result = await db.execute(select(func.count(models.BookScan.id)).filter(models.BookScan.rating == 'Safe'))
    caution_scans_result = await db.execute(select(func.count(models.BookScan.id)).filter(models.BookScan.rating == 'Caution'))
    concern_scans_result = await db.execute(select(func.count(models.BookScan.id)).filter(models.BookScan.rating == 'Concern'))
    
    summary_metrics = {
        "total_scans": total_scans_result.scalar() or 0,
        "safe": safe_scans_result.scalar() or 0,
        "caution": caution_scans_result.scalar() or 0,
        "concern": concern_scans_result.scalar() or 0
    }

    # 2. MAIN PAGINATED BOOK LIST

    # Subquery to calculate the total scan count for each unique ISBN
    scan_counts_subquery = (
        select(
            models.BookScan.isbn,
            func.count(models.BookScan.id).label('total_book_scans')
        )
        .group_by(models.BookScan.isbn)
        .subquery()
    )

    # Main query to fetch individual scans and join the total count
    main_query = (
        select(
            models.BookScan,
            scan_counts_subquery.c.total_book_scans
        )
        .join(scan_counts_subquery, models.BookScan.isbn == scan_counts_subquery.c.isbn)
    )

    # Apply search filter if provided
    if search:
        main_query = main_query.filter(
            or_(
                models.BookScan.title.ilike(f"%{search}%"),
                models.BookScan.author.ilike(f"%{search}%"),
                models.BookScan.isbn.ilike(f"%{search}%")
            )
        )

    # Apply rating dropdown filter if provided
    if rating_filter and rating_filter in ['Safe', 'Caution', 'Concern']:
        main_query = main_query.filter(models.BookScan.rating == rating_filter)

    # Get total count for pagination
    count_query = main_query.with_only_columns(func.count(models.BookScan.id))
    total_items_result = await db.execute(count_query)
    total_items = total_items_result.scalar() or 0

    # Apply sorting and pagination
    offset = (page - 1) * limit
    main_query = main_query.order_by(desc(models.BookScan.scan_date)).offset(offset).limit(limit)
    
    # Execute and fetch all results
    query_result = await db.execute(main_query)
    all_rows = query_result.all()

    book_list =[]
    for row in all_rows:
        scan_record = row[0]
        total_book_scans = row[1]
        
        book_list.append({
            "id": scan_record.id,
            "title": scan_record.title,
            "author": scan_record.author,
            "cover_image_url": scan_record.cover_image_url,
            "isbn": scan_record.isbn,
            "rating": scan_record.rating,
            "scans": total_book_scans,
            "cached": "Yes" # Every item in our DB is cached
        })
        
    data = {
        "summary_metrics": summary_metrics,
        "pagination": {
            "total_items": total_items,
            "total_pages": (total_items + limit - 1) // limit,
            "current_page": page,
            "limit": limit
        },
        "books": book_list
    }

    return standard_response(200, "Books management data fetched successfully", data)

# 3. DELETE A BOOK SCAN ENTRY
@router.delete("/books/{scan_id}")
async def delete_book_scan(
    scan_id: int,
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Deletes a specific book scan entry from the database."""
    
    result = await db.execute(select(models.BookScan).filter(models.BookScan.id == scan_id))
    scan_to_delete = result.scalars().first()
    
    if not scan_to_delete:
        return standard_response(404, "Scan record not found.")
        
    await db.delete(scan_to_delete)
    await db.commit()
    
    return standard_response(200, f"Scan record ID {scan_id} has been deleted successfully.")

# 4. USERS MANAGEMENT
@router.get("/users")
async def get_users_management(
    search: Optional[str] = Query(None, description="Search by user name or email"),
    subscription: Optional[str] = Query(None, description="Filter by 'Premium' or 'Free'"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches aggregated metrics and a paginated list of users for the Admin Users Management page."""
    
    # 1. SUMMARY METRICS
    total_users_result = await db.execute(select(func.count(models.User.id)))
    premium_users_result = await db.execute(select(func.count(models.User.id)).filter(models.User.subscription_plan != 'free'))
    
    # New users this week
    one_week_ago = datetime.utcnow() - timedelta(days=7)
    new_users_result = await db.execute(select(func.count(models.User.id)).filter(models.User.join_date >= one_week_ago))

    summary_metrics = {
        "total_users": total_users_result.scalar() or 0,
        "premium_users": premium_users_result.scalar() or 0,
        "new_this_week": new_users_result.scalar() or 0
    }

    # 2. MAIN PAGINATED USER LIST

    # Subquery to count scans for each user
    scan_counts_subquery = (
        select(
            models.BookScan.owner_id,
            func.count(models.BookScan.id).label('total_user_scans')
        )
        .group_by(models.BookScan.owner_id)
        .subquery()
    )
    
    # Main query for users, joining the scan counts
    main_query = (
        select(
            models.User,
            func.coalesce(scan_counts_subquery.c.total_user_scans, 0).label('total_scans')
        )
        .outerjoin(scan_counts_subquery, models.User.id == scan_counts_subquery.c.owner_id)
    )

    # Apply search filter
    if search:
        main_query = main_query.filter(
            or_(
                models.User.full_name.ilike(f"%{search}%"),
                models.User.email.ilike(f"%{search}%")
            )
        )

    # Apply subscription dropdown filter
    if subscription:
        if subscription.lower() == 'premium':
            main_query = main_query.filter(models.User.subscription_plan != 'free')
        elif subscription.lower() == 'free':
            main_query = main_query.filter(models.User.subscription_plan == 'free')

    # Get total count for pagination before applying limit/offset
    count_query = main_query.with_only_columns(func.count(models.User.id))
    total_items_result = await db.execute(count_query)
    total_items = total_items_result.scalar() or 0
    
    # Apply sorting and pagination
    offset = (page - 1) * limit
    main_query = main_query.order_by(desc(models.User.join_date)).offset(offset).limit(limit)

    query_result = await db.execute(main_query)
    all_rows = query_result.all()

    user_list = []
    for row in all_rows:
        user_record = row[0]
        total_user_scans = row[1]
        
        user_list.append({
            "id": user_record.id,
            "name": user_record.full_name,
            "email": user_record.email,
            "profile_picture_url": user_record.profile_picture_url,
            "join_date": user_record.join_date.strftime("%-m/%-d/%Y"),
            "total_scans": total_user_scans,
            "subscription": user_record.subscription_plan.capitalize(),
            "status": "Active" if user_record.is_active else "Inactive"
        })

    data = {
        "summary_metrics": summary_metrics,
        "pagination": {
            "total_items": total_items,
            "total_pages": (total_items + limit - 1) // limit,
            "current_page": page,
            "limit": limit
        },
        "users": user_list
    }

    return standard_response(200, "Users management data fetched successfully", data)

# 5. GET USER DETAILS & SCAN HISTORY (For Modal)
@router.get("/users/{user_id}")
async def get_user_details(
    user_id: int,
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches a specific user's details and their entire scan history."""
    
    # Fetch user details
    user_result = await db.execute(select(models.User).filter(models.User.id == user_id))
    user = user_result.scalars().first()
    
    if not user:
        return standard_response(404, "User not found.")
        
    # Fetch user's scan history
    history_result = await db.execute(
        select(models.BookScan)
        .filter(models.BookScan.owner_id == user_id)
        .order_by(desc(models.BookScan.scan_date))
    )
    scan_history = history_result.scalars().all()

    user_details = {
        "id": user.id,
        "name": user.full_name,
        "email": user.email,
        "profile_picture_url": user.profile_picture_url,
        "location": "Overland Park, KS", # Mocked location as it's not in the DB model
        "join_date": user.join_date.strftime("%d %b, %Y")
    }

    service_provided = []
    for scan in scan_history:
        service_provided.append({
            "id": scan.id,
            "title": scan.title,
            "author": scan.author,
            "cover_image_url": scan.cover_image_url,
            "rating": scan.rating
        })

    return standard_response(200, "User details fetched successfully", data={
        "user_details": user_details,
        "service_provided": service_provided
    })

# 6. DELETE A USER
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Deletes a user and all their associated data (e.g., scans)."""
    
    result = await db.execute(select(models.User).filter(models.User.id == user_id))
    user_to_delete = result.scalars().first()
    
    if not user_to_delete:
        return standard_response(404, "User not found.")
    
    # The 'cascade' setting in the User model's relationship will auto-delete their scans.
    await db.delete(user_to_delete)
    await db.commit()
    
    return standard_response(200, f"User {user_to_delete.email} has been deleted successfully.")

# 7. TRANSACTION MANAGEMENT 
@router.get("/transactions")
async def get_transactions_management(
    search: Optional[str] = Query(None, description="Search by user name, email, or ISBN in their scans"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches aggregated metrics and a paginated list of user transactions."""
    
    # 1. SUMMARY METRICS 
    total_earnings_result = await db.execute(select(func.sum(models.Transaction.amount)))
    total_subscriptions_result = await db.execute(select(func.count(models.User.id)).filter(models.User.subscription_plan != 'free'))
    active_users_result = await db.execute(select(func.count(models.User.id)).filter(models.User.is_active == True))

    summary_metrics = {
        "total_earnings": total_earnings_result.scalar() or 0.0,
        "total_subscriptions": total_subscriptions_result.scalar() or 0,
        "active_users": active_users_result.scalar() or 0,
    }

    # 2. MAIN PAGINATED TRANSACTION LIST

    # Subquery to count scans for each user
    scan_counts_subquery = (
        select(models.BookScan.owner_id, func.count(models.BookScan.id).label('total_user_scans'))
        .group_by(models.BookScan.owner_id).subquery()
    )
    
    # Subquery to find the most recent transaction provider for each user
    latest_transaction_subquery = (
        select(
            models.Transaction.user_id,
            models.Transaction.provider
        )
        .distinct(models.Transaction.user_id)
        .order_by(models.Transaction.user_id, desc(models.Transaction.transaction_date))
        .subquery()
    )

    main_query = (
        select(
            models.User,
            func.coalesce(scan_counts_subquery.c.total_user_scans, 0).label('total_scans'),
            latest_transaction_subquery.c.provider.label('transaction_provider')
        )
        .outerjoin(scan_counts_subquery, models.User.id == scan_counts_subquery.c.owner_id)
        .outerjoin(latest_transaction_subquery, models.User.id == latest_transaction_subquery.c.user_id)
    )

    # Apply search filter
    if search:
        main_query = main_query.filter(
            or_(
                models.User.full_name.ilike(f"%{search}%"),
                models.User.email.ilike(f"%{search}%")
            )
        )

    # Get total count for pagination
    count_query = main_query.with_only_columns(func.count(models.User.id))
    total_items_result = await db.execute(count_query)
    total_items = total_items_result.scalar() or 0

    # Apply sorting and pagination
    offset = (page - 1) * limit
    main_query = main_query.order_by(desc(models.User.last_active)).offset(offset).limit(limit)

    query_result = await db.execute(main_query)
    all_rows = query_result.all()

    transaction_list = []
    for row in all_rows:
        user_record, total_user_scans, provider = row
        transaction_list.append({
            "user_id": user_record.id,
            "name": user_record.full_name,
            "email": user_record.email,
            "profile_picture_url": user_record.profile_picture_url,
            "join_date": user_record.join_date.strftime("%-m/%-d/%Y"),
            "total_scans": total_user_scans,
            "last_active": user_record.last_active.strftime("%-m/%-d/%Y"),
            "transaction_provider": provider or "N/A"
        })

    data = {
        "summary_metrics": summary_metrics,
        "pagination": {
            "total_items": total_items,
            "total_pages": (total_items + limit - 1) // limit,
            "current_page": page,
            "limit": limit
        },
        "transactions": transaction_list
    }

    return standard_response(200, "Transaction data fetched successfully", data)