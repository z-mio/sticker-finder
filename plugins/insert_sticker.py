import re
import time
from typing import cast

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LinkPreviewOptions,
    Message,
)
from pyrogram.types import Sticker as Stk
from sqlalchemy.exc import IntegrityError

from db import get_session
from db.models.sticker import Sticker
from log import logger
from plugins.auto_index import build_auto_index_button
from repo.sticker import StickerRepo
from services.ingest import insert_sticker, insert_stickers
from utils.filters import is_admin
from utils.rate_limit import rate_limit
from utils.telegram import parse_stickers

STICKER_PACK_STATUS: dict[int, bool] = {}


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
    if STICKER_PACK_STATUS.get(uid):
        await message.reply("当前已有任务，请等完成后再试")
        return

    STICKER_PACK_STATUS[uid] = True
    try:
        await add_sticker_pack(client, message, match[1])
    except Exception as e:
        logger.error(e)
        await message.reply(f"添加失败，请重试\n错误：{e}")
    finally:
        STICKER_PACK_STATUS[uid] = False


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
    button = [
        [
            InlineKeyboardButton(
                "编辑标签",
                switch_inline_query_current_chat=f"edit {sticker.file_unique_id}\000",
            ),
            InlineKeyboardButton(
                "删除贴纸",
                switch_inline_query_current_chat=f"del {sticker.file_unique_id}\000",
            ),
        ],
        [
            InlineKeyboardButton(
                "编辑贴纸包",
                switch_inline_query_current_chat=f"edit https://t.me/addstickers/{sticker.set_name}\000",
            ),
            InlineKeyboardButton(
                "删除贴纸包",
                switch_inline_query_current_chat=f"del https://t.me/addstickers/{sticker.set_name}\000",
            ),
        ],
        [await build_auto_index_button(sticker.set_name, uid)],
    ]
    text = "**标签：**`{tag}`\n**Emoji：**`{emoji}`\n**贴纸包：**`{title}` | `{set_name}`"

    # 如果贴纸已经存在就发送贴纸信息
    if stk := await sticker_exist(uid, sticker.file_unique_id):
        text = (
            f"{text.format(tag=stk.tag, emoji=stk.emoji, title=stk.title, set_name=stk.set_name)}"
            f"\n**使用次数：**`{stk.usage_count + 1}`"
        )
        await message.reply(text, reply_markup=InlineKeyboardMarkup(button))
        return

    msg = cast(Message, await message.reply("添加中...", disable_notification=True))
    try:
        stk_dict = await insert_sticker(client, uid, sticker)
    except IntegrityError:
        stk = cast(Sticker, await sticker_exist(uid, sticker.file_unique_id))
        text = text.format(tag=stk.tag, emoji=stk.emoji, title=stk.title, set_name=stk.set_name)
        await msg.edit(text, reply_markup=InlineKeyboardMarkup(button))
        return
    if stk_dict is None:
        await msg.edit("识别失败，未添加，请稍后重新发送贴纸")
        return
    info = text.format(
        tag=stk_dict["tag"], emoji=stk_dict["emoji"], title=stk_dict["title"], set_name=stk_dict["set_name"]
    )
    text = f"✅添加成功!\n{info}"
    await msg.edit(text, reply_markup=InlineKeyboardMarkup(button))


# 添加新贴纸包
async def add_sticker_pack(client: Client, message: Message, set_name: str) -> None:
    stk_pack = await parse_stickers(client, set_name)
    if stk_pack is None or stk_pack.not_modified:
        await message.reply("贴纸包不存在或链接无效")
        return

    assert message.from_user is not None
    uid = message.from_user.id
    a_button = [
        InlineKeyboardButton("查看贴纸包", switch_inline_query_current_chat=stk_pack.short_name),
        InlineKeyboardButton("编辑贴纸包", switch_inline_query_current_chat=f"edit {message.text}\000"),
        InlineKeyboardButton("删除贴纸包", switch_inline_query_current_chat=f"del {message.text}\000"),
    ]
    stop_button = [InlineKeyboardButton("停止添加", callback_data="sticker_stop")]

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
    failed = 0
    t = time.time()
    done = stk_pack.count - len(pending)
    for start in range(0, len(pending), 5):
        if not STICKER_PACK_STATUS[uid]:
            await msg.edit("已停止添加")
            return
        failed += await insert_stickers(client, uid, pending[start : start + 5], stk_pack.title)
        done = min(done + 5, stk_pack.count)
        await msg.edit(
            f"正在添加贴纸包，请稍等|{done}/{stk_pack.count}",
            reply_markup=InlineKeyboardMarkup([a_button, stop_button]),
        )
    text = f"""
✅完成！
贴纸包: `{stk_pack.title}`|`{stk_pack.short_name}`
数量: `{stk_pack.count}`
耗时: `{time.time() - t:.2f}s`
"""
    if failed:
        text += f"失败: `{failed}` 张（识别失败未添加，重新发送链接可补齐）\n"
    await msg.edit(
        text,
        reply_markup=InlineKeyboardMarkup([a_button, [await build_auto_index_button(set_name, uid)]]),
    )


@Client.on_callback_query(filters.regex(r"sticker_stop") & is_admin)
async def stop_add_sticker(_: Client, callback_query: CallbackQuery) -> None:
    STICKER_PACK_STATUS[callback_query.from_user.id] = False
    await callback_query.answer()


# 判断贴纸是否已存在
async def sticker_exist(uid: int, file_unique_id: str) -> Sticker | None:
    async with get_session() as session:
        return await StickerRepo(session).get(uid, file_unique_id)
