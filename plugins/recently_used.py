from pyrogram import Client
from pyrogram.types import ChosenInlineResult

from db import get_session
from log import logger
from services.sticker import StickerService
from utils.filters import is_inline_command
from utils.telegram import get_sticker_id


# 最近使用
@Client.on_chosen_inline_result(~is_inline_command)
@logger.catch()
async def stickers_used(_: Client, chosen: ChosenInlineResult) -> None:
    if chosen.result_id.startswith("icon"):
        return
    async with get_session() as session:
        await StickerService(session).record_use(chosen.from_user.id, get_sticker_id(chosen.result_id))
