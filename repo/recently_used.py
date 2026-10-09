from collections.abc import Sequence
from typing import cast

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.recently_used import RecentlyUsed
from db.models.sticker import Sticker


class RecentlyUsedRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, uid: int, sticker_unique_id: str) -> RecentlyUsed | None:
        stmt = select(RecentlyUsed).where(RecentlyUsed.uid == uid, RecentlyUsed.sticker_unique_id == sticker_unique_id)
        return cast(RecentlyUsed | None, await self._session.scalar(stmt))

    # 只返回贴纸仍然存在的历史记录, 按使用时间升序
    async def list_existing(self, uid: int) -> Sequence[RecentlyUsed]:
        stmt = (
            select(RecentlyUsed)
            .join(
                Sticker,
                (Sticker.uid == RecentlyUsed.uid) & (Sticker.sticker_unique_id == RecentlyUsed.sticker_unique_id),
            )
            .where(RecentlyUsed.uid == uid)
            .order_by(RecentlyUsed.time.asc())
        )
        result = await self._session.scalars(stmt)
        return result.all()

    async def add(self, record: RecentlyUsed) -> RecentlyUsed:
        self._session.add(record)
        await self._session.flush()
        return record

    async def remove_by_unique_ids(self, uid: int, sticker_unique_ids: Sequence[str]) -> None:
        if not sticker_unique_ids:
            return
        stmt = delete(RecentlyUsed).where(
            RecentlyUsed.uid == uid, RecentlyUsed.sticker_unique_id.in_(sticker_unique_ids)
        )
        await self._session.execute(stmt)

    async def remove_by_uid(self, uid: int) -> None:
        stmt = delete(RecentlyUsed).where(RecentlyUsed.uid == uid)
        await self._session.execute(stmt)

    # 只保留最新的 keep 条
    async def trim(self, uid: int, keep: int = 19) -> None:
        stmt = select(RecentlyUsed.id).where(RecentlyUsed.uid == uid).order_by(RecentlyUsed.time.desc()).offset(keep)
        result = await self._session.scalars(stmt)
        ids = result.all()
        if not ids:
            return
        await self._session.execute(delete(RecentlyUsed).where(RecentlyUsed.id.in_(ids)))
