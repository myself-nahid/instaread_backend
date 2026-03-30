from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc, Date, cast
from datetime import datetime, timedelta
from app.schemas import policy as policy_schemas

from app import models
from app.api import deps
from app.db.session import get_db
from sqlalchemy.orm import aliased
from sqlalchemy import or_
from typing import Optional
import re

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
    Includes summary metrics, 7-day chart data, and top scanned books with trends.
    """

    # 1. TIME RANGES
    now = datetime.utcnow()
    today = now.date()

    current_start = today - timedelta(days=6)
    previous_start = today - timedelta(days=13)
    previous_end = today - timedelta(days=7)

    # 2. TREND FUNCTION (3 DIRECTIONS)
    def calculate_trend_with_direction(current, previous):
        if previous == 0:
            if current > 0:
                return 100, "up"
            return 0, "neutral"

        percentage = round(((current - previous) / previous) * 100, 2)

        if percentage > 0:
            direction = "up"
        elif percentage < 0:
            direction = "down"
        else:
            direction = "neutral"

        return percentage, direction

    # 3. ACTIVE USERS
    current_active_users_result = await db.execute(
        select(func.count(models.User.id)).filter(
            models.User.is_active == True,
            models.User.last_active >= current_start
        )
    )

    previous_active_users_result = await db.execute(
        select(func.count(models.User.id)).filter(
            models.User.is_active == True,
            models.User.last_active.between(previous_start, previous_end)
        )
    )

    current_active_users = current_active_users_result.scalar() or 0
    previous_active_users = previous_active_users_result.scalar() or 0

    active_trend, active_direction = calculate_trend_with_direction(
        current_active_users, previous_active_users
    )

    # 4. TOTAL SCANS
    current_scans_result = await db.execute(
        select(func.count(models.BookScan.id)).filter(
            models.BookScan.scan_date >= current_start
        )
    )

    previous_scans_result = await db.execute(
        select(func.count(models.BookScan.id)).filter(
            models.BookScan.scan_date.between(previous_start, previous_end)
        )
    )

    current_scans = current_scans_result.scalar() or 0
    previous_scans = previous_scans_result.scalar() or 0

    scans_trend, scans_direction = calculate_trend_with_direction(
        current_scans, previous_scans
    )

    # 5. TOTAL EARNINGS (MOCK BASED ON PREMIUM USERS)
    current_premium_users_result = await db.execute(
        select(func.count(models.User.id)).filter(
            models.User.subscription_plan != "free"
        )
    )

    previous_premium_users_result = await db.execute(
        select(func.count(models.User.id)).filter(
            models.User.subscription_plan != "free",
            models.User.join_date < current_start
        )
    )

    current_premium_users = current_premium_users_result.scalar() or 0
    previous_premium_users = previous_premium_users_result.scalar() or 0

    current_earnings = current_premium_users * 2.99
    previous_earnings = previous_premium_users * 2.99

    earnings_trend, earnings_direction = calculate_trend_with_direction(
        current_earnings, previous_earnings
    )

    # 6. CHART DATA (LAST 7 DAYS)
    chart_query = (
        select(
            cast(models.BookScan.scan_date, Date).label('date'),
            func.count(models.BookScan.id).label('total_scans'),
            func.count(func.distinct(models.BookScan.owner_id)).label('unique_users')
        )
        .filter(models.BookScan.scan_date >= current_start)
        .group_by(cast(models.BookScan.scan_date, Date))
        .order_by(cast(models.BookScan.scan_date, Date))
    )

    chart_result = await db.execute(chart_query)
    chart_rows = chart_result.all()

    chart_data_map = {
        row.date.strftime("%b %-d"): {
            "total_scans": row.total_scans,
            "unique_users": row.unique_users
        }
        for row in chart_rows
    }

    final_chart_data = []
    for i in range(7):
        date_str = (current_start + timedelta(days=i)).strftime("%b %-d")
        if date_str in chart_data_map:
            final_chart_data.append({
                "date": date_str,
                "total_scans": chart_data_map[date_str]["total_scans"],
                "unique_users": chart_data_map[date_str]["unique_users"]
            })
        else:
            final_chart_data.append({
                "date": date_str,
                "total_scans": 0,
                "unique_users": 0
            })

    # 7. TOP SCANNED BOOKS
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

    top_books_list = []
    for index, row in enumerate(top_books_rows):
        top_books_list.append({
            "rank": index + 1,
            "title": row.title,
            "rating": row.rating,
            "scans": row.scan_count
        })

    # 8. FINAL RESPONSE
    data = {
        "summary_metrics": {
            "total_earnings": {
                "value": f"${current_earnings:,.0f}",
                "trend_percentage": earnings_trend,
                "trend_direction": earnings_direction
            },
            "active_users": {
                "value": f"{current_active_users:,}",
                "trend_percentage": active_trend,
                "trend_direction": active_direction
            },
            "total_scans": {
                "value": f"{current_scans:,}",
                "trend_percentage": scans_trend,
                "trend_direction": scans_direction
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

# User Management
@router.get("/users")
async def get_users_management(
    search: Optional[str] = Query(None, description="Search by user name or email"),
    subscription: Optional[str] = Query(None, description="Filter by 'Premium' or 'Free'"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches aggregated metrics and a paginated list of non-admin users with trends."""

    # 1. TIME RANGES
    now = datetime.utcnow()
    one_week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # 2. TREND FUNCTION (3 DIRECTIONS)
    def calculate_trend_with_direction(current, previous):
        if previous == 0:
            if current > 0:
                return 100, "up"
            return 0, "neutral"

        percentage = round(((current - previous) / previous) * 100, 2)

        if percentage > 0:
            direction = "up"
        elif percentage < 0:
            direction = "down"
        else:
            direction = "neutral"

        return percentage, direction

    # 3. TOTAL USERS
    current_total_users = await db.execute(
        select(func.count(models.User.id))
        .filter(models.User.is_superuser == False)
    )

    previous_total_users = await db.execute(
        select(func.count(models.User.id))
        .filter(
            models.User.join_date < one_week_ago,
            models.User.is_superuser == False
        )
    )

    current_total = current_total_users.scalar() or 0
    previous_total = previous_total_users.scalar() or 0

    total_trend, total_direction = calculate_trend_with_direction(current_total, previous_total)

    # 4. PREMIUM USERS
    current_premium_users = await db.execute(
        select(func.count(models.User.id))
        .filter(
            models.User.subscription_plan != 'free',
            models.User.is_superuser == False
        )
    )

    previous_premium_users = await db.execute(
        select(func.count(models.User.id))
        .filter(
            models.User.subscription_plan != 'free',
            models.User.join_date < one_week_ago,
            models.User.is_superuser == False
        )
    )

    current_premium = current_premium_users.scalar() or 0
    previous_premium = previous_premium_users.scalar() or 0

    premium_trend, premium_direction = calculate_trend_with_direction(current_premium, previous_premium)

    # 5. NEW USERS (THIS WEEK vs LAST WEEK)
    current_new_users = await db.execute(
        select(func.count(models.User.id))
        .filter(
            models.User.join_date >= one_week_ago,
            models.User.is_superuser == False
        )
    )

    previous_new_users = await db.execute(
        select(func.count(models.User.id))
        .filter(
            models.User.join_date >= two_weeks_ago,
            models.User.join_date < one_week_ago,
            models.User.is_superuser == False
        )
    )

    current_new = current_new_users.scalar() or 0
    previous_new = previous_new_users.scalar() or 0

    new_trend, new_direction = calculate_trend_with_direction(current_new, previous_new)

    # 6. SUMMARY METRICS WITH 3 TREND DIRECTIONS
    summary_metrics = {
        "total_users": {
            "value": current_total,
            "previous": previous_total,
            "trend_percentage": total_trend,
            "trend_direction": total_direction
        },
        "premium_users": {
            "value": current_premium,
            "previous": previous_premium,
            "trend_percentage": premium_trend,
            "trend_direction": premium_direction
        },
        "new_this_week": {
            "value": current_new,
            "previous": previous_new,
            "trend_percentage": new_trend,
            "trend_direction": new_direction
        }
    }

    # 7. USER LIST
    scan_counts_subquery = (
        select(models.BookScan.owner_id, func.count(models.BookScan.id).label('total_user_scans'))
        .group_by(models.BookScan.owner_id)
        .subquery()
    )
    
    main_query = (
        select(
            models.User,
            func.coalesce(scan_counts_subquery.c.total_user_scans, 0).label('total_scans')
        )
        .outerjoin(scan_counts_subquery, models.User.id == scan_counts_subquery.c.owner_id)
        .filter(models.User.is_superuser == False)
    )

    if search:
        main_query = main_query.filter(
            or_(
                models.User.full_name.ilike(f"%{search}%"),
                models.User.email.ilike(f"%{search}%")
            )
        )

    if subscription:
        if subscription.lower() == 'premium':
            main_query = main_query.filter(models.User.subscription_plan != 'free')
        elif subscription.lower() == 'free':
            main_query = main_query.filter(models.User.subscription_plan == 'free')

    count_query = main_query.with_only_columns(func.count(models.User.id))
    total_items = (await db.execute(count_query)).scalar() or 0
    
    offset = (page - 1) * limit
    main_query = main_query.order_by(desc(models.User.join_date)).offset(offset).limit(limit)

    result = await db.execute(main_query)
    rows = result.all()

    user_list = []
    for user_record, total_scans in rows:
        user_list.append({
            "id": user_record.id,
            "name": user_record.full_name,
            "email": user_record.email,
            "profile_picture_url": user_record.profile_picture_url,
            "join_date": user_record.join_date.strftime("%-m/%-d/%Y"),
            "total_scans": total_scans,
            "subscription": user_record.subscription_plan.capitalize(),
            "status": "Active" if user_record.is_active else "Inactive"
        })

    # 8. FINAL RESPONSE
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

# transactions management
@router.get("/transactions")
async def get_transactions_management(
    search: Optional[str] = Query(None, description="Search by user name or email"),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches aggregated metrics with trend directions and a paginated list of subscribed user transactions."""

    # 1. TIME RANGES
    now = datetime.utcnow()
    one_week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # 2. TREND FUNCTION (3 DIRECTIONS)
    def calculate_trend_with_direction(current, previous):
        if previous == 0:
            if current > 0:
                return 100, "up"
            return 0, "neutral"
        
        percentage = round(((current - previous) / previous) * 100, 2)

        if percentage > 0:
            direction = "up"
        elif percentage < 0:
            direction = "down"
        else:
            direction = "neutral"

        return percentage, direction

    # 3. TOTAL EARNINGS
    current_earnings_result = await db.execute(
        select(func.coalesce(func.sum(models.Transaction.amount), 0.0))
        .join(models.User)
        .filter(
            models.User.is_superuser == False,
            models.Transaction.transaction_date >= one_week_ago
        )
    )

    previous_earnings_result = await db.execute(
        select(func.coalesce(func.sum(models.Transaction.amount), 0.0))
        .join(models.User)
        .filter(
            models.User.is_superuser == False,
            models.Transaction.transaction_date.between(two_weeks_ago, one_week_ago)
        )
    )

    current_earnings = current_earnings_result.scalar() or 0.0
    previous_earnings = previous_earnings_result.scalar() or 0.0

    earnings_trend, earnings_direction = calculate_trend_with_direction(
        current_earnings, previous_earnings
    )

    # 4. TOTAL SUBSCRIPTIONS
    current_subscriptions_result = await db.execute(
        select(func.count(models.User.id)).filter(
            models.User.subscription_plan != 'free',
            models.User.is_superuser == False
        )
    )

    previous_subscriptions_result = await db.execute(
        select(func.count(models.User.id)).filter(
            models.User.subscription_plan != 'free',
            models.User.join_date < one_week_ago,
            models.User.is_superuser == False
        )
    )

    current_subscriptions = current_subscriptions_result.scalar() or 0
    previous_subscriptions = previous_subscriptions_result.scalar() or 0

    subs_trend, subs_direction = calculate_trend_with_direction(
        current_subscriptions, previous_subscriptions
    )

    # 5. ACTIVE USERS
    current_active_users_result = await db.execute(
        select(func.count(models.User.id)).filter(
            models.User.is_active == True,
            models.User.last_active >= one_week_ago,
            models.User.is_superuser == False
        )
    )

    previous_active_users_result = await db.execute(
        select(func.count(models.User.id)).filter(
            models.User.is_active == True,
            models.User.last_active.between(two_weeks_ago, one_week_ago),
            models.User.is_superuser == False
        )
    )

    current_active_users = current_active_users_result.scalar() or 0
    previous_active_users = previous_active_users_result.scalar() or 0

    active_trend, active_direction = calculate_trend_with_direction(
        current_active_users, previous_active_users
    )

    # 6. SUMMARY METRICS
    summary_metrics = {
        "total_earnings": {
            "value": f"${current_earnings:,.2f}",
            "trend_percentage": earnings_trend,
            "trend_direction": earnings_direction
        },
        "total_subscriptions": {
            "value": f"{current_subscriptions:,}",
            "trend_percentage": subs_trend,
            "trend_direction": subs_direction
        },
        "active_users": {
            "value": f"{current_active_users:,}",
            "trend_percentage": active_trend,
            "trend_direction": active_direction
        }
    }

    # 7. TRANSACTION LIST (ONLY USERS WITH TRANSACTIONS)
    scan_counts_subquery = (
        select(models.BookScan.owner_id, func.count(models.BookScan.id).label('total_user_scans'))
        .group_by(models.BookScan.owner_id)
        .subquery()
    )

    latest_transaction_subquery = (
        select(
            models.Transaction.user_id,
            models.Transaction.provider,
            models.Transaction.transaction_date
        )
        .distinct(models.Transaction.user_id)
        .order_by(models.Transaction.user_id, desc(models.Transaction.transaction_date))
        .subquery()
    )

    main_query = (
        select(
            models.User,
            func.coalesce(scan_counts_subquery.c.total_user_scans, 0).label('total_scans'),
            latest_transaction_subquery.c.provider,
            latest_transaction_subquery.c.transaction_date
        )
        .join(latest_transaction_subquery, models.User.id == latest_transaction_subquery.c.user_id)
        .outerjoin(scan_counts_subquery, models.User.id == scan_counts_subquery.c.owner_id)
        .filter(models.User.is_superuser == False)
    )

    if search:
        main_query = main_query.filter(
            or_(
                models.User.full_name.ilike(f"%{search}%"),
                models.User.email.ilike(f"%{search}%")
            )
        )

    count_query = main_query.with_only_columns(func.count(models.User.id))
    total_items = (await db.execute(count_query)).scalar() or 0

    offset = (page - 1) * limit
    main_query = main_query.order_by(desc(models.User.last_active)).offset(offset).limit(limit)

    result = await db.execute(main_query)
    rows = result.all()

    transaction_list = []
    for user, total_scans, provider, txn_date in rows:
        transaction_list.append({
            "user_id": user.id,
            "transaction_id": f"TXN{user.id:06d}",
            "name": user.full_name,
            "email": user.email,
            "transaction_date": txn_date.strftime("%-m/%-d/%Y") if txn_date else None,
            "transaction_provider": provider or "N/A"
        })

    # 8. FINAL RESPONSE
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

# slug generator 
def generate_slug(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    s = re.sub(r'^-+|-+$', '', s)
    return s

# POLICY MANAGEMENT (GET + PATCH ONLY)
@router.get("/policies")
async def get_policies(
    policy_slug: Optional[str] = None,
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    GET:
    - All policies (if no slug)
    - Single policy (if slug provided)
    """

    if policy_slug:
        result = await db.execute(
            select(models.Policy).filter(models.Policy.slug == policy_slug)
        )
        policy = result.scalars().first()

        if not policy:
            return standard_response(404, "Policy not found.")

        return standard_response(200, "Policy fetched successfully", {
            "slug": policy.slug,
            "title": policy.title,
            "description": policy.description
        })

    # Get all policies
    result = await db.execute(select(models.Policy).order_by(models.Policy.id))
    policies = result.scalars().all()

    policy_list = [
        {
            "slug": p.slug,
            "title": p.title,
            "description": p.description
        }
        for p in policies
    ]

    return standard_response(200, "Policies fetched successfully", {
        "policies": policy_list
    })


@router.patch("/policies/{policy_slug}")
async def upsert_policy(
    policy_slug: str,
    payload: policy_schemas.PolicyCreate,  
    current_admin: models.User = Depends(deps.get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """
    PATCH:
    - Update existing policy
    - Create new policy if not exists (UPSERT)
    """

    result = await db.execute(
        select(models.Policy).filter(models.Policy.slug == policy_slug)
    )
    policy = result.scalars().first()

    # If NOT exists → CREATE
    if not policy:
        slug = generate_slug(payload.title)

        # Prevent duplicate slug
        existing = await db.execute(
            select(models.Policy).filter(models.Policy.slug == slug)
        )
        if existing.scalars().first():
            return standard_response(400, "Policy with this title already exists.")

        new_policy = models.Policy(
            slug=slug,
            title=payload.title,
            description=payload.description
        )

        db.add(new_policy)
        await db.commit()
        await db.refresh(new_policy)

        return standard_response(201, "Policy created successfully", {
            "slug": new_policy.slug,
            "title": new_policy.title,
            "description": new_policy.description
        })

    # If exists → UPDATE
    update_data = payload.dict(exclude_unset=True)

    # If title updated → regenerate slug
    if "title" in update_data:
        new_slug = generate_slug(update_data["title"])
        policy.slug = new_slug

    for key, value in update_data.items():
        setattr(policy, key, value)

    await db.commit()
    await db.refresh(policy)

    return standard_response(200, "Policy updated successfully", {
        "slug": policy.slug,
        "title": policy.title,
        "description": policy.description
    })