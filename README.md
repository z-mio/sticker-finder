# 贴纸搜索机器人


## 介绍

添加的贴纸包多了之后，想找到某张贴纸就比较麻烦，特别是语录类的贴纸包，找起来更是费眼睛。在水群时，也会经常因为找不到贴纸而错过发送时机。  
所以，贴纸搜索bot就诞生了，用来快速查找贴纸，节省寻找贴纸的时间

**查找贴纸**：支持通过 `自定义标签` / `贴纸中的文字` / `Emoji` / `贴纸包名称/标题` 来搜索贴纸，支持模糊搜索  
**最近使用**：将最近使用的贴纸置顶显示，方便快速使用常用的贴纸。  
**自动索引**：自动索引贴纸包中新增的贴纸  
**使用教程：[LINK](https://telegra.ph/%E8%B4%B4%E7%BA%B8%E6%94%B6%E8%97%8F%E5%A4%B9bot%E4%BD%BF%E7%94%A8%E6%95%99%E7%A8%8B-09-08)**  
**体验一下：[贴纸收藏夹](https://t.me/KTagbot)**

<img src="https://github.com/z-mio/sticker-finder/blob/059d5bfcb766f475903ed6016d3efc4be2e7522a/img/search.gif"  width="500" />

**打开bot内联模式**

在 https://t.me/BotFather 新建bot后

<img src="https://github.com/z-mio/sticker-finder/blob/059d5bfcb766f475903ed6016d3efc4be2e7522a/img/inline.gif" width="400" />

---


## 环境变量

将 `.env.example` 文件重命名为 `.env`

| 名称          | 描述                            | 默认值     |
|-------------|-------------------------------|---------|
| `ADMINS`    | 管理员用户ID，多个用户用逗号分隔，留空则所有人可用             |         |
| `API_ID`    | 登录 https://my.telegram.org 获取 |         |
| `API_HASH`  | 登录 https://my.telegram.org 获取 |         |
| `BOT_TOKEN` | 在 https://t.me/BotFather 获取   |         |
| `BOT_PROXY` | Bot 代理, 海外服务器不用填              |         |
| `DEBUG`     | 调试模式开关，设置为 `true` 启用调试日志      | `false` |
| `OCR_CONCURRENCY` | 同时进行的下载/转码/OCR 任务数          | `1`     |

## 开始部署

#### Docker (推荐):

**在项目根目录运行:**

```shell
sudo sh start.sh # 构建并运行 Bot
# 其他命令:
sudo sh start.sh -h # 查看帮助
sudo sh start.sh stop  # 停止 Bot
sudo sh start.sh restart # 重启 Bot
```

#### 直接运行:

**在项目根目录运行:**

```shell
# 安装依赖
apt install python3-pip -y
pip install uv --break-system-packages
uv venv --python 3.12
uv sync
# 运行 Bot
uv run bot.py 
```

