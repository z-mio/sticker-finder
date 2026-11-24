import re
import time
from typing import cast

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    LinkPreviewOptions,
    Message,
)
from pyrogram.types import Sticker as Stk

from db import get_session
from log import logger
from plugins.filters import is_admin
from plugins.helpers import build_auto_index_button, single_sticker_buttons
from repo.ingest import IngestRepo
from repo.sticker import StickerRepo
from services.ingest import StickerSource
from services.sticker import StickerService
from services.task_queue import task_queue
from utils.rate_limit import rate_limit
from utils.telegram import parse_stickers


@Client.on_message(filters.text & filters.private & ~filters.inline_keyboard & ~filters.via_bot & is_admin)
@logger.catch()
async def help_(client: Client, message: Message) -> None:
    match = re.match(r"^https://t\.me/addstickers/(\w+)", str(message.text))
    if not match:
        await message.reply(
            "请发送贴纸or贴纸包链接\n教程：[LINK](https://telegra.ph/贴纸收藏夹bot使用教程-09-08)",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return

    assert message.from_user is not None
    uid = message.from_user.id
    async with get_session() as session:
        busy = await IngestRepo(session).has_active_job(uid, "pack")
    if busy:
        await message.reply("当前已有任务，请等完成后再试")
        return

    try:
        await add_sticker_pack(client, message, match[1])
    except Exception as e:
        logger.error(e)
        await message.reply(f"添加失败，请重试\n错误：{e}")


# 添加新贴纸
@Client.on_message(filters.sticker & filters.private & ~filters.inline_keyboard & is_admin)
@rate_limit(1, 1)
@logger.catch()
async def add_sticker(client: Client, message: Message) -> None:
    assert message.from_user is not None
    sticker = cast(Stk, message.sticker)

    # 如果贴纸不在贴纸包内
    if not sticker.set_name:
        sticker.set_name = "KTagBot"  # KTagBot 是 bot 默认贴纸包 https://t.me/addstickers/KTagBot
    if not sticker.emoji:
        sticker.emoji = "😀"

    uid = message.from_user.id
    assert sticker.set_name is not None
    button = single_sticker_buttons(sticker.file_unique_id, sticker.set_name)
    button.inline_keyboard.append([await build_auto_index_button(sticker.set_name, uid)])
    text = "**标签：**`{tag}`\n**Emoji：**`{emoji}`\n**贴纸包：**`{title}` | `{set_name}`"

    # 如果贴纸已经存在就发送贴纸信息
    async with get_session() as session:
        stk = await StickerService(session).get(uid, sticker.file_unique_id)
    if stk is not None:
        text = (
            f"{text.format(tag=stk.tag, emoji=stk.emoji, title=stk.title, set_name=stk.set_name)}"
            f"\n**使用次数：**`{stk.usage_count + 1}`"
        )
        await message.reply(text, reply_markup=button)
        return

    msg = cast(Message, await message.reply("添加中...", disable_notification=True))
    await task_queue.submit(
        {
            "kind": "single",
            "uid": uid,
            "set_name": sticker.set_name,
            "title": None,
            "chat_id": uid,
            "message_id": msg.id,
            "total": 1,
            "created_at": time.time(),
        },
        [StickerSource.from_sticker(sticker)],
    )


# 添加新贴纸包
async def add_sticker_pack(client: Client, message: Message, set_name: str) -> None:
    stk_pack = await parse_stickers(client, set_name)
    if stk_pack is None or stk_pack.not_modified:
        await message.reply("贴纸包不存在或链接无效")
        return

    assert message.from_user is not None
    uid = message.from_user.id

    # 已存在和包内重复的贴纸只取一次
    async with get_session() as session:
        existing = set(await StickerRepo(session).list_unique_ids_by_set(uid, set_name))
    seen: set[str] = set()
    pending: list[Stk] = []
    for s in stk_pack.stickers:
        if s.file_unique_id in existing or s.file_unique_id in seen:
            continue
        seen.add(s.file_unique_id)
        pending.append(s)

    msg = cast(Message, await message.reply(f"正在添加贴纸包，请稍等|0/{stk_pack.count}"))
    await task_queue.submit(
        {
            "kind": "pack",
            "uid": uid,
            "set_name": set_name,
            "title": stk_pack.title,
            "chat_id": uid,
            "message_id": msg.id,
            "total": stk_pack.count,
            "created_at": time.time(),
        },
        [StickerSource.from_sticker(s) for s in pending],
    )


@Client.on_callback_query(filters.regex(r"sticker_stop") & is_admin)
async def stop_add_sticker(_: Client, callback_query: CallbackQuery) -> None:
    uid = callback_query.from_user.id
    async with get_session() as session:
        repo = IngestRepo(session)
        job = await repo.stop_active_job(uid, "pack")
        job_id = job.id if job is not None else None
        if job_id is not None:
            await repo.delete_pending_tasks(job_id)
    if job_id is not None:
        await task_queue.finalize(job_id)
    await callback_query.answer()
