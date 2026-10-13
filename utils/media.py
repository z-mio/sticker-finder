import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import cv2
from pyrogram import Client
from rlottie_python import LottieAnimation

from core.config import bs


def _tmp(suffix: str) -> Path:
    return bs.downloads_path / f"{uuid.uuid4().hex}{suffix}"


def _extract_first_frame(i_p: Path, o_p: Path) -> None:
    video = cv2.VideoCapture(str(i_p))
    try:
        ok, image = video.read()
    finally:
        video.release()
    if not ok:
        raise ValueError("无法读取视频首帧")
    cv2.imwrite(str(o_p), image)


def _render_tgs_first_frame(i_p: Path, o_p: Path) -> None:
    with LottieAnimation.from_tgs(str(i_p)) as anim:
        anim.save_frame(str(o_p), frame_num=0)


# 下载贴纸并转成单张静态图片, 退出时删除全部临时文件
@asynccontextmanager
async def sticker_to_image(client: Client, file_id: str, mime_type: str) -> AsyncIterator[Path]:
    suffix = {"video/webm": ".webm", "application/x-tgsticker": ".tgs"}.get(mime_type, ".webp")
    i_p = _tmp(suffix)
    o_p: Path | None = None
    try:
        await client.download_media(file_id, str(i_p))
        if mime_type == "video/webm":
            o_p = _tmp(".png")
            await asyncio.to_thread(_extract_first_frame, i_p, o_p)
            yield o_p
        elif mime_type == "application/x-tgsticker":
            o_p = _tmp(".png")
            await asyncio.to_thread(_render_tgs_first_frame, i_p, o_p)
            yield o_p
        else:
            yield i_p
    finally:
        i_p.unlink(missing_ok=True)
        if o_p is not None:
            o_p.unlink(missing_ok=True)
