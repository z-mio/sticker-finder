import asyncio
from collections import defaultdict
from pathlib import Path
from time import time

import httpx
import translators as ts
from pyrogram import Client, errors, filters, raw
from pyrogram.raw.types.messages import StickerSet
from pyrogram.types import Sticker as Stk
from rapidocr_onnxruntime import RapidOCR
from sqlalchemy import or_, select

from config.config import admin
from database import AutoIndexSticker, DBSession, RecentlyUsed, Sticker


def get_sticker_pack_name(client: Client, set_name):
    try:
        info: StickerSet = client.invoke(
            raw.functions.messages.GetStickerSet(
                stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
                hash=0,
            )
        )
    except errors.StickersetInvalid:
        return []
    return info.set.title


# 获取贴纸包名称
async def async_get_sticker_pack_name(client: Client, set_name):
    try:
        info: StickerSet = await client.invoke(
            raw.functions.messages.GetStickerSet(
                stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
                hash=0,
            )
        )
    except errors.StickersetInvalid:
        return []
    return info.set.title


# 获取贴纸中所有贴纸
def parse_stickers(client: Client, set_name):
    try:
        info: StickerSet = client.invoke(
            raw.functions.messages.GetStickerSet(
                stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
                hash=0,
            )
        )
    except errors.StickersetInvalid:
        return []
    documents = info.documents
    final = []
    title = info.set.title
    count = info.set.count
    short_name = info.set.short_name
    for stk in documents:
        __sticker = asyncio.run(
            Stk._parse(client, stk, {type(i): i for i in stk.attributes})
        )
        final.append(__sticker)
    return {"title": title, "count": count, "short_name": short_name, "final": final}


# 获取自动索引的贴纸包
def get_auto_indexed_packages(set_name, uid):
    with DBSession.begin() as session:
        stmt = select(AutoIndexSticker).filter(
            AutoIndexSticker.uid == uid, AutoIndexSticker.set_name == set_name
        )
        return session.execute(stmt).scalars().one_or_none()


# 过滤指定字符开头的内联查询结果
def filter_inline_query_results(command: str):
    """
    过滤指定字符开头的内联查询结果

    :param command:
    :return:
    """

    async def func(_, __, update):
        return update.query.startswith(command)

    return filters.create(func, name="InlineQueryResultFilter", commands=command)


def stick_find(query, uid) -> list[Sticker]:
    if query:
        stmt = select(Sticker).filter(
            or_(
                Sticker.tag.ilike(f"%{query}%"),
                Sticker.emoji.ilike(f"%{query}%"),
                Sticker.title.ilike(f"%{query}%"),
                Sticker.set_name == query,
                Sticker.sticker_unique_id == query,
            ),
            Sticker.uid == uid,
        )
    else:
        stmt = select(Sticker).filter(Sticker.uid == uid)
    # 按贴纸包名和emoji升序排序
    stmt_asc = stmt.order_by(Sticker.set_name.asc(), Sticker.time.asc())
    session = DBSession()
    return session.execute(stmt_asc).scalars().all()


def recently_used_find(uid) -> list[Sticker]:
    stmt = (
        select(RecentlyUsed)
        .filter(RecentlyUsed.uid == uid)
        .order_by(RecentlyUsed.time.asc())
    )
    session = DBSession()
    return session.execute(stmt).scalars().all()


# _ocr = PaddleOCR(use_angle_cls=True, enable_mkldnn=True, ocr_version='PP-OCRv4')
# def ocr(path: str) -> list:
#     result = _ocr.ocr(path, cls=False)
#     return [i[1][0] for i in result[0]]


# 最优组合为：
# ch_PP-OCRv3_det + ch_ppocr_mobile_v2.0_cls + ch_PP-OCRv3_rec
# 和v4速度相差不大，文字检测不如v4

# rapid_ocr = RapidOCR(
# det_model_path="resources/models/ch_PP-OCRv3_det_infer.onnx",  # 指定检测模型文件路径
# cls_model_path="resources/models/ch_ppocr_mobile_v2.0_cls_infer.onnx",  # 指定方向分类模型文件路径
# rec_model_path="resources/models/ch_PP-OCRv3_rec_infer.onnx",  # 指定识别模型文件路径
# )

rapid_ocr = RapidOCR()


def ocr_rapid(path) -> list[None | str]:
    result, _ = rapid_ocr(path, text_score=0.4, use_angle_cls=False)
    return [i[1] for i in result] if result else []


def get_sticker_id(sid: str) -> str:
    i = sid.split("_")
    return "_".join(i[1:]) if i[1:] else i[0]


requests = defaultdict(int)
last_request_time = defaultdict(int)


# 速率限制
def rate_limit(request_limit=3, time_limit=60):
    def decorator(func):
        def wrapper(client, message):
            user_id = message.from_user.id
            current_time = time()
            if current_time - last_request_time[user_id] > time_limit:
                requests[user_id] = 1
                last_request_time[user_id] = current_time
            else:
                if requests[user_id] >= request_limit:
                    return message.reply(
                        f"速率限制：{request_limit}张/{time_limit}秒，请稍后再试"
                    )  # 超过限制次数,不处理请求
                requests[user_id] += 1

            func(client, message)  # 调用原函数

        return wrapper

    return decorator


def is_admin():
    async def func(_, __, update):
        return not admin or update.from_user.id == admin

    return filters.create(func)


def azure_img_tag(path: str | Path) -> str:
    params = {
        "features": "tags",
        "language": "zh",
    }
    with open(path, "rb") as f:
        data = {"file": f}
        response = httpx.post(
            "https://portal.vision.cognitive.azure.com/api/demo/analyze",
            params=params,
            files=data,
        )
        if response.status_code == 200:
            response = response.json()
        else:
            return []
        return [i["name"] for i in response["tagsResult"]["values"]]


def azure_img_caption(path: str | Path) -> str:
    params = {
        "features": "caption",
        "language": "en",
    }
    with open(path, "rb") as f:
        data = {"file": f}
        response = httpx.post(
            "https://portal.vision.cognitive.azure.com/api/demo/analyze",
            params=params,
            files=data,
        )
        if response.status_code == 200:
            response = response.json()
        else:
            raise Exception("识别失败")
        text = response["captionResult"]["text"]
        try:
            text = ts.translate_text(text, "youdao", to_language="zh")
        finally:
            return text
