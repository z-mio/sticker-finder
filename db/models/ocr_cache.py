from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class OcrCache(Base):
    # 表的名字
    __tablename__ = "OcrCache"

    # 表的结构
    sticker_unique_id: Mapped[str] = mapped_column(primary_key=True)
    tag: Mapped[str]  # OCR 识别出的标签
