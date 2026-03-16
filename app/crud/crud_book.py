from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.book import BookScan
from app.schemas.book import BookScanCreate

class CRUDBook:
    async def get_multi_by_owner(
        self, db: AsyncSession, *, owner_id: int, skip: int = 0, limit: int = 100
    ) -> List[BookScan]:
        result = await db.execute(
            select(BookScan)
            .filter(BookScan.owner_id == owner_id)
            .offset(skip)
            .limit(limit)
            .order_by(BookScan.scan_date.desc())
        )
        return result.scalars().all()

    async def create_with_owner(
        self, db: AsyncSession, *, obj_in: BookScanCreate, owner_id: int
    ) -> BookScan:
        db_obj = BookScan(**obj_in.dict(), owner_id=owner_id)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

book = CRUDBook()