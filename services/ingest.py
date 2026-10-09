import asyncio
from datetime import datetime
from typing import Any, cast

from pyrogram import Client
from pyrogram.types import Sticker as Stk

from core.config import bs
from db import get_session
from db.models.sticker import Sticker
from log import logger
from repo.ocr_cache import OcrCacheRepo
from repo.sticker import StickerRepo
from utils.ai import recognize_sticker
from utils.media import sticker_to_image
from utils.telegram import get_sticker_pack_name

# 下载/转码/识别 全局并发上限
_recognize_semaphore = asyncio.Semaphore(bs.ocr_concurrency)

_SUPPORTED_MIME = ("image/webp", "video/webm", "application/x-tgsticker")


# 返回tag, 命中识别缓存直接返回; 下载/转换/识别任何一步失败都返回 None
async def get_tag(client: Client, sticker: Stk) -> str | None:
    async with get_session() as session:
        cached = await OcrCacheRepo(session).get(sticker.file_unique_id)
    if cached is not None:
        return cached

    if sticker.mime_type not in _SUPPORTED_MIME:
        return None
    try:
        async with (
            _recognize_semaphore,
            sticker_to_image(client, sticker.file_id, sticker.mime_type) as image,
        ):
            tag = await recognize_sticker(image)
    except Exception:
        logger.exception(f"贴纸识别失败: {sticker.file_unique_id}")
        return None

    # 失败或空结果不缓存
    if not tag:
        return None
    async with get_session() as session:
        await OcrCacheRepo(session).upsert(sticker.file_unique_id, tag)
    return tag


async def insert_sticker(client: Client, uid: int, sticker: Stk, title: str | None = None) -> dict | None:
    tag = await get_tag(client, sticker)
    if tag is None:
        return None
    stk_ = await create_sticker_data(client, uid, tag, sticker, title)
    async with get_session() as session:
        await StickerRepo(session).add(Sticker(**stk_))
    return stk_


# 批量添加, 返回识别失败未插入的数量
async def insert_stickers(client: Client, uid: int, stickers: list[Stk], title: str | None = None) -> int:
    data = []
    for s in stickers:
        tag = await get_tag(client, s)
        if tag is None:
            continue
        data.append(Sticker(**await create_sticker_data(client, uid, tag, s, title)))
    if data:
        async with get_session() as session:
            await StickerRepo(session).add_all(data)
    return len(stickers) - len(data)


async def create_sticker_data(
    client: Client, uid: int, tag: str, sticker: Stk, title: str | None = None
) -> dict[str, Any]:
    # 优先用户自定义title > 传入的贴纸包title > 在线获取, 都不行就用 set_name
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
        "title": title or sticker.set_name,
        "usage_count": 0,
        "time": cast(datetime, sticker.date).timestamp(),  # 贴纸添加时间转为时间戳
    }
