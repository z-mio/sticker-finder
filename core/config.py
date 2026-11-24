from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy import make_url


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

    @field_validator("bot_proxy", mode="before")
    @classmethod
    def empty_proxy_to_none(cls, v: Any) -> Any:
        return v or None

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
