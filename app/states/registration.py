from aiogram.fsm.state import StatesGroup, State


class Registration(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    bio = State()
    photos = State()
    confirm = State()
