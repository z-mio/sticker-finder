import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from pyrogram import Client
from pyrogram.types import Sticker as Stk

from db import get_session
from db.models.sticker import Sticker
from log import logger
from repo.ocr_cache import OcrCacheRepo
from repo.sticker import StickerRepo
from utils.ai import recognize_sticker
from utils.media import sticker_to_image
from utils.telegram import get_sticker_pack_name

_SUPPORTED_MIME = ("image/webp", "video/webm", "application/x-tgsticker")


# 入库用的贴纸信息, 可以来自 pyrogram Sticker 或 IngestTask
@dataclass
class StickerSource:
    file_id: str
    file_unique_id: str
    mime_type: str | None
    emoji: str | None
    set_name: str
    date: int

    @classmethod
    def from_sticker(cls, stk: Stk) -> "StickerSource":
        return cls(
            file_id=stk.file_id,
            file_unique_id=stk.file_unique_id,
            mime_type=stk.mime_type,
            emoji=stk.emoji,
            set_name=cast(str, stk.set_name),
            date=int(cast(datetime, stk.date).timestamp()) if stk.date else int(time.time()),
        )


# 返回tag, 命中识别缓存直接返回; 下载/转换/识别任何一步失败都返回 None
async def get_tag(client: Client, source: StickerSource) -> str | None:
    async with get_session() as session:
        cached = await OcrCacheRepo(session).get(source.file_unique_id)
    if cached is not None:
        return cached

    if source.mime_type not in _SUPPORTED_MIME:
        return None
    try:
        async with sticker_to_image(client, source.file_id, source.mime_type) as image:
            tag = await recognize_sticker(image)
    except Exception:
        logger.exception(f"贴纸识别失败: {source.file_unique_id}")
        return None

    # 失败或空结果不缓存
    if not tag:
        return None
    async with get_session() as session:
        await OcrCacheRepo(session).upsert(source.file_unique_id, tag)
    return tag


# 入库一张贴纸, 已存在时直接返回已有数据(幂等), 返回 (数据, 是否新插入), 识别失败返回 (None, False)
async def insert_sticker(
    client: Client, uid: int, source: StickerSource, title: str | None = None
) -> tuple[dict | None, bool]:
    async with get_session() as session:
        existing = await StickerRepo(session).get(uid, source.file_unique_id)
    if existing is not None:
        return sticker_to_dict(existing), False

    tag = await get_tag(client, source)
    if tag is None:
        return None, False
    stk_ = await create_sticker_data(client, uid, tag, source, title)
    async with get_session() as session:
        await StickerRepo(session).add(Sticker(**stk_))
    return stk_, True


def sticker_to_dict(sticker: Sticker) -> dict[str, Any]:
    return {
        "uid": sticker.uid,
        "tag": sticker.tag,
        "sticker_id": sticker.sticker_id,
        "sticker_unique_id": sticker.sticker_unique_id,
        "sticker_type": sticker.sticker_type,
        "emoji": sticker.emoji,
        "set_name": sticker.set_name,
        "title": sticker.title,
        "usage_count": sticker.usage_count,
        "time": sticker.time,
    }


async def create_sticker_data(
    client: Client, uid: int, tag: str, source: StickerSource, title: str | None = None
) -> dict[str, Any]:
    # 优先用户自定义title > 传入的贴纸包title > 在线获取, 都不行就用 set_name
    async with get_session() as session:
        title = await StickerRepo(session).get_title_by_set(uid, source.set_name) or title
    if not title:
        title = await get_sticker_pack_name(client, source.set_name)

    return {
        "uid": uid,
        "tag": tag,
        "sticker_id": source.file_id,
        "sticker_unique_id": source.file_unique_id,
        "sticker_type": source.mime_type,
        "emoji": source.emoji,
        "set_name": source.set_name,
        "title": title or source.set_name,
        "usage_count": 0,
        "time": source.date,  # 贴纸添加时间转为时间戳
    }
