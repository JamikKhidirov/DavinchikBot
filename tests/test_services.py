import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def clean_db():
    from app.database import async_session, init_db
    from sqlalchemy import text
    await init_db()
    async with async_session() as session:
        for table in ("payments", "advertisements", "complaints", "matches", "likes", "blocks", "profiles", "users"):
            try:
                await session.execute(text(f"DELETE FROM {table}"))
            except Exception:
                pass
        await session.commit()


@pytest.mark.anyio
async def test_get_or_create_user():
    from app.database import init_db
    from app.services.profile_service import get_or_create_user
    await init_db()
    user = await get_or_create_user(telegram_id=992010, username="svc_test")
    assert user is not None
    assert user.telegram_id == 992010
    assert user.username == "svc_test"
    same = await get_or_create_user(telegram_id=992010)
    assert same.id == user.id


@pytest.mark.anyio
async def test_create_and_get_profile():
    from app.database import init_db
    from app.services.profile_service import create_profile, get_or_create_user, get_profile_by_telegram_id
    await init_db()
    await get_or_create_user(telegram_id=992011)
    profile = await create_profile(
        telegram_id=992011,
        name="TestName", age=25, gender="male",
        looking_for="female", city="Moscow", bio="Hello!",
        photos=["photo1.jpg"],
    )
    assert profile is not None
    assert profile.name == "TestName"
    assert profile.age == 25
    assert profile.city == "Moscow"
    fetched = await get_profile_by_telegram_id(992011)
    assert fetched is not None
    assert fetched.id == profile.id


@pytest.mark.anyio
async def test_get_all_users():
    from app.database import init_db
    from app.services.profile_service import get_all_users, get_or_create_user
    await init_db()
    await get_or_create_user(telegram_id=992020, username="u1")
    await get_or_create_user(telegram_id=992021, username="u2")
    users = await get_all_users()
    ids = [u.telegram_id for u in users]
    assert 992020 in ids
    assert 992021 in ids


@pytest.mark.anyio
async def test_deactivate_inactive_profiles():
    from app.database import init_db, async_session
    from app.models import User, Profile
    from app.services.profile_service import deactivate_inactive_profiles
    from datetime import datetime, timedelta, timezone
    await init_db()
    async with async_session() as session:
        user = User(telegram_id=992030, last_active_at=datetime.now(timezone.utc) - timedelta(days=31))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        profile = Profile(
            user_id=user.id, name="Old", age=20, gender="male",
            looking_for="female", city="City", bio="",
            is_active=True,
        )
        session.add(profile)
        await session.commit()
    result = await deactivate_inactive_profiles()
    assert result >= 1


@pytest.mark.anyio
async def test_block_unblock():
    from app.database import init_db, async_session
    from app.models import User
    from app.services.block_service import block_user, unblock_user, is_blocked
    await init_db()
    async with async_session() as session:
        u1 = User(telegram_id=992040)
        u2 = User(telegram_id=992041)
        session.add_all([u1, u2])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
    assert await block_user(u1.telegram_id, u2.id) is True
    assert await is_blocked(u1.id, u2.id) is True
    assert await is_blocked(u2.id, u1.id) is True
    assert await unblock_user(u1.telegram_id, u2.id) is True
    assert await is_blocked(u1.id, u2.id) is False


@pytest.mark.anyio
async def test_like_and_match():
    from app.database import init_db, async_session
    from app.models import User, Profile
    from app.services.matching_service import like_profile, get_matches
    await init_db()
    async with async_session() as session:
        u1 = User(telegram_id=992050)
        u2 = User(telegram_id=992051)
        session.add_all([u1, u2])
        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        session.add_all([
            Profile(user_id=u1.id, name="A", age=25, gender="male", looking_for="female", city="Moscow", bio="hi", is_active=True),
            Profile(user_id=u2.id, name="B", age=24, gender="female", looking_for="male", city="Moscow", bio="hey", is_active=True),
        ])
        await session.commit()
    result = await like_profile(u1.telegram_id, u2.id)
    assert result == "liked"
    result = await like_profile(u2.telegram_id, u1.id)
    assert result == "match"
    matches = await get_matches(u1.telegram_id)
    assert len(matches) >= 1
    assert matches[0]["telegram_id"] == u2.telegram_id


@pytest.mark.anyio
async def test_premium_and_boost():
    from app.database import init_db, async_session
    from app.models import User, Profile
    from app.services.premium_service import activate_premium, check_premium_expired, activate_boost, check_boost_expired
    await init_db()
    async with async_session() as session:
        user = User(telegram_id=992060)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.add(Profile(user_id=user.id, name="P", age=20, gender="male", looking_for="female", city="C", bio="", is_active=True))
        await session.commit()
    assert await activate_premium(992060, "1m") is True
    assert await activate_boost(992060) is True
    async with async_session() as s:
        u = await s.get(User, user.id)
        assert u.is_premium is True
        assert u.premium_expires_at is not None
    expired = await check_premium_expired()
    assert isinstance(expired, int)
    expired_b = await check_boost_expired()
    assert isinstance(expired_b, int)


@pytest.mark.anyio
async def test_ad_increment():
    from app.database import init_db, async_session
    from app.services.ad_service import create_ad, get_active_ads, increment_impression, increment_click
    await init_db()
    ad = await create_ad(photo_id="photo123", text="Test ad", button_text="Click", button_url="https://example.com")
    assert ad.id is not None
    assert ad.is_active is True
    active = await get_active_ads()
    assert len(active) >= 1
    assert active[0].id == ad.id
    await increment_impression(ad.id)
    await increment_click(ad.id)
    async with async_session() as s:
        updated = await s.get(type(ad), ad.id)
        assert updated.impressions_count == 1
        assert updated.clicks_count == 1


@pytest.mark.anyio
async def test_notification_functions_exist():
    from app.services.notification_service import notify_like, notify_match, send_broadcast
    assert callable(notify_like)
    assert callable(notify_match)
    assert callable(send_broadcast)
