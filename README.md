# 贴纸搜索机器人


## 介绍

**查找贴纸**：通过 `自定义标签` / `贴纸中的文字` / `Emoji` / `贴纸包名称/标题` 来搜索贴纸，支持模糊搜索  
**最近使用**：将最近使用的贴纸置顶显示，方便快速使用常用的贴纸。

**使用教程：[LINK](https://telegra.ph/%E8%B4%B4%E7%BA%B8%E6%94%B6%E8%97%8F%E5%A4%B9bot%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B-09-08)**

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
api_id = ''  # 在 https://my.telegram.org/apps 获取
api_hash = ''  # 在 https://my.telegram.org/apps 获取
bot_token = ''  # 在 https://t.me/BotFather 获取

# 代理支持“socks4”、“socks5”和“http”
scheme = ''  # 'http'
hostname = ''  # '127.0.0.1'
port = ''  # '7890'
```

**1.4 打开bot内联模式**

在 https://t.me/BotFather 新建bot后

<img src="https://img.chkaja.com/0067b6b46aac67f7.gif" alt="0067b6b46aac67f7.gif" title="0067b6b46aac67f7.gif" width="400" />



## 2.运行

**前台启动bot**

``` 
python3 bot.py
```


**后台启动bot**

``` 
nohup python3 bot.py > botlog.log 2>&1 &
```



