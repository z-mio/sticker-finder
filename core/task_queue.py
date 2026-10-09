import asyncio
import contextlib
import os
import time
from typing import Any

from pyrogram import Client
from pyrogram.errors import RPCError
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from db import get_session
from db.models.ingest import IngestJob
from log import logger
from repo.ingest import IngestRepo
from services.ingest import _SUPPORTED_MIME, StickerSource, insert_sticker

WORKERS = min(32, (os.cpu_count() or 1) + 4)
MAX_RETRIES = 3
RETRY_DELAYS = (15, 30, 60)


# 全局任务队列, 贴纸识别任务统一排队
class TaskQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._retry_handles: list[asyncio.TimerHandle] = []
        self._client: Client | None = None

    async def start(self, client: Client) -> None:
        self._client = client
        async with get_session() as session:
            pending = await IngestRepo(session).list_pending_ids()
        for task_id in pending:
            self._queue.put_nowait(task_id)
        self._workers = [asyncio.create_task(self._worker()) for _ in range(WORKERS)]
        if pending:
            logger.info(f"任务队列: 恢复 {len(pending)} 个未完成任务")

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        for w in self._workers:
            with contextlib.suppress(asyncio.CancelledError):
                await w
        self._workers = []
        for h in self._retry_handles:
            h.cancel()
        self._retry_handles = []

    # 提交一个 job 及其任务, 返回 job_id; 全是重复任务时直接完成
    async def submit(self, job_fields: dict[str, Any], sources: list[StickerSource]) -> int:
        async with get_session() as session:
            repo = IngestRepo(session)
            job = await repo.create_job(**job_fields)
            task_ids = await repo.add_tasks(job.id, job.uid, sources)
            job_id = job.id
        for task_id in task_ids:
            self._queue.put_nowait(task_id)
        if not task_ids:
            await self.finalize(job_id, None, job_fields["kind"] == "single")
        return job_id

    # 任务清空时删除 job 并发送完成消息, 并发下只有一个调用生效
    # dup_single: kind=single 且 0 个任务入队(贴纸已在别的任务里)
    async def finalize(self, job_id: int, result: dict | None = None, dup_single: bool = False) -> None:
        async with get_session() as session:
            job = await IngestRepo(session).finalize_job(job_id)
        if job is None:
            return
        await self._send_final(job, result, dup_single)

    async def _worker(self) -> None:
        while True:
            task_id = await self._queue.get()
            try:
                await self._process(task_id)
            except Exception:
                logger.exception(f"队列任务 {task_id} 处理失败")
                # 意外错误计为失败并删除任务, 避免卡死队列
                job_id = None
                async with get_session() as session:
                    repo = IngestRepo(session)
                    task = await repo.get_task(task_id)
                    if task is not None:
                        await repo.delete_task(task_id)
                        await repo.inc_counter(task.job_id, failed=True)
                        job_id = task.job_id
                if job_id is not None:
                    await self.finalize(job_id)
            finally:
                self._queue.task_done()

    async def _process(self, task_id: int) -> None:
        assert self._client is not None
        async with get_session() as session:
            repo = IngestRepo(session)
            task = await repo.get_task(task_id)
            if task is None:
                # 已停止或被清理
                return
            job = await repo.get_job(task.job_id)
            if job is None:
                await repo.delete_task(task_id)
                return
            source = StickerSource(
                file_id=task.file_id,
                file_unique_id=task.file_unique_id,
                mime_type=task.mime_type,
                emoji=task.emoji,
                set_name=task.set_name,
                date=task.date,
            )
            job_id, uid, kind, title = job.id, task.uid, job.kind, job.title

        errored = False
        try:
            result, is_new = await insert_sticker(self._client, uid, source, title)
        except Exception:
            logger.exception(f"贴纸 {source.file_unique_id} 入库失败")
            result, is_new = None, False
            errored = True

        # 识别失败回队尾重试(限可识别格式), 超过 MAX_RETRIES 才计失败
        if not errored and result is None and source.mime_type in _SUPPORTED_MIME:
            async with get_session() as session:
                repo = IngestRepo(session)
                task = await repo.get_task(task_id)
                if task is not None and task.attempts < MAX_RETRIES:
                    task.attempts += 1
                    delay = RETRY_DELAYS[task.attempts - 1]
                    handle = asyncio.get_running_loop().call_later(delay, self._queue.put_nowait, task_id)
                    self._retry_handles.append(handle)
                    logger.info(f"贴纸 {source.file_unique_id} 识别失败, {delay}s 后重试(第 {task.attempts} 次)")
                    return

        async with get_session() as session:
            repo = IngestRepo(session)
            await repo.delete_task(task_id)
            await repo.inc_counter(job_id, failed=result is None)
            job = await repo.get_job(job_id)
            if job is not None:
                await session.refresh(job)
        if job is None:
            return

        # auto: 新插入的贴纸发送索引通知, 通知失败不影响计数
        if kind == "auto" and is_new and result is not None:
            await self._send_auto_notice(uid, job, source, result)
        # pack: 每 5 个更新一次进度消息
        if kind == "pack" and job.chat_id and job.message_id and (job.done + job.failed) % 5 == 0:
            await self._edit_progress(job)

        await self.finalize(job_id, result)

    async def _send_auto_notice(self, uid: int, job: IngestJob, source: StickerSource, result: dict) -> None:
        assert self._client is not None
        button = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        f"标签：{result['tag']}",
                        switch_inline_query_current_chat=f"{result['sticker_unique_id']}",
                    )
                ],
                [InlineKeyboardButton("新贴纸|已自动索引", url=f"t.me/addstickers/{job.set_name}")],
            ]
        )
        try:
            await self._client.send_sticker(chat_id=uid, sticker=source.file_id, reply_markup=button)
        except RPCError as e:
            logger.warning(f"自动索引通知发送失败: {e}")

    async def _edit_progress(self, job: IngestJob) -> None:
        assert self._client is not None
        markup = InlineKeyboardMarkup(
            [_pack_buttons(job.set_name), [InlineKeyboardButton("停止添加", callback_data="sticker_stop")]]
        )
        try:
            await self._client.edit_message_text(
                int(job.chat_id),  # type: ignore[arg-type]
                int(job.message_id),  # type: ignore[arg-type]
                f"正在添加贴纸包，请稍等|{job.done + job.failed}/{job.total}",
                reply_markup=markup,
            )
        except RPCError as e:
            logger.debug(f"进度消息更新失败: {e}")

    async def _send_final(self, job: IngestJob, result: dict | None, dup_single: bool = False) -> None:
        assert self._client is not None
        if job.kind == "single":
            if result is not None:
                from plugins.auto_index import build_auto_index_button

                button = _single_buttons(result)
                button.inline_keyboard.append([await build_auto_index_button(str(result["set_name"]), job.uid)])
                await self._edit(job, _info_text(result), button)
            elif dup_single:
                await self._edit(job, "该贴纸已在队列中，请稍候")
            else:
                await self._edit(job, "识别失败，未添加，请稍后重新发送贴纸")
        elif job.kind == "pack":
            if job.stopped:
                await self._edit(job, "已停止添加")
                return
            from plugins.auto_index import build_auto_index_button

            text = f"""
✅完成！
贴纸包: `{job.title or job.set_name}`|`{job.set_name}`
数量: `{job.total}`
耗时: `{time.time() - job.created_at:.2f}s`
"""
            if job.failed:
                text += f"失败: `{job.failed}` 张（识别失败未添加，重新发送链接可补齐）\n"
            markup = InlineKeyboardMarkup(
                [_pack_buttons(job.set_name), [await build_auto_index_button(job.set_name, job.uid)]]
            )
            await self._edit(job, text, markup)
        elif job.kind == "auto":
            # 全部成功才写回 hash, 记录已被删除则忽略
            if job.failed == 0 and not job.stopped and job.auto_index_id is not None and job.target_hash is not None:
                from services.auto_index import AutoIndexService

                async with get_session() as session:
                    await AutoIndexService(session).update_hash_if_exists(job.auto_index_id, job.target_hash)
            if job.failed:
                logger.warning(f"自动索引贴纸包 {job.set_name} 有 {job.failed} 张贴纸识别失败，未更新 hash")

    async def _edit(self, job: IngestJob, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
        assert self._client is not None
        if not job.chat_id or not job.message_id:
            return
        try:
            await self._client.edit_message_text(int(job.chat_id), int(job.message_id), text, reply_markup=markup)
        except RPCError as e:
            logger.debug(f"结果消息发送失败: {e}")


def _pack_buttons(set_name: str) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton("查看贴纸包", switch_inline_query_current_chat=set_name),
        InlineKeyboardButton(
            "编辑贴纸包", switch_inline_query_current_chat=f"edit https://t.me/addstickers/{set_name}\000"
        ),
        InlineKeyboardButton(
            "删除贴纸包", switch_inline_query_current_chat=f"del https://t.me/addstickers/{set_name}\000"
        ),
    ]


def _info_text(stk: dict) -> str:
    return (
        f"✅添加成功!\n**标签：**`{stk['tag']}`\n**Emoji：**`{stk['emoji']}`\n"
        f"**贴纸包：**`{stk['title']}` | `{stk['set_name']}`"
    )


def _single_buttons(stk: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "编辑标签", switch_inline_query_current_chat=f"edit {stk['sticker_unique_id']}\000"
                ),
                InlineKeyboardButton(
                    "删除贴纸", switch_inline_query_current_chat=f"del {stk['sticker_unique_id']}\000"
                ),
            ],
            [
                InlineKeyboardButton(
                    "编辑贴纸包",
                    switch_inline_query_current_chat=f"edit https://t.me/addstickers/{stk['set_name']}\000",
                ),
                InlineKeyboardButton(
                    "删除贴纸包",
                    switch_inline_query_current_chat=f"del https://t.me/addstickers/{stk['set_name']}\000",
                ),
            ],
        ]
    )


task_queue = TaskQueue()
