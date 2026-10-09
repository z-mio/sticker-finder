from collections.abc import Sequence
from typing import cast

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.sticker import Sticker


class StickerRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, uid: int, sticker_unique_id: str) -> Sticker | None:
        stmt = select(Sticker).where(Sticker.sticker_unique_id == sticker_unique_id, Sticker.uid == uid)
        return cast(Sticker | None, await self._session.scalar(stmt))

    async def search(self, uid: int, query: str | None, offset: int, limit: int) -> Sequence[Sticker]:
        if query:
            stmt = select(Sticker).where(
                or_(
                    Sticker.tag.ilike(f"%{query}%"),
                    Sticker.emoji.ilike(f"%{query}%"),
                    Sticker.title.ilike(f"%{query}%"),
                    Sticker.set_name == query,
                    Sticker.sticker_unique_id == query,
                ),
                Sticker.uid == uid,
            )
        else:
            stmt = select(Sticker).where(Sticker.uid == uid)
        # 按贴纸包名和添加时间升序排序
        stmt = stmt.order_by(Sticker.set_name.asc(), Sticker.time.asc()).offset(offset).limit(limit)
        result = await self._session.scalars(stmt)
        return result.all()

    async def list_unique_ids_by_set(self, uid: int, set_name: str) -> Sequence[str]:
        stmt = select(Sticker.sticker_unique_id).where(Sticker.set_name == set_name, Sticker.uid == uid)
        result = await self._session.scalars(stmt)
        return result.all()

    async def get_title_by_set(self, uid: int, set_name: str) -> str | None:
        stmt = select(Sticker.title).where(Sticker.set_name == set_name, Sticker.uid == uid)
        return cast(str | None, await self._session.scalar(stmt))

    async def add(self, sticker: Sticker) -> Sticker:
        self._session.add(sticker)
        await self._session.flush()
        return sticker

    async def add_all(self, stickers: list[Sticker]) -> None:
        self._session.add_all(stickers)
        await self._session.flush()

    async def update_tag(self, uid: int, sticker_unique_id: str, new_tag: str) -> None:
        stmt = (
            update(Sticker)
            .where(Sticker.sticker_unique_id == sticker_unique_id, Sticker.uid == uid)
            .values(tag=new_tag)
        )
        await self._session.execute(stmt)

    async def update_title_by_set(self, uid: int, set_name: str, new_title: str) -> None:
        stmt = update(Sticker).where(Sticker.set_name == set_name, Sticker.uid == uid).values(title=new_title)
        await self._session.execute(stmt)

    async def remove(self, sticker: Sticker) -> None:
        await self._session.delete(sticker)

    async def remove_by_set(self, uid: int, set_name: str) -> None:
        stmt = delete(Sticker).where(Sticker.set_name == set_name, Sticker.uid == uid)
        await self._session.execute(stmt)

    async def remove_by_uid(self, uid: int) -> None:
        stmt = delete(Sticker).where(Sticker.uid == uid)
        await self._session.execute(stmt)
