from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from db.models.auto_index import AutoIndexSticker
from repo.auto_index import AutoIndexRepo


class AutoIndexService:
    def __init__(self, session: AsyncSession) -> None:
        self.auto_index = AutoIndexRepo(session)

    # 切换自动索引, 返回切换后的开启状态
    async def toggle(self, uid: int, set_name: str) -> bool:
        if record := await self.auto_index.get(uid, set_name):
            await self.auto_index.remove(record)
            return False
        await self.auto_index.add(uid, set_name)
        return True

    async def is_enabled(self, uid: int, set_name: str) -> bool:
        return await self.auto_index.get(uid, set_name) is not None

    async def list(self) -> Sequence[AutoIndexSticker]:
        return await self.auto_index.list_all()

    async def update_hash(self, record_id: int, new_hash: int) -> None:
        await self.auto_index.update_hash(record_id, new_hash)
