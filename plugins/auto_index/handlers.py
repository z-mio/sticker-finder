from typing import Any, cast

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
)

from db import get_session
from log import logger
from plugins.filters import is_admin
from plugins.helpers import build_auto_index_button
from services.auto_index import AutoIndexService


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
