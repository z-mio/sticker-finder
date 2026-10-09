import asyncio
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

# 最优组合为：
# ch_PP-OCRv3_det + ch_ppocr_mobile_v2.0_cls + ch_PP-OCRv3_rec
# 和v4速度相差不大，文字检测不如v4

rapid_ocr = RapidOCR()


async def ocr_rapid(path: str | Path) -> list[str]:
    result, _ = await asyncio.to_thread(rapid_ocr, path, text_score=0.4, use_angle_cls=False)
    return [i[1] for i in result] if result else []
