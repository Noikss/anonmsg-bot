from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_ID
from database.db import get_stats

router = Router()


@router.message(Command("stats"), F.from_user.id == ADMIN_ID)
async def cmd_stats(message: Message):
    users, msgs = await get_stats()
    await message.answer(
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Пользователей: <b>{users}</b>\n"
        f"💌 Сообщений всего: <b>{msgs}</b>",
        parse_mode="HTML"
    )
