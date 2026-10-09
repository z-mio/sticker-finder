from dataclasses import dataclass, field

from pyrogram import Client, errors, raw
from pyrogram.raw.types.messages import StickerSet, StickerSetNotModified
from pyrogram.types import Sticker as Stk


@dataclass
class StickerSetInfo:
    title: str
    short_name: str
    count: int
    hash: int
    stickers: list[Stk] = field(default_factory=list)
    not_modified: bool = False


# 获取贴纸包名称, 不存在返回 None
async def get_sticker_pack_name(client: Client, set_name: str) -> str | None:
    try:
        info: StickerSet = await client.invoke(
            raw.functions.messages.GetStickerSet(  # type: ignore[arg-type]
                stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
                hash=0,
            )
        )
    except errors.StickersetInvalid:
        return None
    return info.set.title


# 获取贴纸包内所有贴纸, known_hash 传上次记录的 hash 以利用 StickerSetNotModified
async def parse_stickers(client: Client, set_name: str, known_hash: int = 0) -> StickerSetInfo | None:
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
        return StickerSetInfo(title="", short_name=set_name, count=0, hash=known_hash, not_modified=True)
    stickers = [
        await Stk._parse(client, stk, {type(i): i for i in stk.attributes})  # type: ignore[arg-type, union-attr]
        for stk in info.documents
    ]
    return StickerSetInfo(
        title=info.set.title,
        short_name=info.set.short_name,
        count=info.set.count,
        hash=info.set.hash,
        stickers=stickers,
    )


def get_sticker_id(sid: str) -> str:
    i = sid.split("_")
    return "_".join(i[1:]) if i[1:] else i[0]
