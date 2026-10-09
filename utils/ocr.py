import asyncio
from pathlib import Path
from typing import cast

import httpx
import translators as ts
from rapidocr_onnxruntime import RapidOCR

# 最优组合为：
# ch_PP-OCRv3_det + ch_ppocr_mobile_v2.0_cls + ch_PP-OCRv3_rec
# 和v4速度相差不大，文字检测不如v4

rapid_ocr = RapidOCR()


async def ocr_rapid(path: str | Path) -> list[str]:
    result, _ = await asyncio.to_thread(rapid_ocr, path, text_score=0.4, use_angle_cls=False)
    return [i[1] for i in result] if result else []


async def azure_img_tag(path: str | Path) -> list:
    params = {
        "features": "tags",
        "language": "zh",
    }
    async with httpx.AsyncClient() as client:
        with open(path, "rb") as f:
            data = {"file": f}
            response = await client.post(
                "https://portal.vision.cognitive.azure.com/api/demo/analyze",
                params=params,
                files=data,
            )
        if response.status_code == 200:
            response = response.json()
        else:
            return []
        return [i["name"] for i in response["tagsResult"]["values"]]


# 微软试用接口 图片标题
async def azure_img_caption(path: str | Path) -> str:
    params = {
        "features": "caption",
        "language": "en",
    }
    async with httpx.AsyncClient() as client:
        with open(path, "rb") as f:
            data = {"file": f}
            response = await client.post(
                "https://portal.vision.cognitive.azure.com/api/demo/analyze",
                params=params,
                files=data,
            )
        if response.status_code == 200:
            response = response.json()
        else:
            raise Exception("识别失败")
        text: str = response["captionResult"]["text"]
        try:
            text = cast(str, await asyncio.to_thread(ts.translate_text, text, "google", to_language="zh"))
        except Exception:
            pass
        return text
