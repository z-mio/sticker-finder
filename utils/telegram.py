from typing import Any

from pyrogram import Client, errors, raw
from pyrogram.raw.types.messages import StickerSet, StickerSetNotModified
from pyrogram.types import Sticker as Stk


# 获取贴纸包名称
async def get_sticker_pack_name(client: Client, set_name: str) -> Any:
    try:
        info: StickerSet = await client.invoke(
            raw.functions.messages.GetStickerSet(  # type: ignore[arg-type]
                stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
                hash=0,
            )
        )
    except errors.StickersetInvalid:
        return []
    return info.set.title


# 获取贴纸中所有贴纸, known_hash 传上次记录的 hash 以利用 StickerSetNotModified
async def parse_stickers(client: Client, set_name: str, known_hash: int = 0) -> dict | None:
    try:
        info: StickerSet | StickerSetNotModified = await client.invoke(
            raw.functions.messages.GetStickerSet(
                stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
                hash=known_hash,
            )
        )
    except errors.StickersetInvalid:
        return None
    if isinstance(info, StickerSetNotModified):
        return {"not_modified": True}
    documents = info.documents
    final = []
    title = info.set.title
    count = info.set.count
    short_name = info.set.short_name
    for stk in documents:
        __sticker = await Stk._parse(client, stk, {type(i): i for i in stk.attributes})  # type: ignore[arg-type, union-attr]
        final.append(__sticker)
    return {
        "title": title,
        "count": count,
        "short_name": short_name,
        "final": final,
        "hash": info.set.hash,
        "not_modified": False,
    }


def get_sticker_id(sid: str) -> str:
    i = sid.split("_")
    return "_".join(i[1:]) if i[1:] else i[0]
