from collections.abc import Sequence
from typing import cast

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.auto_index import AutoIndexSticker


class AutoIndexRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, uid: int, set_name: str) -> AutoIndexSticker | None:
        stmt = select(AutoIndexSticker).where(AutoIndexSticker.uid == uid, AutoIndexSticker.set_name == set_name)
        return cast(AutoIndexSticker | None, await self._session.scalar(stmt))

    async def get_by_id(self, record_id: int) -> AutoIndexSticker | None:
        return cast(AutoIndexSticker | None, await self._session.get(AutoIndexSticker, record_id))

    async def list_all(self) -> Sequence[AutoIndexSticker]:
        result = await self._session.scalars(select(AutoIndexSticker))
        return result.all()

    async def add(self, uid: int, set_name: str) -> AutoIndexSticker:
        record = AutoIndexSticker(uid=uid, set_name=set_name)
        self._session.add(record)
        await self._session.flush()
        return record

    async def remove(self, record: AutoIndexSticker) -> None:
        await self._session.delete(record)

    async def update_hash(self, record_id: int, new_hash: int) -> None:
        stmt = update(AutoIndexSticker).where(AutoIndexSticker.id == record_id).values(hash=new_hash)
        await self._session.execute(stmt)

    async def remove_by_uid(self, uid: int) -> None:
        stmt = delete(AutoIndexSticker).where(AutoIndexSticker.uid == uid)
        await self._session.execute(stmt)
