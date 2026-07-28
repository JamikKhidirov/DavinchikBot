def test_config_imports():
    from app.config import config, Config
    assert Config is not None
    assert config.bot_token is not None
    assert len(config.bot_token) > 0


def test_database_imports():
    from app.database import engine, async_session, init_db, Base
    assert engine is not None
    assert async_session is not None
    assert Base is not None


def test_models_imports():
    from app.models import User, Profile, Like, Match, Block, Complaint, Advertisement, Payment, Message, Gift, Referral, WithdrawalRequest
    assert User is not None
    assert Profile is not None
    assert Like is not None
    assert Match is not None
    assert Block is not None
    assert Complaint is not None
    assert Advertisement is not None
    assert Payment is not None
    assert Message is not None
    assert Gift is not None
    assert Referral is not None
    assert WithdrawalRequest is not None


def test_all_handlers_import():
    from app.handlers import start, registration, search, profile, matches, admin, complaints, premium, anonymous, chat, gifts
    assert start.router is not None
    assert registration.router is not None
    assert search.router is not None
    assert profile.router is not None
    assert matches.router is not None
    assert admin.router is not None
    assert complaints.router is not None
    assert premium.router is not None
    assert anonymous.router is not None
    assert chat.router is not None
    assert gifts.router is not None


def test_services_import():
    from app.services import profile_service, matching_service, block_service, ad_service, notification_service, premium_service, message_service, referral_service, gift_service, geo_service, ads_purchase_service
    assert profile_service is not None
    assert matching_service is not None
    assert block_service is not None
    assert ad_service is not None
    assert notification_service is not None
    assert premium_service is not None
    assert message_service is not None
    assert referral_service is not None
    assert gift_service is not None
    assert geo_service is not None
    assert ads_purchase_service is not None


def test_keyboards_import():
    from app.keyboards import profile as profile_kb, admin as admin_kb
    assert profile_kb is not None
    assert admin_kb is not None
    assert admin_kb.admin_grant_keyboard is not None


def test_states_import():
    from app.states import registration as reg_states, admin_states, edit_profile, chat_states
    assert reg_states is not None
    assert admin_states is not None
    assert edit_profile is not None
    assert chat_states is not None


def test_middleware_import():
    from app.middlewares.throttling import ThrottlingMiddleware
    assert ThrottlingMiddleware is not None


def test_setup_bot_import():
    from app.setup_bot import setup_bot, BOT_NAME, COMMANDS
    assert setup_bot is not None
    assert len(BOT_NAME) > 0
    assert len(COMMANDS) > 0


def test_main_import():
    import app.main
    assert app.main is not None
