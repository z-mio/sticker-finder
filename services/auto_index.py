import asyncio
import time
from collections.abc import Sequence

from pyrogram import Client
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from db.models.auto_index import AutoIndexSticker
from log import logger
from repo.auto_index import AutoIndexRepo
from repo.ingest import IngestRepo
from repo.sticker import StickerRepo
from services.ingest import StickerSource
from utils.telegram import parse_stickers


class AutoIndexService:
    def __init__(self, session: AsyncSession) -> None:
        self.auto_index = AutoIndexRepo(session)

    # 切换自动索引, 返回切换后的开启状态
    async def toggle(self, uid: int, set_name: str) -> bool:
        if record := await self.auto_index.get(uid, set_name):
            await self.auto_index.remove(record)
            return False
        await self.auto_index.add(uid, set_name)
        return True

    async def is_enabled(self, uid: int, set_name: str) -> bool:
        return await self.auto_index.get(uid, set_name) is not None

    async def list(self) -> Sequence[AutoIndexSticker]:
        return await self.auto_index.list_all()

    async def update_hash(self, record_id: int, new_hash: int) -> None:
        await self.auto_index.update_hash(record_id, new_hash)

    # 记录还存在才更新 hash
    async def update_hash_if_exists(self, record_id: int, new_hash: int) -> None:
        if await self.auto_index.get_by_id(record_id):
            await self.auto_index.update_hash(record_id, new_hash)


async def update(client: Client, i: AutoIndexSticker) -> None:
    from services.task_queue import task_queue

    set_name = i.set_name
    uid = i.uid
    async with get_session() as session:
        if await IngestRepo(session).has_active_auto_job(i.id):
            return
    stk_set = await parse_stickers(client, set_name, i.hash or 0)
    if stk_set is None:
        logger.debug(f"自动索引贴纸包 {set_name} 不存在或已删除")
        return
    if stk_set.not_modified:
        return
    async with get_session() as session:
        existing = set(await StickerRepo(session).list_unique_ids_by_set(uid, set_name))
    sources = [StickerSource.from_sticker(s) for s in stk_set.stickers if s.file_unique_id not in existing]
    if not sources:
        # 没有新贴纸, 直接写回 hash
        async with get_session() as session:
            await AutoIndexService(session).update_hash(i.id, stk_set.hash)
        return
    await task_queue.submit(
        {
            "kind": "auto",
            "uid": uid,
            "set_name": set_name,
            "title": stk_set.title,
            "chat_id": None,
            "message_id": None,
            "total": len(sources),
            "auto_index_id": i.id,
            "target_hash": stk_set.hash,
            "created_at": time.time(),
        },
        sources,
    )


@logger.catch()
async def index_sticker(client: Client) -> None:
    async with get_session() as session:
        result = await AutoIndexService(session).list()

    # 串行处理, 一个包失败不影响后面的包
    for i in result:
        try:
            await update(client, i)
        except Exception:
            logger.exception(f"自动索引贴纸包 {i.set_name} 失败")


AUTO_INDEX_INTERVAL = 600  # 秒


async def auto_index_loop(client: Client) -> None:
    while True:
        await asyncio.sleep(AUTO_INDEX_INTERVAL)
        await index_sticker(client)
