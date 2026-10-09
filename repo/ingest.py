from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, cast

from sqlalchemy import delete, exists, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.ingest import IngestJob, IngestTask

if TYPE_CHECKING:
    from services.ingest import StickerSource


class IngestRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(self, **fields: Any) -> IngestJob:
        job = IngestJob(**fields)
        self._session.add(job)
        await self._session.flush()
        return job

    async def get_job(self, job_id: int) -> IngestJob | None:
        return cast(IngestJob | None, await self._session.get(IngestJob, job_id))

    # 批量加任务, 跳过 (uid, file_unique_id) 已在队列里的, 返回新任务 id
    async def add_tasks(self, job_id: int, uid: int, sources: Sequence[StickerSource]) -> list[int]:
        unique_ids = [s.file_unique_id for s in sources]
        stmt = select(IngestTask.file_unique_id).where(IngestTask.uid == uid, IngestTask.file_unique_id.in_(unique_ids))
        existing = set((await self._session.scalars(stmt)).all())
        ids = []
        for s in sources:
            if s.file_unique_id in existing:
                continue
            task = IngestTask(
                job_id=job_id,
                uid=uid,
                file_id=s.file_id,
                file_unique_id=s.file_unique_id,
                mime_type=s.mime_type,
                emoji=s.emoji,
                set_name=s.set_name,
                date=s.date,
            )
            self._session.add(task)
            await self._session.flush()
            ids.append(task.id)
        return ids

    async def list_pending_ids(self) -> Sequence[int]:
        stmt = select(IngestTask.id).order_by(IngestTask.id)
        return (await self._session.scalars(stmt)).all()

    async def get_task(self, task_id: int) -> IngestTask | None:
        return cast(IngestTask | None, await self._session.get(IngestTask, task_id))

    async def delete_task(self, task_id: int) -> None:
        await self._session.execute(delete(IngestTask).where(IngestTask.id == task_id))

    # 原子累加 done/failed
    async def inc_counter(self, job_id: int, failed: bool = False) -> None:
        col = IngestJob.failed if failed else IngestJob.done
        await self._session.execute(update(IngestJob).where(IngestJob.id == job_id).values({col: col + 1}))

    async def delete_pending_tasks(self, job_id: int) -> None:
        await self._session.execute(delete(IngestTask).where(IngestTask.job_id == job_id))

    async def has_active_job(self, uid: int, kind: str) -> bool:
        stmt = select(exists().where(IngestJob.uid == uid, IngestJob.kind == kind))
        return bool(await self._session.scalar(stmt))

    async def has_active_auto_job(self, auto_index_id: int) -> bool:
        stmt = select(exists().where(IngestJob.auto_index_id == auto_index_id))
        return bool(await self._session.scalar(stmt))

    async def delete_jobs_by_uid(self, uid: int) -> None:
        await self._session.execute(delete(IngestJob).where(IngestJob.uid == uid))

    async def delete_jobs(self, uid: int, set_name: str) -> None:
        await self._session.execute(delete(IngestJob).where(IngestJob.uid == uid, IngestJob.set_name == set_name))

    # 标记用户的进行中的 job 为停止
    async def stop_active_job(self, uid: int, kind: str) -> IngestJob | None:
        stmt = select(IngestJob).where(IngestJob.uid == uid, IngestJob.kind == kind).limit(1)
        job = cast(IngestJob | None, await self._session.scalar(stmt))
        if job is not None:
            job.stopped = True
        return job

    # 任务清空时删除 job 并返回它, 并发下只有一个调用会成功
    async def finalize_job(self, job_id: int) -> IngestJob | None:
        job = await self.get_job(job_id)
        stmt = delete(IngestJob).where(
            IngestJob.id == job_id,
            ~exists().where(IngestTask.job_id == job_id),
        )
        result = cast(CursorResult[Any], await self._session.execute(stmt))
        return job if result.rowcount == 1 else None
