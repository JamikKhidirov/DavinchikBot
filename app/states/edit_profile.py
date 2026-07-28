from aiogram.fsm.state import StatesGroup, State


class EditProfile(StatesGroup):
    name = State()
    age = State()
    gender = State()
    looking_for = State()
    city = State()
    bio = State()
    photos = State()


class Verification(StatesGroup):
    photo = State()
