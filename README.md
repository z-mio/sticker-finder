# 贴纸搜索机器人

## 介绍

添加的贴纸包多了之后，想找到某张贴纸就比较麻烦，特别是语录类的贴纸包，找起来特别费眼睛。在水群时，也会经常因为找不到贴纸而错过发送时机。  
所以，贴纸搜索bot就诞生了，用来快速查找贴纸，节省寻找贴纸的时间  
**识别贴纸**：优先识别贴纸（只支持静态贴纸）中的文字，如果没有，则自动[识别图像内容](https://portal.vision.cognitive.azure.com/demo/image-captioning)作为贴纸标签  
**查找贴纸**：支持通过 `自定义标签` / `贴纸中的文字` / `贴纸的内容` / `Emoji` / `贴纸包名称/标题` 来搜索贴纸，支持模糊搜索  
**最近使用**：将最近使用的贴纸置顶显示，方便快速使用常用贴纸。  
**自动索引**：自动索引贴纸包中新增的贴纸  
**使用教程：[LINK](https://telegra.ph/%E8%B4%B4%E7%BA%B8%E6%94%B6%E8%97%8F%E5%A4%B9bot%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B-09-08)**  
**体验一下：[贴纸收藏夹](https://t.me/KTagbot)**

<img src="https://github.com/z-mio/sticker-finder/blob/059d5bfcb766f475903ed6016d3efc4be2e7522a/img/search.gif"  width="500" />

---

## 1.安装

**1.1 安装 python3-pip**

```
apt install python3-pip
```

**1.2 将项目克隆到本地**

``` 
git clone https://github.com/z-mio/sticker-finder.git && cd sticker-finder && pip3 install -r requirements.txt
```

**1.3 修改 config.yaml 里的配置信息**

``` yaml
proxy:
  hostname: '' # '127.0.0.1'
  port: ''  # '7890'
  scheme: '' # 'http'
user:
  # 默认为null，所有人都可以使用bot，设置之后只有管理员可用
  admin: null # 填user_id 可以从 https://t.me/getletbot 发送 /get 指令获取
  api_hash: 123abc # 在 https://my.telegram.org/apps 获取
  api_id: 123456789 # 在 https://my.telegram.org/apps 获取
  bot_token: 6108379846:AAH2 # 在 https://t.me/BotFather 获取
```

**1.4 打开bot内联模式**

在 https://t.me/BotFather 新建bot后

<img src="https://github.com/z-mio/sticker-finder/blob/059d5bfcb766f475903ed6016d3efc4be2e7522a/img/inline.gif" width="400" />

## 2.运行

**前台启动bot**

``` 
python3 bot.py
```

**后台启动bot**

``` 
nohup python3 bot.py > botlog.log 2>&1 &
```

