# 贴纸收藏夹Bot


**使用教程**：[LINK]([sticker-finder](xsjapp://doc/b01f30e8-94d7-4839-83e5-b0a36a38c938#xsj_1694490373279))


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

## 2.运行

**前台启动bot**

``` 
python3 bot.py
```


**后台启动bot**

``` 
nohup python3 bot.py > botlog.log 2>&1 &
```



