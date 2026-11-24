"""plugins 共用的命令表和内联按钮构建"""

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db import get_session
from services.auto_index import AutoIndexService

COMMANDS = {
    "start": "开始",
    "help": "帮助",
}


async def build_auto_index_button(set_name: str, uid: int) -> InlineKeyboardButton:
    async with get_session() as session:
        enabled = await AutoIndexService(session).is_enabled(uid, set_name)
    return InlineKeyboardButton(f"自动索引新贴纸{'✅' if enabled else '❎'}", callback_data=f"auto_index_{set_name}")


def pack_buttons(set_name: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton("查看贴纸包", switch_inline_query_current_chat=set_name),
        InlineKeyboardButton(
            "编辑贴纸包", switch_inline_query_current_chat=f"edit https://t.me/addstickers/{set_name}\000"
        ),
        InlineKeyboardButton(
            "删除贴纸包", switch_inline_query_current_chat=f"del https://t.me/addstickers/{set_name}\000"
        ),
    ]


def sticker_info_text(stk: dict) -> str:
    return (
        f"✅添加成功!\n**标签：**`{stk['tag']}`\n**Emoji：**`{stk['emoji']}`\n"
        f"**贴纸包：**`{stk['title']}` | `{stk['set_name']}`"
    )


def single_sticker_buttons(stk: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "编辑标签", switch_inline_query_current_chat=f"edit {stk['sticker_unique_id']}\000"
                ),
                InlineKeyboardButton(
                    "删除贴纸", switch_inline_query_current_chat=f"del {stk['sticker_unique_id']}\000"
                ),
            ],
            [
                InlineKeyboardButton(
                    "编辑贴纸包",
                    switch_inline_query_current_chat=f"edit https://t.me/addstickers/{stk['set_name']}\000",
                ),
                InlineKeyboardButton(
                    "删除贴纸包",
                    switch_inline_query_current_chat=f"del https://t.me/addstickers/{stk['set_name']}\000",
                ),
            ],
        ]
    )
