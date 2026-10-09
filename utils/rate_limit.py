from collections import defaultdict
from collections.abc import Awaitable, Callable
from time import time
from typing import Any

from pyrogram import Client
from pyrogram.types import Message

requests: defaultdict[int, int] = defaultdict(int)
last_request_time: defaultdict[int, int] = defaultdict(int)


# 速率限制
def rate_limit(request_limit: int = 3, time_limit: int = 60) -> Callable:
    def decorator(func: Callable[[Client, Message], Awaitable[Any]]) -> Callable:
        async def wrapper(client: Client, message: Message) -> Message | None:
            assert message.from_user is not None
            user_id = message.from_user.id
            current_time = time()
            if current_time - last_request_time[user_id] > time_limit:
                requests[user_id] = 1
                last_request_time[user_id] = int(current_time)
            else:
                if requests[user_id] >= request_limit:
                    return await message.reply(
                        f"速率限制：{request_limit}张/{time_limit}秒，请稍后再试"
                    )  # 超过限制次数,不处理请求
                requests[user_id] += 1

            await func(client, message)  # 调用原函数
            return None

        return wrapper

    return decorator
