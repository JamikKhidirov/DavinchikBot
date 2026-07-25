import pytest
from sqlalchemy import text

from app.database import async_session


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def clean_db():
    async with async_session() as session:
        for table in ("payments", "advertisements", "complaints", "matches", "likes", "blocks", "profiles", "users"):
            await session.execute(text(f"DELETE FROM {table}"))
        await session.commit()


@pytest.mark.anyio
async def test_init_db():
    from app.database import init_db
    await init_db()
    async with async_session() as session:
        result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        )
        tables = [row[0] for row in result]
        expected = {"users", "profiles", "likes", "matches", "blocks", "complaints", "advertisements", "payments"}
        for t in expected:
            assert t in tables, f"Table {t} not found"


@pytest.mark.anyio
async def test_create_user():
    from app.database import init_db
    from app.models import User
    await init_db()
    async with async_session() as session:
        user = User(telegram_id=991001, username="test_user")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        assert user.id is not None
        saved = await session.get(User, user.id)
        assert saved is not None
        assert saved.telegram_id == 991001
        assert saved.username == "test_user"
        assert saved.is_admin is False
        assert saved.is_premium is False


@pytest.mark.anyio
async def test_create_profile():
    from app.database import init_db
    from app.models import User, Profile
    await init_db()
    async with async_session() as session:
        user = User(telegram_id=991002, username="profile_test")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        profile = Profile(
            user_id=user.id,
            name="Test",
            age=25,
            gender="male",
            looking_for="female",
            city="Moscow",
            bio="Hello!",
            is_active=True,
        )
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
        assert profile.id is not None
        assert profile.name == "Test"
        assert profile.age == 25
        assert profile.city == "Moscow"


@pytest.mark.anyio
async def test_create_like():
    from app.database import init_db
    from app.models import User, Like
    await init_db()
    async with async_session() as session:
        u1 = User(telegram_id=991003)
        u2 = User(telegram_id=991004)
        session.add_all([u1, u2])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        like = Like(from_user_id=u1.id, to_user_id=u2.id)
        session.add(like)
        await session.commit()
        await session.refresh(like)
        assert like.id is not None
        assert like.from_user_id == u1.id
        assert like.to_user_id == u2.id


@pytest.mark.anyio
async def test_create_match():
    from app.database import init_db
    from app.models import User, Match
    await init_db()
    async with async_session() as session:
        u1 = User(telegram_id=991005)
        u2 = User(telegram_id=991006)
        session.add_all([u1, u2])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        match = Match(user1_id=u1.id, user2_id=u2.id)
        session.add(match)
        await session.commit()
        await session.refresh(match)
        assert match.id is not None
        assert match.user1_id == u1.id
        assert match.user2_id == u2.id


@pytest.mark.anyio
async def test_create_payment():
    from app.database import init_db
    from app.models import User, Payment
    await init_db()
    async with async_session() as session:
        u = User(telegram_id=991007)
        session.add(u)
        await session.commit()
        await session.refresh(u)
        payment = Payment(
            user_id=u.id,
            amount=50.0,
            payment_type="stars_1m",
            status="completed",
        )
        session.add(payment)
        await session.commit()
        await session.refresh(payment)
        assert payment.id is not None
        assert payment.payment_type == "stars_1m"
        assert payment.amount == 50.0
        assert payment.status == "completed"
