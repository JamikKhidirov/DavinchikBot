import os
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import config


BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

TEST_MODE = os.environ.get("TEST_DATABASE") == "1"
DB_PATH = DATA_DIR / "test_database.sqlite3" if TEST_MODE else DATA_DIR / "database.sqlite3"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH.as_posix()}"


class Base(DeclarativeBase):
    pass


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        from sqlalchemy import text
        migrations = [
            "ALTER TABLE profiles ADD COLUMN videos JSON DEFAULT '[]'",
            "ALTER TABLE profiles ADD COLUMN interests JSON DEFAULT '[]'",
            "ALTER TABLE profiles ADD COLUMN latitude FLOAT",
            "ALTER TABLE profiles ADD COLUMN longitude FLOAT",
            "ALTER TABLE profiles ADD COLUMN search_radius INTEGER DEFAULT 300",
            "ALTER TABLE users ADD COLUMN referral_code VARCHAR(16)",
            "ALTER TABLE users ADD COLUMN referred_by_id INTEGER",
            "ALTER TABLE users ADD COLUMN extra_likes INTEGER DEFAULT 0",
            "ALTER TABLE likes ADD COLUMN is_superlike BOOLEAN DEFAULT 0",
            "ALTER TABLE likes ADD COLUMN superlike_message VARCHAR(256)",
            "ALTER TABLE payments ADD COLUMN currency VARCHAR(16) DEFAULT 'XTR'",
            "ALTER TABLE payments ADD COLUMN description TEXT",
        ]
        for sql in migrations:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass
