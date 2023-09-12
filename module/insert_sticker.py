import os
import time
from typing import List, Mapping

from loguru import logger
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message
from pyrogram.types import Sticker as Stk
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from config.config import DOWNLOADS_PATH, chat_data
from database import DBSession, Sticker
from utils import get_sticker_pack_name, ocr_rapid, parse_stickers, rate_limit

STICKER_PACK_STATUS = {}


@Client.on_message(filters.text & filters.private & ~filters.inline_keyboard & ~filters.via_bot)
@logger.catch()
def help_(client: Client, message: Message):
    text = message.text
    if not text.startswith('https://t.me/addstickers/'):
        return message.reply('请发送贴纸or贴纸包链接\n教程：[LINK](https://telegra.ph/贴纸收藏夹bot使用教程-09-08)',
                             disable_web_page_preview=True)
    
    if STICKER_PACK_STATUS.get(message.from_user.id):
        return message.reply('当前已有任务，请等完成后再试')
    
    STICKER_PACK_STATUS[message.from_user.id] = True
    add_sticker_pack(client, message)


# 添加新贴纸
@Client.on_message(filters.sticker & filters.private & ~filters.inline_keyboard)
@rate_limit(1, 1)
@logger.catch()
def add_sticker(client: Client, message: Message):
    sticker = message.sticker
    uid = message.from_user.id
    button = [
        [
            InlineKeyboardButton('编辑标签',
                                 switch_inline_query_current_chat=f'edit {sticker.file_unique_id}\000'),
            InlineKeyboardButton('删除贴纸',
                                 switch_inline_query_current_chat=f'del {sticker.file_unique_id}\000')
        ],
        [
            InlineKeyboardButton('编辑贴纸包',
                                 switch_inline_query_current_chat=f'edit https://t.me/addstickers/{sticker.set_name}\000'),
            InlineKeyboardButton('删除贴纸包',
                                 switch_inline_query_current_chat=f'del https://t.me/addstickers/{sticker.set_name}\000')
        
        ]
    ]
    text = '**标签：**`{tag}`\n**Emoji：**`{emoji}`\n**贴纸包：**`{title}` | `{set_name}`'
    # 如果贴纸已经存在就发送贴纸信息
    
    if stk := sticker_exist(uid, sticker.file_unique_id):
        text = f"{text.format(tag=stk.tag, emoji=stk.emoji, title=stk.title, set_name=stk.set_name)}\n**使用次数：**`{stk.usage_count + 1}`"
        return message.reply(text, reply_markup=InlineKeyboardMarkup(button))
    
    else:
        msg: Message = message.reply('添加中...', disable_notification=True)
        
        tag = 'None'
        if sticker.mime_type == 'image/webp':
            download_sticker(client, sticker.file_id)
            tag = chat_data[f'ocrTag_{sticker.file_id}']
            chat_data.pop(f'ocrTag_{sticker.file_id}')
        
        try:
            stk = insert_stacker(client, message.from_user.id, tag, sticker)
        except IntegrityError:
            stk = sticker_exist(uid, sticker.file_unique_id)
            text = text.format(tag=stk.tag, emoji=stk.emoji, title=stk.title, set_name=stk.set_name)
            return msg.edit(text, reply_markup=InlineKeyboardMarkup(button))
        
        text = f'✅添加成功!\n{text.format(tag=stk["tag"], emoji=stk["emoji"], title=stk["title"], set_name=stk["set_name"])}'
        msg.edit(text, reply_markup=InlineKeyboardMarkup(button))
    del stk, uid, sticker, tag, text, button
    return


# 添加新贴纸包
@rate_limit(10, 60)
def add_sticker_pack(client: Client, message: Message):
    set_name = message.text.replace('https://t.me/addstickers/', '')
    stk_pack = parse_stickers(client, set_name)
    uid = message.from_user.id
    
    button = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton('查看贴纸包', switch_inline_query_current_chat=stk_pack['short_name']),
                InlineKeyboardButton('编辑贴纸包', switch_inline_query_current_chat=f'edit {message.text}\000'),
                InlineKeyboardButton('删除贴纸包', switch_inline_query_current_chat=f'del {message.text}\000')
            
            ]
        ]
    )
    
    msg: Message = message.reply(f'正在添加贴纸包，请稍等|0/{stk_pack["count"]}')
    _tag = []
    _stk = []
    t = time.time()
    for i, sticker in enumerate(stk_pack['final']):
        i += 1
        if i % 5 == 0 or i == stk_pack["count"]:
            msg.edit(f'正在添加贴纸包，请稍等|{i}/{stk_pack["count"]}', reply_markup=button)
        
        if sticker_exist(uid, sticker.file_unique_id):
            continue
        tag = 'None'
        if sticker.mime_type == 'image/webp':
            download_sticker(client, sticker.file_id)
            tag = chat_data[f'ocrTag_{sticker.file_id}']
            chat_data.pop(f'ocrTag_{sticker.file_id}')
            # 如果贴纸已经存在就发送贴纸信息
        _tag.append(tag)
        _stk.append(sticker)
    insert_stacker(client, message.from_user.id, _tag, _stk)
    text = f'''
✅完成！
贴纸包: `{stk_pack['title']}`|`{stk_pack['short_name']}`
数量: `{stk_pack["count"]}`
耗时: `{time.time() - t:.2f}s`
'''
    msg.edit(text, reply_markup=button)
    STICKER_PACK_STATUS[message.from_user.id] = False
    del _tag, _stk, set_name, stk_pack, uid, text
    return


# 判断贴纸是否已存在
def sticker_exist(uid, file_unique_id) -> Sticker:
    session = DBSession()
    stmt = select(Sticker).filter(Sticker.sticker_unique_id == file_unique_id,
                                  Sticker.uid == uid)
    result = session.execute(stmt).scalars().first()
    del stmt, session
    return result


# 下载贴纸
def download_sticker(client: Client, sticker_id: str):
    path = DOWNLOADS_PATH.joinpath(f'{sticker_id[:5]}_{time.time():.0f}.png')
    path = client.download_media(sticker_id, path)
    tag = ''.join(ocr_rapid(path)) or "None"
    chat_data[f'ocrTag_{sticker_id}'] = tag
    os.remove(path)
    del tag, path
    return


def insert_stacker(client: Client, uid: int, tag: Mapping[str, List[str]], sticker: Mapping[Stk, List[Stk]]) -> dict:
    with DBSession.begin() as session:
        if isinstance(sticker, Stk):
            stk_ = create_sticker_data(client, uid, tag, sticker)
            session.add(Sticker(**stk_))
            return stk_
        else:
            stickers = [Sticker(**create_sticker_data(client, uid, tag[i], sticker[i])) for i in range(len(sticker))]
            session.add_all(stickers)
            del stickers
    del session


def create_sticker_data(client: Client, uid: int, tag: List[str], sticker: Stk):
    # 如果用户是自定义title，则会获取自定义的title
    with DBSession.begin() as session:
        stmt = select(Sticker).filter(Sticker.set_name == sticker.set_name, Sticker.uid == uid)
        title = session.execute(stmt).scalars().first()
        title = title.title if title else get_sticker_pack_name(client, sticker.set_name)
    
    stk_ = {
        'uid': uid,
        'tag': tag,
        'sticker_id': sticker.file_id,
        'sticker_unique_id': sticker.file_unique_id,
        'sticker_type': sticker.mime_type,
        'emoji': sticker.emoji,
        'set_name': sticker.set_name,
        'title': title,
        'usage_count': 0,
        'time': time.time(),
    }
    del title, stmt
    return stk_
