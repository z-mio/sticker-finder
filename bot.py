import asyncio
from typing import Any

from pyrogram import Client
from pyrogram.handlers import ConnectHandler, DisconnectHandler
from pyrogram.types import BotCommand

from core.config import bs, ws
from core.scheduler import scheduler
from core.watchdog import on_connect, on_disconnect
from db.engine import close_db
from db.init import init_db
from log import logger, setup_logging
from plugins.auto_index import scheduled_indexing_tasks
from utils.event_loop import setup_optimized_event_loop

setup_logging(debug=bs.debug)

setup_optimized_event_loop()
loop = asyncio.new_event_loop()

COMMANDS = {
    "start": "开始",
    "help": "帮助",
}


class Bot(Client):
    def __init__(self) -> None:
        super().__init__(
            bs.bot_session_name,
            api_id=bs.api_id,
            api_hash=bs.api_hash,
            bot_token=bs.bot_token,
            plugins={"root": "plugins"},
            proxy=bs.bot_proxy,
            loop=loop,
            workdir=bs.bot_workdir,
            lang_code="zh",
        )

    async def start(self, **kwargs: Any) -> Client:
        self.init_watchdog()
        logger.info("初始化数据库...")
        await init_db()
        await super().start(**kwargs)
        scheduler.start()
        scheduled_indexing_tasks(self)
        await self.set_menu()
        return self

    async def stop(self, *args: Any, **kwargs: Any) -> Client:
        ws.exit_flag = True
        if scheduler.running:
            scheduler.shutdown()
        await super().stop(*args, **kwargs)
        await close_db()
        return self

    def init_watchdog(self) -> None:
        self.add_handler(ConnectHandler(on_connect))
        self.add_handler(DisconnectHandler(on_disconnect))

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
