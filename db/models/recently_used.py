from sqlalchemy import INTEGER, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


# 最近使用
class RecentlyUsed(Base):
    # 表的名字
    __tablename__ = "RecentlyUsed"

    # 表的结构
    id: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    uid: Mapped[int]  # 用户id
    sticker_id: Mapped[str]  # 贴纸文件id
    sticker_unique_id: Mapped[str]  # 贴纸唯一id
    time: Mapped[int]  # 添加时间

    # 复合唯一约束
    __table_args__ = (UniqueConstraint("uid", "sticker_unique_id", name="uix_uid_sticker"),)
