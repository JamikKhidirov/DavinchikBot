from aiogram.fsm.state import StatesGroup, State


class AddAdvertisement(StatesGroup):
    photo = State()
    text = State()
    button_text = State()
    button_url = State()
    confirm = State()


class Broadcast(StatesGroup):
    text = State()
    photo = State()
    confirm = State()
