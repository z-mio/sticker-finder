import re
from typing import cast

from pyrogram import Client, filters
from pyrogram.types import (
    ChosenInlineResult,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)

from db import get_session
from log import logger
from plugins.find_sticker import load_sticker
from services.auto_index import AutoIndexService
from services.sticker import StickerService
from utils.filters import filter_inline_query_results, is_admin
from utils.telegram import get_sticker_id, get_sticker_pack_name


@Client.on_inline_query(filters.regex(r"^del[\s\S]*") & is_admin)
@logger.catch()
async def del_sticker(client: Client, inline_query: InlineQuery) -> None:
    query = re.sub(r"del:|del\s|del", "", inline_query.query, count=1)
    # 删除贴纸包
    if query.startswith("https://t.me/addstickers/"):
        pack_name = stk_pack_name(query) or ""
        # 包已不存在时回退显示 set_name
        title = await get_sticker_pack_name(client, pack_name) or pack_name
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    title="点击删除贴纸包",
                    description=f"{title}",
                    input_message_content=InputTextMessageContent(f"已删除贴纸包: [{title}]({query})"),
                )
            ]
        )
    # 删除单张贴纸
    else:
        button = InlineKeyboardMarkup([[InlineKeyboardButton("已删除", callback_data="已删除")]])
        await load_sticker(inline_query, query, button)


@Client.on_chosen_inline_result(filter_inline_query_results("del"))
@logger.catch()
async def start_del_stickers(client: Client, chosen: ChosenInlineResult) -> None:
    query = chosen.query
    uid = chosen.from_user.id
    async with get_session() as session:
        # 删除贴纸包
        if "https://t.me/addstickers/" in query:
            pack_name = stk_pack_name(query) or ""
            await StickerService(session).delete_pack(uid, pack_name)
            return

        # 删除单张贴纸
        sticker_unique_id = get_sticker_id(chosen.result_id)
        sticker = await StickerService(session).get(uid, sticker_unique_id)
        if sticker is None:
            return
        if await AutoIndexService(session).is_enabled(uid, sticker.set_name):
            button = InlineKeyboardMarkup(
                [[InlineKeyboardButton("删除失败，请先关闭自动索引", callback_data="删除失败")]]
            )
            await client.edit_inline_reply_markup(cast(str, chosen.inline_message_id), reply_markup=button)
        else:
            await StickerService(session).delete_single(uid, sticker_unique_id)


def stk_pack_name(link: str) -> str | None:
    if match := re.search(r"([^/]+)$", link):
        return match[1]
    return None


@Client.on_inline_query(filters.regex("^clear") & is_admin)
@logger.catch()
async def clear_sticker(_: Client, inline_query: InlineQuery) -> None:
    await inline_query.answer(
        results=[
            InlineQueryResultArticle(
                title="点击删除所有贴纸",
                input_message_content=InputTextMessageContent("已删除所有贴纸"),
            )
        ]
    )


@Client.on_chosen_inline_result(filter_inline_query_results("clear"))
@logger.catch()
async def start_clear_sticker(_: Client, chosen: ChosenInlineResult) -> None:
    async with get_session() as session:
        await StickerService(session).clear(chosen.from_user.id)
