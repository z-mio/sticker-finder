import time
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.recently_used import RecentlyUsed
from db.models.sticker import Sticker
from repo.auto_index import AutoIndexRepo
from repo.ingest import IngestRepo
from repo.recently_used import RecentlyUsedRepo
from repo.sticker import StickerRepo


class StickerService:
    def __init__(self, session: AsyncSession) -> None:
        self.stickers = StickerRepo(session)
        self.recently_used = RecentlyUsedRepo(session)
        self.auto_index = AutoIndexRepo(session)
        self.ingest = IngestRepo(session)

    async def get(self, uid: int, sticker_unique_id: str) -> Sticker | None:
        return await self.stickers.get(uid, sticker_unique_id)

    # 搜索一页, limit 建议传 page_size+1 用于判断是否有下一页
    async def search_page(self, uid: int, query: str | None, offset: int, limit: int) -> Sequence[Sticker]:
        return await self.stickers.search(uid, query, offset, limit)

    async def list_existing_history(self, uid: int) -> Sequence[RecentlyUsed]:
        return await self.recently_used.list_existing(uid)

    # 删除单张贴纸及其最近使用记录
    async def delete_single(self, uid: int, sticker_unique_id: str) -> bool:
        sticker = await self.stickers.get(uid, sticker_unique_id)
        if sticker is None:
            return False
        await self.recently_used.remove_by_unique_ids(uid, [sticker_unique_id])
        await self.stickers.remove(sticker)
        return True

    # 删除贴纸包: 队列任务 + 自动索引 + 相关最近使用 + 所有贴纸
    async def delete_pack(self, uid: int, set_name: str) -> None:
        await self.ingest.delete_jobs(uid, set_name)
        if record := await self.auto_index.get(uid, set_name):
            await self.auto_index.remove(record)
        unique_ids = await self.stickers.list_unique_ids_by_set(uid, set_name)
        await self.recently_used.remove_by_unique_ids(uid, unique_ids)
        await self.stickers.remove_by_set(uid, set_name)

    # 清空用户的全部数据
    async def clear(self, uid: int) -> None:
        await self.ingest.delete_jobs_by_uid(uid)
        await self.auto_index.remove_by_uid(uid)
        await self.stickers.remove_by_uid(uid)
        await self.recently_used.remove_by_uid(uid)

    # 记录一次贴纸使用, 贴纸不存在时不做任何事
    async def record_use(self, uid: int, sticker_unique_id: str) -> None:
        sticker = await self.stickers.get(uid, sticker_unique_id)
        if sticker is None:
            return
        sticker.usage_count += 1

        # 历史记录已存在就更新时间, 否则新增并裁剪到最新19条
        if record := await self.recently_used.get(uid, sticker_unique_id):
            record.time = time.time()  # type: ignore[assignment]
            return
        await self.recently_used.add(
            RecentlyUsed(
                uid=uid,
                sticker_id=sticker.sticker_id,
                sticker_unique_id=sticker_unique_id,
                time=time.time(),
            )
        )
        await self.recently_used.trim(uid, keep=19)
