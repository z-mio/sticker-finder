from typing import Any

from pyrogram import Client, filters
from pyrogram.types import Update

from core.config import bs


async def _is_admin(_: object, __: Client, update: Update) -> bool:
    """管理员过滤, ADMINS 为空时所有人可用"""
    from_user = getattr(update, "from_user", None)
    return from_user is not None and (not bs.admins or from_user.id in bs.admins)


is_admin = filters.create(_is_admin)


def filter_inline_query_results(command: str) -> filters.Filter:
    """
    过滤指定字符开头的内联查询结果

    :param command:
    :return:
    """

    async def func(_: object, __: Client, update: Any) -> bool:
        return bool(update.query.startswith(command))

    return filters.create(func, name="InlineQueryResultFilter", commands=command)
