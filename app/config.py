from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    bot_token: str
    admin_ids: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/database.sqlite3"
    swipe_before_ad: int = 3
    max_likes_per_day: int = 30
    inactive_days_before_hide: int = 30

    premium_1m_stars: int = 50
    premium_3m_stars: int = 120
    premium_lifetime_stars: int = 300
    boost_stars: int = 30
    provider_token: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def admin_ids_list(self) -> list[int]:
        if not self.admin_ids:
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]


config = Config(_env_file=Path(__file__).parent.parent / ".env")
