import asyncio
import time
from typing import Any, cast

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from core.task_queue import task_queue
from db import get_session
from db.models.auto_index import AutoIndexSticker
from log import logger
from repo.ingest import IngestRepo
from repo.sticker import StickerRepo
from services.auto_index import AutoIndexService
from services.ingest import StickerSource
from utils.filters import is_admin
from utils.telegram import parse_stickers


async def build_auto_index_button(set_name: str, uid: int) -> InlineKeyboardButton:
    async with get_session() as session:
        enabled = await AutoIndexService(session).is_enabled(uid, set_name)
    return InlineKeyboardButton(f"自动索引新贴纸{'✅' if enabled else '❎'}", callback_data=f"auto_index_{set_name}")


@Client.on_callback_query(filters.regex(r"^auto_index_(.+)") & is_admin)
@logger.catch()
async def set_auto_index(_: Client, callback_query: CallbackQuery) -> None:
    set_name = str(callback_query.data).replace("auto_index_", "")
    uid = callback_query.from_user.id
    async with get_session() as session:
        await AutoIndexService(session).toggle(uid, set_name)
    message = cast(Any, callback_query.message)
    button = cast(InlineKeyboardMarkup, message.reply_markup).inline_keyboard
    button[-1] = [await build_auto_index_button(set_name, uid)]

    await message.edit_reply_markup(InlineKeyboardMarkup(button))
    await callback_query.answer()


async def update(client: Client, i: AutoIndexSticker) -> None:
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
