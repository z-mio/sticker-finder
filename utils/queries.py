from sqlalchemy import or_, select

from core.database import AutoIndexSticker, DBSession, RecentlyUsed, Sticker


# 获取自动索引的贴纸包
def get_auto_indexed_packages(set_name: str, uid: int) -> AutoIndexSticker | None:
    with DBSession.begin() as session:
        stmt = select(AutoIndexSticker).filter(AutoIndexSticker.uid == uid, AutoIndexSticker.set_name == set_name)
        return session.execute(stmt).scalars().one_or_none()


def stick_find(query: str | None, uid: int) -> list[Sticker]:
    if query:
        stmt = select(Sticker).filter(
            or_(
                Sticker.tag.ilike(f"%{query}%"),
                Sticker.emoji.ilike(f"%{query}%"),
                Sticker.title.ilike(f"%{query}%"),
                Sticker.set_name == query,
                Sticker.sticker_unique_id == query,
            ),
            Sticker.uid == uid,
        )
    else:
        stmt = select(Sticker).filter(Sticker.uid == uid)
    # 按贴纸包名和emoji升序排序
    stmt_asc = stmt.order_by(Sticker.set_name.asc(), Sticker.time.asc())
    with DBSession() as session:
        return list(session.execute(stmt_asc).scalars().all())


def recently_used_find(uid: int) -> list[RecentlyUsed]:
    stmt = select(RecentlyUsed).filter(RecentlyUsed.uid == uid).order_by(RecentlyUsed.time.asc())
    with DBSession() as session:
        return list(session.execute(stmt).scalars().all())
