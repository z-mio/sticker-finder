# -*- coding: UTF-8 -*-
from loguru import logger
from pyrogram import Client

from config.config import (api_hash, api_id, bot_token, hostname, port,
                           scheme)
from module.auto_index import scheduled_indexing_tasks

logger.add("logs/bot.log", rotation="5 MB")

proxy = {
    "scheme": scheme,  # 支持“socks4”、“socks5”和“http”
    "hostname": hostname,
    "port": port
}

plugins = dict(root="module")

app = Client(
    "my_bot", proxy=proxy if all([scheme, hostname, port]) else None, bot_token=bot_token,
    api_id=api_id, api_hash=api_hash, plugins=plugins, lang_code="zh")


def main():
    scheduled_indexing_tasks(app)
    app.run()


if __name__ == '__main__':
    logger.info("Bot运行中...")
    main()
