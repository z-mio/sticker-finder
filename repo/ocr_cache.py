from sqlalchemy.ext.asyncio import AsyncSession

from db.models.ocr_cache import OcrCache


class OcrCacheRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, sticker_unique_id: str) -> str | None:
        record = await self._session.get(OcrCache, sticker_unique_id)
        return record.tag if record else None

    async def upsert(self, sticker_unique_id: str, tag: str) -> None:
        await self._session.merge(OcrCache(sticker_unique_id=sticker_unique_id, tag=tag))
