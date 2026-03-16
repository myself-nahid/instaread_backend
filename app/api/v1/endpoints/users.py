from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, models, schemas
from app.db.session import get_db
from app.schemas.user import UserCreate, UserUpdate

router = APIRouter()

@router.post("/", response_model=UserCreate)
async def create_user(
    *,
    db: AsyncSession = Depends(get_db),
    user_in: UserCreate,
):
    user = await crud.user.get_by_email(db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )
    user = await crud.user.create(db, obj_in=user_in)
    return user