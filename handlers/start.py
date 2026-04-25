from aiogram import Router, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN
from database.db import get_user, create_user, get_user_by_token
from keyboards.inline import main_menu, block_sender_keyboard
from utils.helpers import generate_token, hash_sender

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    await state.clear()
    args = message.text.split(maxsplit=1)
    token_arg = args[1] if len(args) > 1 else None

    user = await get_user(message.from_user.id)

    # Регистрируем если новый
    if not user:
        token = generate_token()
        await create_user(
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            full_name=message.from_user.full_name,
            token=token
        )
        user = await get_user(message.from_user.id)

    # Если пришёл по чужой ссылке — режим отправки
    if token_arg and token_arg != user["link_token"]:
        receiver = await get_user_by_token(token_arg)
        if not receiver:
            await message.answer("❌ Ссылка недействительна.")
            return

        await state.set_state("sending")
        await state.update_data(
            receiver_id=receiver["user_id"],
            receiver_name=receiver["full_name"]
        )
        await message.answer(
            f"👤 Ты пишешь <b>{receiver['full_name']}</b> анонимно.\n\n"
            f"Отправь текст, фото или голосовое — это дойдёт без раскрытия личности.",
            parse_mode="HTML"
        )
        return

    # Иначе — главное меню
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={user['link_token']}"
    await message.answer(
        f"👋 Привет, <b>{message.from_user.first_name}</b>!\n\n"
        f"Это твоя анонимная страница. Поделись ссылкой — и люди смогут писать тебе анонимно.\n\n"
        f"🔗 <code>{link}</code>",
        parse_mode="HTML",
        reply_markup=main_menu(me.username, user["link_token"])
    )
