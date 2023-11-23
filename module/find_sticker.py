from loguru import logger
from pyrogram import Client
from pyrogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InlineQueryResultCachedSticker,
    InputTextMessageContent,
)

from utils import is_admin, recently_used_find, stick_find


@Client.on_inline_query(is_admin())
@logger.catch()
async def find_sticker(_, inline_query: InlineQuery):
    query = "%".join(inline_query.query.split(" "))
    await load_sticker(inline_query, query)


async def load_sticker(inline_query, query, button=None):
    offset = inline_query.offset or 0  # 开始
    if result := stick_find(query, inline_query.from_user.id):
        next_offset = int(offset) + 15  # 结束
        results = [
            InlineQueryResultCachedSticker(
                sticker_file_id=i.sticker_id,
                id=f"a_{i.sticker_unique_id}",
                reply_markup=button,
            )
            for i in result[int(offset) : next_offset]
        ]

        # 只在第一页显示历史记录
        if not int(offset) and not query:
            recently = recently_used_find(inline_query.from_user.id)
            results.insert(
                0,
                InlineQueryResultCachedSticker(
                    sticker_file_id="CAACAgUAAxkBAAEWiBlk_TlzPMQ_kUYHH5Eb9yGHdjfMYwACnwwAAgVq6Vc1hkbCLtDWpDAE",
                    id="icon_all",
                    input_message_content=InputTextMessageContent("全部贴纸"),
                ),
            )

            for i in recently:
                r = InlineQueryResultCachedSticker(
                    sticker_file_id=i.sticker_id,
                    id=f"r_{i.sticker_unique_id}",
                    reply_markup=button,
                )
                results.insert(0, r)

            results.insert(
                0,
                InlineQueryResultCachedSticker(
                    sticker_file_id="CAACAgUAAxkBAAEWiBtk_Tl-PGEw5cHrX1fvPxAhl6peTQACPQsAAuTA6FfdYfY8HDl01zAE",
                    id="icon_history",
                    input_message_content=InputTextMessageContent("最近使用"),
                ),
            )
        await inline_query.answer(
            results=results,
            is_gallery=True,
            cache_time=1,
            next_offset=str(next_offset),
            switch_pm_text="点击跳转到bot",
            switch_pm_parameter="pm",
        )
    else:
        await inline_query.answer(
            results=[
                InlineQueryResultArticle(
                    "未搜索到贴纸",
                    description="给bot发送贴纸来添加",
                    input_message_content=InputTextMessageContent("给bot发送贴纸来添加"),
                )
            ],
            cache_time=1,
            switch_pm_text="点击跳转到bot",
            switch_pm_parameter="pm",
        )
