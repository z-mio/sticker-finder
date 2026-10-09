import asyncio
import base64
import io
import unicodedata
from pathlib import Path

from openai import AsyncOpenAI
from PIL import Image

from core.config import bs

client = AsyncOpenAI(
    base_url=bs.ai_base_url,
    api_key=bs.ai_api_key,
    timeout=bs.ai_timeout,
    max_retries=bs.ai_max_retries,
)

_SYSTEM_PROMPT = "你是 Telegram 贴纸标注助手，根据贴纸图片生成用于搜索的标签。"
_USER_PROMPT = (
    "1. 如果图中有文字，逐字写出原文，保持原语言，不要翻译。\n"
    "2. 再给出 3 到 6 个描述画面的中文关键词（角色、动作、表情、情绪等）。\n"
    "只输出一行，所有内容用空格分隔，不要编号、解释或多余标点。"
)


# 任意格式转 PNG base64, 透明背景垫白, 缩到 512 内
def _to_png_b64(path: str | Path) -> str:
    with Image.open(path) as src:
        img = src.convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(bg, img).convert("RGB")
    img.thumbnail((512, 512))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


async def recognize_sticker(path: str | Path) -> str:
    b64 = await asyncio.to_thread(_to_png_b64, path)
    resp = await client.chat.completions.create(
        model=bs.ai_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            },
        ],
    )
    text = resp.choices[0].message.content or ""
    return " ".join(unicodedata.normalize("NFKC", text).split())
