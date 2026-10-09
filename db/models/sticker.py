from sqlalchemy import INTEGER, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Sticker(Base):
    # 表的名字
    __tablename__ = "sticker"

    # 表的结构
    id: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    uid: Mapped[int]  # 用户id
    tag: Mapped[str]  # 标签
    sticker_id: Mapped[str]  # 贴纸文件id
    sticker_unique_id: Mapped[str]  # 贴纸唯一id
    sticker_type: Mapped[str]  # 贴纸类型 image/webp | video/webm | application/x-tgsticker
    emoji: Mapped[str]  # 贴纸的emoji
    set_name: Mapped[str]  # 贴纸包名
    title: Mapped[str]  # 贴纸包标题
    usage_count: Mapped[int]  # 贴纸使用次数
    time: Mapped[int]  # 添加时间

    # 复合唯一约束
    __table_args__ = (UniqueConstraint("uid", "sticker_unique_id", name="uix_uid_sticker"),)
