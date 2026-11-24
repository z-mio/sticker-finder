import asyncio
import contextlib
from typing import Any

from pyrogram import Client
from pyrogram.types import BotCommand

from core.config import bs
from db.engine import close_db
from db.init import init_db
from log import logger, setup_logging
from plugins.helpers import COMMANDS
from services.auto_index import auto_index_loop
from services.task_queue import task_queue

setup_logging(debug=bs.debug)


class Bot(Client):
    def __init__(self) -> None:
        super().__init__(
            bs.bot_session_name,
            api_id=bs.api_id,
            api_hash=bs.api_hash,
            bot_token=bs.bot_token,
            plugins={"root": "plugins"},
            proxy=bs.bot_proxy,
            workdir=bs.bot_workdir,
            lang_code="zh",
        )
        self._auto_index_task: asyncio.Task[None] | None = None

    async def start(self, **kwargs: Any) -> Client:
        logger.info("初始化数据库...")
        await init_db()
        await super().start(**kwargs)
        self._auto_index_task = asyncio.create_task(auto_index_loop(self))
        await task_queue.start(self)
        await self.set_menu()
        return self

    async def stop(self, *args: Any, **kwargs: Any) -> Client:
        if self._auto_index_task is not None:
            self._auto_index_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._auto_index_task
            self._auto_index_task = None
        await task_queue.stop()
        await super().stop(*args, **kwargs)
        await close_db()
        return self

    async def set_menu(self) -> None:
        commands = await self.get_bot_commands()
        if len(commands) == len(COMMANDS) and all(c.description in str(COMMANDS.values()) for c in commands):
            logger.debug("菜单无变化, 跳过设置")
            return
        await self.set_bot_commands([BotCommand(command=k, description=v) for k, v in COMMANDS.items()])
        logger.debug(f"菜单已设置: {COMMANDS}")


if __name__ == "__main__":
    bot = Bot()
    bot.run()
