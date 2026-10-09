from sqlalchemy import INTEGER, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class IngestJob(Base):
    # 一次添加操作
    __tablename__ = "IngestJob"

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True)
    kind: Mapped[str]  # "single" | "pack" | "auto"
    uid: Mapped[int] = mapped_column(index=True)
    set_name: Mapped[str]
    title: Mapped[str | None]
    chat_id: Mapped[int | None]  # 进度/结果消息, auto 为 None
    message_id: Mapped[int | None]
    total: Mapped[int]
    done: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    stopped: Mapped[bool] = mapped_column(default=False)
    auto_index_id: Mapped[int | None]  # kind=auto: AutoIndexSticker.id
    target_hash: Mapped[int | None]  # kind=auto: 成功后写回的 hash
    created_at: Mapped[float]


class IngestTask(Base):
    # 一张贴纸, id 自增即 FIFO 顺序
    __tablename__ = "IngestTask"
    __table_args__ = (
        UniqueConstraint("uid", "file_unique_id", name="uix_task_uid_sticker"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(INTEGER, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("IngestJob.id", ondelete="CASCADE"), index=True)
    uid: Mapped[int]
    file_id: Mapped[str]
    file_unique_id: Mapped[str]
    mime_type: Mapped[str | None]
    emoji: Mapped[str | None]
    set_name: Mapped[str]
    date: Mapped[int]
    attempts: Mapped[int] = mapped_column(default=0)  # 识别失败重试次数
