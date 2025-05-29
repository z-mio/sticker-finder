import os
import time
from pathlib import Path
from typing import List, Union

import cv2
from loguru import logger
from pyrlottie import run, convMultLottie, FileMap, LottieFile
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from pyrogram.types import Sticker as Stk
from rapidocr_onnxruntime import LoadImageError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config.config import DOWNLOADS_PATH
from database import DBSession, Sticker
from module.auto_index import build_auto_index_button
from utils import (
    get_sticker_pack_name,
    is_admin,
    ocr_rapid,
    parse_stickers,
    rate_limit,
    azure_img_caption,
)

STICKER_PACK_STATUS = {}


@Client.on_message(
    filters.text
    & filters.private
    & ~filters.inline_keyboard
    & ~filters.via_bot
    & is_admin()
)
@logger.catch()
def help_(client: Client, message: Message):
    text = message.text
    if not text.startswith("https://t.me/addstickers/"):
        return message.reply(
            "请发送贴纸or贴纸包链接\n教程：[LINK](https://telegra.ph/贴纸收藏夹bot使用教程-09-08)",
            disable_web_page_preview=True,
        )

    if STICKER_PACK_STATUS.get(message.from_user.id):
        return message.reply("当前已有任务，请等完成后再试")

    STICKER_PACK_STATUS[message.from_user.id] = True
    try:
        add_sticker_pack(client, message)
    except Exception as e:
        logger.error(e)
        message.reply(f"添加失败，请重试\n错误：{e}")
    finally:
        STICKER_PACK_STATUS[message.from_user.id] = False
    return


# 添加新贴纸
@Client.on_message(
    filters.sticker & filters.private & ~filters.inline_keyboard & is_admin()
)
@rate_limit(1, 1)
@logger.catch()
def add_sticker(client: Client, message: Message):
    sticker = message.sticker

    # 如果贴纸不在贴纸包内
    if not sticker.set_name:
        sticker.set_name = (
            "KTagBot"  # KTagBot 是 bot 默认贴纸包 https://t.me/addstickers/KTagBot
        )
    if not sticker.emoji:
        sticker.emoji = "😀"

    uid = message.from_user.id
    button = [
        [
            InlineKeyboardButton(
                "编辑标签",
                switch_inline_query_current_chat=f"edit {sticker.file_unique_id}\000",
            ),
            InlineKeyboardButton(
                "删除贴纸",
                switch_inline_query_current_chat=f"del {sticker.file_unique_id}\000",
            ),
        ],
        [
            InlineKeyboardButton(
                "编辑贴纸包",
                switch_inline_query_current_chat=f"edit https://t.me/addstickers/{sticker.set_name}\000",
            ),
            InlineKeyboardButton(
                "删除贴纸包",
                switch_inline_query_current_chat=f"del https://t.me/addstickers/{sticker.set_name}\000",
            ),
        ],
        [build_auto_index_button(sticker.set_name, uid)],
    ]
    text = "**标签：**`{tag}`\n**Emoji：**`{emoji}`\n**贴纸包：**`{title}` | `{set_name}`"

    # 如果贴纸已经存在就发送贴纸信息
    if stk := sticker_exist(uid, sticker.file_unique_id):
        text = f"{text.format(tag=stk.tag, emoji=stk.emoji, title=stk.title, set_name=stk.set_name)}\n**使用次数：**`{stk.usage_count + 1}`"
        return message.reply(text, reply_markup=InlineKeyboardMarkup(button))

    else:
        msg: Message = message.reply("添加中...", disable_notification=True)
        try:
            stk = insert_stacker(client, message.from_user.id, sticker)
        except IntegrityError:
            stk = sticker_exist(uid, sticker.file_unique_id)
            text = text.format(
                tag=stk.tag, emoji=stk.emoji, title=stk.title, set_name=stk.set_name
            )
            return msg.edit(text, reply_markup=InlineKeyboardMarkup(button))
        except LoadImageError:
            return msg.edit("OCR识别失败，可能是贴纸下载错误")

        text = f'✅添加成功!\n{text.format(tag=stk["tag"], emoji=stk["emoji"], title=stk["title"], set_name=stk["set_name"])}'
        msg.edit(text, reply_markup=InlineKeyboardMarkup(button))
    del stk, uid, sticker, text, button
    return


# 添加新贴纸包
def add_sticker_pack(client: Client, message: Message):
    set_name = message.text.replace("https://t.me/addstickers/", "")
    stk_pack = parse_stickers(client, set_name)
    uid = message.from_user.id

    a_button = [
        InlineKeyboardButton(
            "查看贴纸包", switch_inline_query_current_chat=stk_pack["short_name"]
        ),
        InlineKeyboardButton(
            "编辑贴纸包", switch_inline_query_current_chat=f"edit {message.text}\000"
        ),
        InlineKeyboardButton(
            "删除贴纸包", switch_inline_query_current_chat=f"del {message.text}\000"
        ),
    ]
    stop_button = [InlineKeyboardButton("停止添加", callback_data="sticker_stop")]
    msg: Message = message.reply(f'正在添加贴纸包，请稍等|0/{stk_pack["count"]}')
    _stk = []
    t = time.time()
    for i, sticker in enumerate(stk_pack["final"]):
        if not STICKER_PACK_STATUS[message.from_user.id]:
            return msg.edit("已停止添加")
        i += 1
        if i % 5 == 0 or i == stk_pack["count"]:
            insert_stacker(client, message.from_user.id, _stk)
            _stk.clear()
            msg.edit(
                f'正在添加贴纸包，请稍等|{i}/{stk_pack["count"]}',
                reply_markup=InlineKeyboardMarkup([a_button, stop_button]),
            )
        if sticker_exist(uid, sticker.file_unique_id):
            continue
            # 如果贴纸已经存在就发送贴纸信息
        _stk.append(sticker)
    insert_stacker(client, message.from_user.id, _stk)
    text = f"""
✅完成！
贴纸包: `{stk_pack['title']}`|`{stk_pack['short_name']}`
数量: `{stk_pack["count"]}`
耗时: `{time.time() - t:.2f}s`
"""
    msg.edit(
        text,
        reply_markup=InlineKeyboardMarkup(
            [a_button, [build_auto_index_button(set_name, uid)]]
        ),
    )
    del _stk, set_name, stk_pack, uid, text
    return


@Client.on_callback_query(filters.regex(r"sticker_stop") & is_admin())
async def stop_add_sticker(_, callback_query: CallbackQuery):
    STICKER_PACK_STATUS[callback_query.from_user.id] = False


# 判断贴纸是否已存在
def sticker_exist(uid, file_unique_id) -> Sticker:
    session = DBSession()
    stmt = select(Sticker).filter(
        Sticker.sticker_unique_id == file_unique_id, Sticker.uid == uid
    )
    result = session.execute(stmt).scalars().first()
    del stmt, session
    return result


# 下载贴纸 获取tag
# "image/webp", "video/webm", "application/x-tgsticker"
def download_sticker(client: Client, sticker_id: str, mime_type: str) -> str:
    if mime_type == "application/x-tgsticker":
        path = tgs_to_webp(client, sticker_id)
    elif mime_type == "video/webm":
        i_p, path = get_the_first_frame(client, sticker_id)
        os.remove(i_p)
    else:
        path = client.download_media(
            sticker_id,
            DOWNLOADS_PATH.joinpath(f"{sticker_id[:5]}_{time.time():.0f}.png"),
        )
    tag = identify_tag(path)
    os.remove(path)
    return tag


def tgs_to_webp(client: Client, sticker_id: str) -> str:
    i_p = str(
        client.download_media(
            sticker_id,
            DOWNLOADS_PATH.joinpath(f"{sticker_id[:5]}_{time.time():.0f}.tgs"),
        )
    )
    o_p = f"{i_p}.webp"
    run(convMultLottie([FileMap(LottieFile(i_p), {o_p})], frameSkip=60))
    os.remove(i_p)
    return o_p


# 获取视频第一帧
def get_the_first_frame(client: Client, sticker_id: str) -> tuple[str, str]:
    i_p = str(
        client.download_media(
            sticker_id,
            DOWNLOADS_PATH.joinpath(f"{sticker_id[:5]}_{time.time():.0f}.webm"),
        )
    )
    o_p = f"{i_p}.png"
    video = cv2.VideoCapture(i_p)
    image = video.read()[1]
    cv2.imwrite(o_p, image)

    return i_p, o_p


# 识别tag
def identify_tag(path: str | Path) -> str:
    try:
        tag_list = ocr_rapid(path)
    except LoadImageError:
        tag = "None"
    else:
        # 贴纸中没有文字就识别图像内容
        tag = "".join(tag_list) or azure_img_caption(path)
    return tag


# 返回tag
def tag_(client: Client, sticker: Stk) -> str:
    return (
        download_sticker(client, sticker.file_id, sticker.mime_type)
        if sticker.mime_type in ["image/webp", "video/webm", "application/x-tgsticker"]
        else "None"
    )


def insert_stacker(client: Client, uid: int, sticker: Union[Stk, List[Stk]]) -> dict:
    with DBSession.begin() as session:
        if isinstance(sticker, Stk):
            stk_ = create_sticker_data(client, uid, tag_(client, sticker), sticker)
            session.add(Sticker(**stk_))
            return stk_
        else:
            stickers = [
                Sticker(
                    **create_sticker_data(
                        client, uid, tag_(client, sticker[i]), sticker[i]
                    )
                )
                for i in range(len(sticker))
            ]
            session.add_all(stickers)
            del stickers
    del session


def create_sticker_data(client: Client, uid: int, tag: str, sticker: Stk) -> dict:
    # 如果用户是自定义title，则会获取自定义的title
    with DBSession.begin() as session:
        stmt = select(Sticker).filter(
            Sticker.set_name == sticker.set_name, Sticker.uid == uid
        )
        title = session.execute(stmt).scalars().first()
        title = (
            title.title if title else get_sticker_pack_name(client, sticker.set_name)
        )

    stk_ = {
        "uid": uid,
        "tag": tag,
        "sticker_id": sticker.file_id,
        "sticker_unique_id": sticker.file_unique_id,
        "sticker_type": sticker.mime_type,
        "emoji": sticker.emoji,
        "set_name": sticker.set_name,
        "title": title,
        "usage_count": 0,
        "time": sticker.date.timestamp(),  # 贴纸添加时间转为时间戳
    }
    del title, stmt
    return stk_
