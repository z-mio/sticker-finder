import asyncio
from typing import Any, cast

from pyrogram import Client, filters
from pyrogram.errors import RPCError
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from db import get_session
from db.models.auto_index import AutoIndexSticker
from log import logger
from repo.sticker import StickerRepo
from services.auto_index import AutoIndexService
from services.ingest import insert_sticker
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
    stk_set = await parse_stickers(client, set_name, i.hash or 0)
    if stk_set is None:
        logger.debug(f"自动索引贴纸包 {set_name} 不存在或已删除")
        return
    if stk_set.not_modified:
        return
    async with get_session() as session:
        existing = set(await StickerRepo(session).list_unique_ids_by_set(uid, set_name))
    failed = 0
    for s in stk_set.stickers:
        if s.file_unique_id in existing:
            continue
        stk = await insert_sticker(client, uid, s, stk_set.title)
        if stk is None:
            failed += 1
            continue
        button = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"标签：{stk['tag']}",
                        switch_inline_query_current_chat=f"{stk['sticker_unique_id']}",
                    )
                ],
                [InlineKeyboardButton("新贴纸|已自动索引", url=f"t.me/addstickers/{set_name}")],
            ]
        )
        # 通知失败不影响已插入的贴纸, 也不计入 failed
        try:
            await client.send_sticker(chat_id=uid, sticker=s.file_id, reply_markup=button)
        except RPCError as e:
            logger.warning(f"自动索引通知发送失败: {e}")

    if failed:
        # 有识别失败的贴纸就不更新 hash, 下次运行会重试
        logger.warning(f"自动索引贴纸包 {set_name} 有 {failed} 张贴纸识别失败，未更新 hash")
        return

    # 全部处理成功后才写回新 hash
    async with get_session() as session:
        await AutoIndexService(session).update_hash(i.id, stk_set.hash)


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
