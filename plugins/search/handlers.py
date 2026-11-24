from pyrogram import Client
from pyrogram.types import (
    ChosenInlineResult,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResult,
    InlineQueryResultArticle,
    InlineQueryResultCachedSticker,
    InputTextMessageContent,
)

from db import get_session
from log import logger
from plugins.filters import is_admin, is_inline_command
from services.sticker import StickerService
from utils.telegram import get_sticker_id

PAGE_SIZE = 15

_ICON_HISTORY_FILE_ID = "CAACAgUAAxkBAAEWiBtk_Tl-PGEw5cHrX1fvPxAhl6peTQACPQsAAuTA6FfdYfY8HDl01zAE"
_ICON_ALL_FILE_ID = "CAACAgUAAxkBAAEWiBlk_TlzPMQ_kUYHH5Eb9yGHdjfMYwACnwwAAgVq6Vc1hkbCLtDWpDAE"


@Client.on_inline_query(is_admin & ~is_inline_command)
@logger.catch()
async def find_sticker(_: Client, inline_query: InlineQuery) -> None:
    query = "%".join(inline_query.query.split(" "))
    await load_sticker(inline_query, query)


def _icon_result(result_id: str, sticker_file_id: str, text: str) -> InlineQueryResultCachedSticker:
    return InlineQueryResultCachedSticker(
        sticker_file_id=sticker_file_id,
        id=result_id,
        input_message_content=InputTextMessageContent(text),
    )


async def load_sticker(
    inline_query: InlineQuery, query: str | None, button: InlineKeyboardMarkup | None = None
) -> None:
    offset = int(inline_query.offset or 0)  # 开始
    uid = inline_query.from_user.id
    async with get_session() as session:
        service = StickerService(session)
        # 多查一条判断是否有下一页
        result = list(await service.search_page(uid, query, offset, PAGE_SIZE + 1))
        recently = list(await service.list_existing_history(uid)) if offset == 0 and not query else []
    has_more = len(result) > PAGE_SIZE
    stickers = result[:PAGE_SIZE]
    next_offset = str(offset + PAGE_SIZE) if has_more else ""

    if stickers or offset:
        results: list[InlineQueryResult] = []
        # 只在第一页显示历史记录: icon_history, 最近使用的贴纸(新→旧), icon_all
        if offset == 0 and not query:
            results.append(_icon_result("icon_history", _ICON_HISTORY_FILE_ID, "最近使用"))
            results.extend(
                InlineQueryResultCachedSticker(
                    sticker_file_id=i.sticker_id,
                    id=f"r_{i.sticker_unique_id}",
                    reply_markup=button,
                )
                for i in reversed(recently)
            )
            results.append(_icon_result("icon_all", _ICON_ALL_FILE_ID, "全部贴纸"))
        results.extend(
            InlineQueryResultCachedSticker(
                sticker_file_id=i.sticker_id,
                id=f"a_{i.sticker_unique_id}",
                reply_markup=button,
            )
            for i in stickers
        )
        await inline_query.answer(
            results=results,
            is_gallery=True,
            cache_time=1,
            next_offset=next_offset,
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


# 最近使用
@Client.on_chosen_inline_result(~is_inline_command)
@logger.catch()
async def stickers_used(_: Client, chosen: ChosenInlineResult) -> None:
    if chosen.result_id.startswith("icon"):
        return
    async with get_session() as session:
        await StickerService(session).record_use(chosen.from_user.id, get_sticker_id(chosen.result_id))
