import asyncio
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import cv2
from openai import OpenAIError
from PIL import UnidentifiedImageError
from pyrlottie import FileMap, LottieFile, convMultLottie
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

from core.config import bs
from db import get_session
from db.models.sticker import Sticker
from log import logger
from plugins.auto_index import build_auto_index_button
from repo.ocr_cache import OcrCacheRepo
from repo.sticker import StickerRepo
from utils.ai import recognize_sticker
from utils.filters import is_admin
from utils.lottie import ensure_pyrlottie_exec_bit
from utils.rate_limit import rate_limit
from utils.telegram import get_sticker_pack_name, parse_stickers

ensure_pyrlottie_exec_bit()

# 下载/转码/OCR 全局并发上限
_ocr_semaphore = asyncio.Semaphore(bs.ocr_concurrency)

STICKER_PACK_STATUS: dict[int, bool] = {}


@Client.on_message(filters.text & filters.private & ~filters.inline_keyboard & ~filters.via_bot & is_admin)
@logger.catch()
async def help_(client: Client, message: Message) -> None:
    text = str(message.text)
    if not text.startswith("https://t.me/addstickers/"):
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
        await add_sticker_pack(client, message)
    except Exception as e:
        logger.error(e)
        await message.reply(f"添加失败，请重试\n错误：{e}")
    finally:
        STICKER_PACK_STATUS[uid] = False
    return


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

    else:
        msg = cast(Message, await message.reply("添加中...", disable_notification=True))
        try:
            stk_dict = cast(dict, await insert_stacker(client, uid, sticker))
        except IntegrityError:
            stk = cast(Sticker, await sticker_exist(uid, sticker.file_unique_id))
            text = text.format(tag=stk.tag, emoji=stk.emoji, title=stk.title, set_name=stk.set_name)
            await msg.edit(text, reply_markup=InlineKeyboardMarkup(button))
            return
        info = text.format(
            tag=stk_dict["tag"], emoji=stk_dict["emoji"], title=stk_dict["title"], set_name=stk_dict["set_name"]
        )
        text = f"✅添加成功!\n{info}"
        await msg.edit(text, reply_markup=InlineKeyboardMarkup(button))
    return


# 添加新贴纸包
async def add_sticker_pack(client: Client, message: Message) -> None:
    set_name = str(message.text).replace("https://t.me/addstickers/", "")
    stk_pack = cast(dict, await parse_stickers(client, set_name))
    assert message.from_user is not None
    uid = message.from_user.id

    a_button = [
        InlineKeyboardButton("查看贴纸包", switch_inline_query_current_chat=stk_pack["short_name"]),
        InlineKeyboardButton("编辑贴纸包", switch_inline_query_current_chat=f"edit {message.text}\000"),
        InlineKeyboardButton("删除贴纸包", switch_inline_query_current_chat=f"del {message.text}\000"),
    ]
    stop_button = [InlineKeyboardButton("停止添加", callback_data="sticker_stop")]
    msg = cast(Message, await message.reply(f"正在添加贴纸包，请稍等|0/{stk_pack['count']}"))
    _stk: list[Stk] = []
    t = time.time()
    for i, sticker in enumerate(stk_pack["final"]):
        if not STICKER_PACK_STATUS[uid]:
            await msg.edit("已停止添加")
            return
        i += 1
        if i % 5 == 0 or i == stk_pack["count"]:
            await insert_stacker(client, uid, _stk, stk_pack["title"])
            _stk.clear()
            await msg.edit(
                f"正在添加贴纸包，请稍等|{i}/{stk_pack['count']}",
                reply_markup=InlineKeyboardMarkup([a_button, stop_button]),
            )
        if await sticker_exist(uid, sticker.file_unique_id):
            continue
            # 如果贴纸已经存在就发送贴纸信息
        _stk.append(sticker)
    await insert_stacker(client, uid, _stk, stk_pack["title"])
    text = f"""
✅完成！
贴纸包: `{stk_pack["title"]}`|`{stk_pack["short_name"]}`
数量: `{stk_pack["count"]}`
耗时: `{time.time() - t:.2f}s`
"""
    await msg.edit(
        text,
        reply_markup=InlineKeyboardMarkup([a_button, [await build_auto_index_button(set_name, uid)]]),
    )
    del _stk, set_name, stk_pack, uid, text
    return


@Client.on_callback_query(filters.regex(r"sticker_stop") & is_admin)
async def stop_add_sticker(_: Client, callback_query: CallbackQuery) -> None:
    STICKER_PACK_STATUS[callback_query.from_user.id] = False
    await callback_query.answer()


# 判断贴纸是否已存在
async def sticker_exist(uid: int, file_unique_id: str) -> Sticker | None:
    async with get_session() as session:
        return await StickerRepo(session).get(uid, file_unique_id)


# 下载贴纸 获取tag
# "image/webp", "video/webm", "application/x-tgsticker"
async def download_sticker(client: Client, sticker_id: str, mime_type: str) -> str:
    async with _ocr_semaphore:
        return await _download_sticker_inner(client, sticker_id, mime_type)


async def _download_sticker_inner(client: Client, sticker_id: str, mime_type: str) -> str:
    i_p: str | None = None
    path: str | None = None
    try:
        if mime_type == "application/x-tgsticker":
            path = await tgs_to_webp(client, sticker_id)
        elif mime_type == "video/webm":
            i_p, path = await get_the_first_frame(client, sticker_id)
        else:
            path = cast(
                str,
                await client.download_media(
                    sticker_id,
                    bs.downloads_path.joinpath(f"{sticker_id[:5]}_{time.time():.0f}.png"),
                ),
            )
        return await identify_tag(path)
    finally:
        # 无论成功还是失败都清理临时文件
        if i_p:
            Path(i_p).unlink(missing_ok=True)
        if path:
            Path(path).unlink(missing_ok=True)


async def tgs_to_webp(client: Client, sticker_id: str) -> str:
    i_p = str(
        await client.download_media(
            sticker_id,
            bs.downloads_path.joinpath(f"{sticker_id[:5]}_{time.time():.0f}.tgs"),
        )
    )
    o_p = f"{i_p}.webp"
    try:
        await convMultLottie([FileMap(LottieFile(i_p), {o_p})], frameSkip=60)
    except Exception:
        Path(o_p).unlink(missing_ok=True)
        raise
    finally:
        Path(i_p).unlink(missing_ok=True)
    return o_p


def _extract_first_frame(i_p: str, o_p: str) -> None:
    video = cv2.VideoCapture(i_p)
    image = video.read()[1]
    cv2.imwrite(o_p, image)


# 获取视频第一帧
async def get_the_first_frame(client: Client, sticker_id: str) -> tuple[str, str]:
    i_p = str(
        await client.download_media(
            sticker_id,
            bs.downloads_path.joinpath(f"{sticker_id[:5]}_{time.time():.0f}.webm"),
        )
    )
    o_p = f"{i_p}.png"
    try:
        await asyncio.to_thread(_extract_first_frame, i_p, o_p)
    except Exception:
        Path(i_p).unlink(missing_ok=True)
        Path(o_p).unlink(missing_ok=True)
        raise

    return i_p, o_p


# 识别tag, 识别失败或 AI 返回空都视为 "None"
async def identify_tag(path: str | Path) -> str:
    try:
        tag = await recognize_sticker(path)
    except (OpenAIError, UnidentifiedImageError, OSError) as e:
        logger.warning(f"贴纸识别失败: {e}")
        return "None"
    return tag or "None"


# 返回tag, 命中 OCR 缓存直接返回
async def tag_(client: Client, sticker: Stk) -> str:
    async with get_session() as session:
        cached = await OcrCacheRepo(session).get(sticker.file_unique_id)
    if cached is not None:
        return cached

    tag = (
        await download_sticker(client, sticker.file_id, sticker.mime_type)
        if sticker.mime_type in ["image/webp", "video/webm", "application/x-tgsticker"]
        else "None"
    )
    # "None" 代表识别失败或不支持的类型, 不缓存
    if tag != "None":
        async with get_session() as session:
            await OcrCacheRepo(session).upsert(sticker.file_unique_id, tag)
    return tag


async def insert_stacker(client: Client, uid: int, sticker: Stk | list[Stk], title: str | None = None) -> dict | None:
    if isinstance(sticker, Stk):
        stk_ = await create_sticker_data(client, uid, await tag_(client, sticker), sticker, title)
        async with get_session() as session:
            await StickerRepo(session).add(Sticker(**stk_))
        return stk_
    else:
        stickers = [
            Sticker(**await create_sticker_data(client, uid, await tag_(client, sticker[i]), sticker[i], title))
            for i in range(len(sticker))
        ]
        async with get_session() as session:
            await StickerRepo(session).add_all(stickers)
    return None


async def create_sticker_data(
    client: Client, uid: int, tag: str, sticker: Stk, title: str | None = None
) -> dict[str, Any]:
    # 优先用户自定义title > 传入的贴纸包title > 在线获取
    async with get_session() as session:
        title = await StickerRepo(session).get_title_by_set(uid, cast(str, sticker.set_name)) or title
    if not title:
        title = await get_sticker_pack_name(client, cast(str, sticker.set_name))

    return {
        "uid": uid,
        "tag": tag,
        "sticker_id": sticker.file_id,
        "sticker_unique_id": sticker.file_unique_id,
        "sticker_type": sticker.mime_type,
        "emoji": sticker.emoji,
        "set_name": sticker.set_name,
        "title": title,
        "usage_count": 0,
        "time": cast(datetime, sticker.date).timestamp(),  # 贴纸添加时间转为时间戳
    }
