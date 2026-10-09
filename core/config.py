import os
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import make_url


class WatchdogSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        env_prefix="WD_",
    )
    is_running: bool = Field(default=False)
    """运行中"""
    restart_count: int = Field(default=0)
    """重启次数"""
    disconnect_count: int = Field(default=0)
    """断开连接次数"""
    max_disconnect_count: int = Field(default=3)
    """最大断开连接次数, 超过后重启"""
    remove_session_after_restart: int = Field(default=3)
    """重启失败几次后删除会话文件"""
    max_restart_count: int = Field(default=6)
    """意外断开连接时，最大重启次数"""
    exit_flag: bool = Field(default=False)
    """退出标志"""

    def update_bot_restart_count(self) -> None:
        self.restart_count += 1
        os.environ["WD_RESTART_COUNT"] = str(self.restart_count)

    def reset_bot_restart_count(self) -> None:
        self.restart_count = 0
        os.environ["WD_RESTART_COUNT"] = "0"

    def update_bot_disconnect_count(self) -> None:
        self.disconnect_count += 1
        os.environ["WD_DISCONNECT_COUNT"] = str(self.disconnect_count)

    def reset_bot_disconnect_count(self) -> None:
        self.disconnect_count = 0
        os.environ["WD_DISCONNECT_COUNT"] = "0"


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admins: Annotated[list[int], NoDecode] = Field(default_factory=list)
    """管理员 ID 列表, 留空则所有人可用"""
    bot_token: str
    api_id: str
    api_hash: str
    bot_proxy: str | None = Field(default=None)
    bot_workdir: Path = Field(default=Path("sessions"))
    data_dir: Path = Field(default=Path("data"))
    database_url: str = Field(default="")
    ai_base_url: str = Field(default="https://api.openai.com/v1")
    """OpenAI 兼容接口地址"""
    ai_api_key: str
    ai_model: str
    ai_timeout: float = Field(default=60, gt=0)
    """单次请求超时(秒)"""
    ai_max_retries: int = Field(default=3, ge=0)
    """失败重试次数(含 429 限流)"""
    ocr_concurrency: int = Field(default=1, ge=1)
    """同时进行的下载/转码/识别任务数"""
    debug: bool = Field(default=False)

    def model_post_init(self, __context: Any) -> None:
        """模型初始化后的操作"""
        self.bot_workdir.mkdir(parents=True, exist_ok=True)
        self.downloads_path.mkdir(parents=True, exist_ok=True)

        if not self.database_url:
            self.database_url = f"sqlite+aiosqlite:///{self.data_dir / 'sticker.db'}"
        url = make_url(self.database_url)
        if url.get_backend_name() == "sqlite" and url.database:
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)

    @field_validator("admins", mode="before")
    @classmethod
    def parse_admins(cls, v: Any) -> list[int]:
        if isinstance(v, list):
            return [int(x) if not isinstance(x, int) else x for x in v]
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            return [int(x.strip()) for x in v.replace(" ", "").split(",") if x.strip()]
        raise ValueError("Invalid admins format")

    @property
    def bot_session_name(self) -> str:
        return f"bot_{self.bot_token.split(':')[0]}"

    @property
    def downloads_path(self) -> Path:
        # kurigram 的 download_media 会把相对路径拼到 workdir 下, 这里返回绝对路径
        return (self.data_dir / "downloads").resolve()


bs = BotSettings()  # type: ignore
ws = WatchdogSettings()
