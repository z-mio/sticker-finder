import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, cast

from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Sticker,
)
from sqlalchemy import select

from core.database import AutoIndexSticker, DBSession
from core.scheduler import scheduler
from log import logger
from utils.filters import is_admin
from utils.queries import get_auto_indexed_packages, stick_find
from utils.telegram import parse_stickers


def build_auto_index_button(set_name: str, uid: int) -> InlineKeyboardButton:
    result = get_auto_indexed_packages(set_name, uid)
    return InlineKeyboardButton(f"自动索引新贴纸{'✅' if result else '❎'}", callback_data=f"auto_index_{set_name}")


@Client.on_callback_query(filters.regex(r"^auto_index_(.+)") & is_admin)
async def set_auto_index(_: Client, callback_query: CallbackQuery) -> None:
    set_name = str(callback_query.data).replace("auto_index_", "")
    uid = callback_query.from_user.id
    result = get_auto_indexed_packages(set_name, uid)
    with DBSession.begin() as session:
        if result:
            session.delete(result)
        else:
            session.add(AutoIndexSticker(uid=uid, set_name=set_name))
    message = cast(Any, callback_query.message)
    button = cast(InlineKeyboardMarkup, message.reply_markup).inline_keyboard
    button[-1] = [build_auto_index_button(set_name, uid)]

    await message.edit_reply_markup(InlineKeyboardMarkup(button))
    await callback_query.answer()


async def update(
    client: Client,
    i: AutoIndexSticker,
    insert_stacker: Callable[[Client, int, Any], Awaitable[dict | None]],
) -> None:
    set_name = i.set_name
    uid = i.uid
    stk_set = await parse_stickers(client, set_name)
    if not stk_set:
        return
    stks: list[Sticker] = stk_set["final"]
    existing_stickers = [i.sticker_unique_id for i in stick_find(set_name, uid)]
    for s in stks:
        if s.file_unique_id in existing_stickers:
            continue
        stk = await insert_stacker(client, uid, s) or {}
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
        await client.send_sticker(chat_id=uid, sticker=s.file_id, reply_markup=button)


@logger.catch()
async def index_sticker(client: Client) -> None:
    from plugins.insert_sticker import insert_stacker

    with DBSession() as session:
        stmt = select(AutoIndexSticker)
        result = session.execute(stmt).scalars().all()

    await asyncio.gather(*[update(client, i, insert_stacker) for i in result])


def scheduled_indexing_tasks(client: Client) -> None:
    scheduler.add_job(
        id="auto_index_sticker",
        func=index_sticker,
        args=[client],
        trigger="interval",
        minutes=10,
    )
