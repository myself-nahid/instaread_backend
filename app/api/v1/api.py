from fastapi import APIRouter

from app.api.v1.endpoints import admin, auth, home, payment, settings, users, books, scan

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(books.router, prefix="/books", tags=["books"])
api_router.include_router(scan.router, prefix="/scan", tags=["scan"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(home.router, tags=["home_and_history"])
api_router.include_router(payment.router, prefix="/payment", tags=["payment"])
api_router.include_router(payment.router, tags=["payment"])