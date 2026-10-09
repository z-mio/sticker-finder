from sqlalchemy import INTEGER
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AutoIndexSticker(Base):
    # 表的名字
    __tablename__ = "AutoIndexSticker"

    # 表的结构
    id: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    uid: Mapped[int]  # 用户id
    set_name: Mapped[str]  # 贴纸包名
