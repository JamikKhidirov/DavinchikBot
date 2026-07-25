import asyncio

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.user_times = {}

    async def __call__(self, handler, event, data):
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id:
            now = asyncio.get_event_loop().time()
            last_time = self.user_times.get(user_id, 0)
            if now - last_time < self.rate_limit:
                return
            self.user_times[user_id] = now

        return await handler(event, data)
