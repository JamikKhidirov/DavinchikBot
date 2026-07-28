from aiogram.fsm.state import StatesGroup, State


class Chat(StatesGroup):
    typing = State()
