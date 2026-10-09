from pathlib import Path

from alembic.config import Config
from sqlalchemy.engine import Connection

import db.models  # noqa: F401
from alembic import command
from db.base import Base
from db.session import engine


def upgrade_head(connection: Connection) -> None:
    # 使用绝对路径, 不依赖运行目录
    alembic_cfg = Config(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
    alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(upgrade_head)
