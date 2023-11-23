import time

from loguru import logger
from pyrogram import Client
from pyrogram.types import ChosenInlineResult
from sqlalchemy import select

from database import DBSession, RecentlyUsed, Sticker
from utils import get_sticker_id


# 最近使用
@Client.on_chosen_inline_result()
@logger.catch()
async def stickers_used(_, chosen: ChosenInlineResult):
    if chosen.result_id.startswith("icon"):
        return
    with DBSession.begin() as session:
        stmt = select(Sticker).filter(
            Sticker.sticker_unique_id == get_sticker_id(chosen.result_id),
            Sticker.uid == chosen.from_user.id,
        )
        if result := session.execute(stmt).scalars().first():
            result.usage_count += 1

        # 如果历史记录已存在，就更新使用时间
        stmt = select(RecentlyUsed).filter(
            RecentlyUsed.uid == chosen.from_user.id,
            RecentlyUsed.sticker_unique_id == get_sticker_id(chosen.result_id),
        )
        if sb := session.execute(stmt).scalars().first():
            sb.time = time.time()
            return
        limited_quantity = 19
        # 获取最近使用，超过x条，就删除x之前的
        stmt = (
            select(RecentlyUsed)
            .filter(RecentlyUsed.uid == chosen.from_user.id)
            .order_by(RecentlyUsed.time.desc())
        )
        sb_count = session.execute(stmt).scalars().all()

        # 最近使用默认限制19条
        [
            session.delete(sb_count[-1 + -i])
            for i, _ in enumerate(sb_count)
            if len(sb_count[i:]) >= limited_quantity
        ]

        stk = RecentlyUsed(
            uid=result.uid,
            sticker_id=result.sticker_id,
            sticker_unique_id=result.sticker_unique_id,
            time=time.time(),
        )
        session.add(stk)
    del stmt, sb_count, stk, session, result
    return
