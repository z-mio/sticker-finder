import re

from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import (
    ChosenInlineResult,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from sqlalchemy import select

from database import AutoIndexSticker, DBSession, RecentlyUsed, Sticker
from module.find_sticker import load_sticker
from utils import (
    async_get_sticker_pack_name,
    filter_inline_query_results,
    get_auto_indexed_packages,
    get_sticker_id,
    is_admin,
)


@Client.on_inline_query(filters.regex(r"^del[\s\S]*") & is_admin())
@logger.catch()
async def del_sticker(client: Client, inline_query: InlineQuery):
    query = re.sub(r"del:|del\s|del", "", inline_query.query, 1)
    # 删除贴纸包
    if query.startswith("https://t.me/addstickers/"):
        title = await async_get_sticker_pack_name(client, stk_pack_name(query))
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    title="点击删除贴纸包",
                    description=f"{title}",
                    input_message_content=InputTextMessageContent(
                        f"已删除贴纸包: [{title}]({query})"
                    ),
                )
            ]
        )
    # 删除单张贴纸
    else:
        button = InlineKeyboardMarkup([[InlineKeyboardButton("已删除", "已删除")]])
        await load_sticker(inline_query, query, button)


@Client.on_chosen_inline_result(filter_inline_query_results("del"))
@logger.catch()
async def start_del_stickers(client: Client, chosen: ChosenInlineResult):
    query = chosen.query
    uid = chosen.from_user.id
    with DBSession.begin() as session:
        # 删除贴纸包
        if "https://t.me/addstickers/" in query:
            pack_name = stk_pack_name(query)
            # 删除自动索引
            stmt = select(AutoIndexSticker).filter(
                AutoIndexSticker.uid == uid, AutoIndexSticker.set_name == pack_name
            )
            if result := session.execute(stmt).scalars().one_or_none():
                session.delete(result)

            # 删除贴纸包
            stmt = select(Sticker).filter(
                Sticker.set_name == pack_name, Sticker.uid == uid
            )
            result = session.execute(stmt).scalars().all()

            [session.delete(s) for s in result]

        # 删除单张贴纸
        else:
            stmt = select(Sticker).filter(
                Sticker.sticker_unique_id == get_sticker_id(chosen.result_id),
                Sticker.uid == uid,
            )
            result = session.execute(stmt).scalars().one()
            if get_auto_indexed_packages(result.set_name, chosen.from_user.id):
                button = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("删除失败，请先关闭自动索引", "删除失败")]]
                )
                await client.edit_inline_reply_markup(
                    chosen.inline_message_id, reply_markup=button
                )
            else:
                session.delete(result)
        return


def stk_pack_name(link: str) -> str:
    if match := re.search(r"([^/]+)$", link):
        return match[1]


@Client.on_inline_query(filters.regex("^clear") & is_admin())
@logger.catch()
async def clear_sticker(_, inline_query: InlineQuery):
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
async def start_clear_sticker(_, chosen: ChosenInlineResult):
    with DBSession.begin() as session:
        # 删除自动索引
        stmt = select(AutoIndexSticker).filter(
            AutoIndexSticker.uid == chosen.from_user.id,
        )
        result_a = session.execute(stmt).scalars().all()

        # 删除贴纸
        stmt = select(Sticker).filter(Sticker.uid == chosen.from_user.id)
        result_b = session.execute(stmt).scalars().all()

        # 删除最近使用
        stmt = select(RecentlyUsed).filter(RecentlyUsed.uid == chosen.from_user.id)
        result_c = session.execute(stmt).scalars().all()
        [session.delete(s) for s in result_a + result_b + result_c]

        del stmt, result_a, result_b
    return
