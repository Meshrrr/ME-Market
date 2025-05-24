import uuid
from typing import List, Optional

from sqlalchemy import select
from database.database import async_session_maker
from database.models import UserInventory

async def get_user_inventory(user_id: uuid.UUID, ticker: Optional[str] = None) -> List[UserInventory]:
    async with async_session_maker() as session:
        q = select(UserInventory).where(UserInventory.user_id == user_id)
        if ticker:
            q = select(UserInventory).where(UserInventory.user_id == user_id, UserInventory.instrument_ticker == ticker)
        result = await session.execute(q)

        return result.scalars().all()