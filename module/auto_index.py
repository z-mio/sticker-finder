import concurrent
from concurrent.futures import ThreadPoolExecutor

from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Sticker,
)
from sqlalchemy import select

from database import AutoIndexSticker, DBSession
from tool.scheduler_manager import aps
from utils import get_auto_indexed_packages, is_admin, parse_stickers, stick_find


def build_auto_index_button(set_name: str, uid: int) -> InlineKeyboardButton:
    result = get_auto_indexed_packages(set_name, uid)
    return InlineKeyboardButton(
        f'自动索引新贴纸{"✅" if result else "❎"}', callback_data=f"auto_index_{set_name}"
    )


@Client.on_callback_query(filters.regex(r"^auto_index_(.+)") & is_admin())
async def set_auto_index(_, callback_query: CallbackQuery):
    set_name = callback_query.data.replace("auto_index_", "")
    uid = callback_query.from_user.id
    result = get_auto_indexed_packages(set_name, uid)
    with DBSession.begin() as session:
        if result:
            session.delete(result)
        else:
            session.add(AutoIndexSticker(uid=uid, set_name=set_name))
    button = callback_query.message.reply_markup.inline_keyboard
    button[-1] = [build_auto_index_button(set_name, uid)]

    await callback_query.message.edit_reply_markup(InlineKeyboardMarkup(button))


def update(client: Client, i, insert_stacker):
    set_name = i.set_name
    uid = i.uid
    stk_set = parse_stickers(client, set_name)
    if not stk_set:
        return
    stks: list[Sticker] = stk_set["final"]
    existing_stickers = [i.sticker_unique_id for i in stick_find(set_name, uid)]
    for s in stks:
        if s.file_unique_id in existing_stickers:
            continue
        stk = insert_stacker(client, uid, s)
        button = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f'标签：{stk["tag"]}',
                        switch_inline_query_current_chat=f'{stk["sticker_unique_id"]}',
                    )
                ],
                [InlineKeyboardButton("新贴纸|已自动索引", url=f"t.me/addstickers/{set_name}")],
            ]
        )
        client.send_sticker(chat_id=uid, sticker=s.file_id, reply_markup=button)


@logger.catch()
def index_sticker(client: Client):
    from module.insert_sticker import insert_stacker

    session = DBSession()
    stmt = select(AutoIndexSticker)
    result = session.execute(stmt).scalars().all()

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(update, client, i, insert_stacker) for i in result]
    [future.result() for future in concurrent.futures.wait(futures).done]


def scheduled_indexing_tasks(client: Client):
    aps.add_job(
        job_id="auto_index_sticker",
        func=index_sticker,
        args=[client],
        trigger="interval",
        minutes=10,
    )
