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
from sqlalchemy import update

from database import DBSession, Sticker
from module.find_sticker import load_sticker
from utils import filter_inline_query_results, get_sticker_id, is_admin

NEW_TAG = {}


# 编辑贴纸关键词
@Client.on_inline_query(
    filters.regex(r"^edit(?!.*https://t\.me/addstickers/\w*).*$") & is_admin()
)
@logger.catch()
async def edit_sticker(_, inline_query: InlineQuery):
    edit_query = re.sub(r"edit:|edit\s|edit", "", inline_query.query, 1)
    edit_query = edit_query.split(" ")

    # @bot edit 新标签
    if len(edit_query) == 1:
        query = None
        new_tag = edit_query[0]
        if new_tag == "":
            return await load_sticker(inline_query, query)
    # @bot edit 旧标签 新标签
    else:
        query = edit_query[0]
        new_tag = edit_query[1]

    button = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"新标签：{new_tag}", switch_inline_query_current_chat=new_tag
                )
            ]
        ]
    )
    await load_sticker(inline_query, query, button)

    NEW_TAG[inline_query.from_user.id] = new_tag


# 匹配贴纸包
@Client.on_inline_query(
    filters.regex(r"^edit[\s\S]*(https://t.me/addstickers/\w+)") & is_admin()
)
@logger.catch()
async def edit_sticker_pack(_, inline_query: InlineQuery):
    edit_query = re.sub(r"edit:|edit\s|edit", "", inline_query.query, 1).split(" ")
    if new_tag := edit_query[1:]:
        new_tag = "".join(new_tag)
        NEW_TAG[inline_query.from_user.id] = new_tag

        # 新标签加入字典，set_name加入内联结果id
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    title="点击修改包名",
                    id=edit_query[0].replace("https://t.me/addstickers/", ""),
                    description=new_tag,
                    input_message_content=InputTextMessageContent(f"新贴纸包名：{new_tag}"),
                )
            ]
        )
    else:
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    title="请输入新贴纸包名",
                    description="格式：@bot edit 贴纸包链接 新贴纸包名",
                    input_message_content=InputTextMessageContent(
                        "格式：@bot edit 贴纸包链接 新贴纸包名"
                    ),
                )
            ]
        )


@Client.on_chosen_inline_result(filter_inline_query_results("edit"))
@logger.catch()
async def edit_tag(_, chosen: ChosenInlineResult):
    new_tag = NEW_TAG.get(chosen.from_user.id)
    if not new_tag:
        return
    NEW_TAG.pop(chosen.from_user.id)
    with DBSession.begin() as session:
        # 更改贴纸包标题
        if "https://t.me/addstickers/" in chosen.query:
            stmt = (
                update(Sticker)
                .filter(
                    Sticker.set_name == chosen.result_id,
                    Sticker.uid == chosen.from_user.id,
                )
                .values(title=new_tag)
            )

        # 更新标签
        else:
            stmt = (
                update(Sticker)
                .filter(
                    Sticker.sticker_unique_id == get_sticker_id(chosen.result_id),
                    Sticker.uid == chosen.from_user.id,
                )
                .values(tag=new_tag)
            )

        session.execute(stmt)
    del session, new_tag, stmt
    return
