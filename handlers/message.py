from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import (
    get_user, save_message, is_sender_blocked,
    get_user_by_token
)
from keyboards.inline import (
    block_sender_keyboard, confirm_block_keyboard,
    main_menu, share_link_keyboard
)
from utils.helpers import hash_sender

router = Router()

MEDIA_TYPES = {
    "photo": "фото",
    "voice": "голосовое",
    "video": "видео",
    "document": "файл",
    "sticker": "стикер",
    "video_note": "кружок",
}


@router.message(F.func(lambda m: True))
async def handle_any_message(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    current_state = await state.get_state()

    # Режим отправки анонимного сообщения
    if current_state == "sending":
        receiver_id = data.get("receiver_id")
        sender_hash = hash_sender(message.from_user.id, receiver_id)

        # Проверка блокировки
        if await is_sender_blocked(receiver_id, sender_hash):
            await message.answer("🚫 Получатель заблокировал тебя.")
            return

        # Определяем тип медиа
        media_type = None
        file_id = None
        text_content = ""

        if message.text:
            text_content = message.text
        elif message.photo:
            media_type = "photo"
            file_id = message.photo[-1].file_id
            text_content = message.caption or ""
        elif message.voice:
            media_type = "voice"
            file_id = message.voice.file_id
        elif message.video:
            media_type = "video"
            file_id = message.video.file_id
            text_content = message.caption or ""
        elif message.document:
            media_type = "document"
            file_id = message.document.file_id
            text_content = message.caption or ""
        elif message.sticker:
            media_type = "sticker"
            file_id = message.sticker.file_id
        elif message.video_note:
            media_type = "video_note"
            file_id = message.video_note.file_id
        else:
            await message.answer("❌ Этот тип сообщений не поддерживается.")
            return

        # Сохраняем в БД
        await save_message(receiver_id, sender_hash, text_content, media_type, file_id)

        # Отправляем получателю
        header = f"💌 <b>Анонимное сообщение</b>\n<code>#{sender_hash[:8]}</code>\n\n"
        kb = block_sender_keyboard(sender_hash)

        try:
            if not media_type:
                await bot.send_message(
                    receiver_id,
                    header + text_content,
                    parse_mode="HTML",
                    reply_markup=kb
                )
            elif media_type == "photo":
                await bot.send_photo(
                    receiver_id, file_id,
                    caption=header + text_content,
                    parse_mode="HTML",
                    reply_markup=kb
                )
            elif media_type == "voice":
                await bot.send_voice(receiver_id, file_id, reply_markup=kb)
                await bot.send_message(receiver_id, header, parse_mode="HTML")
            elif media_type == "video":
                await bot.send_video(
                    receiver_id, file_id,
                    caption=header + text_content,
                    parse_mode="HTML",
                    reply_markup=kb
                )
            elif media_type == "document":
                await bot.send_document(
                    receiver_id, file_id,
                    caption=header + text_content,
                    parse_mode="HTML",
                    reply_markup=kb
                )
            elif media_type == "sticker":
                await bot.send_sticker(receiver_id, file_id)
                await bot.send_message(receiver_id, header, parse_mode="HTML", reply_markup=kb)
            elif media_type == "video_note":
                await bot.send_video_note(receiver_id, file_id)
                await bot.send_message(receiver_id, header, parse_mode="HTML", reply_markup=kb)

            await message.answer("✅ Сообщение отправлено анонимно!")
        except Exception:
            await message.answer("❌ Не удалось доставить сообщение. Возможно, получатель заблокировал бота.")

        await state.clear()
        return

    # Не в режиме отправки — показываем меню
    user = await get_user(message.from_user.id)
    if user:
        me = await bot.get_me()
        link = f"https://t.me/{me.username}?start={user['link_token']}"
        await message.answer(
            f"🔗 Твоя ссылка:\n<code>{link}</code>\n\nПоделись ей — и тебе напишут анонимно.",
            parse_mode="HTML",
            reply_markup=main_menu(me.username, user["link_token"])
        )


# --- Callbacks ---

@router.callback_query(F.data == "my_link")
async def cb_my_link(call: CallbackQuery, bot: Bot):
    user = await get_user(call.from_user.id)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={user['link_token']}"
    await call.message.edit_text(
        f"🔗 Твоя анонимная ссылка:\n\n<code>{link}</code>\n\nОтправь её в соцсетях или друзьям.",
        parse_mode="HTML",
        reply_markup=share_link_keyboard(me.username, user["link_token"])
    )
    await call.answer()


@router.callback_query(F.data == "back_main")
async def cb_back_main(call: CallbackQuery, bot: Bot):
    user = await get_user(call.from_user.id)
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={user['link_token']}"
    await call.message.edit_text(
        f"🔗 Твоя ссылка:\n<code>{link}</code>",
        parse_mode="HTML",
        reply_markup=main_menu(me.username, user["link_token"])
    )
    await call.answer()


@router.callback_query(F.data == "my_stats")
async def cb_my_stats(call: CallbackQuery):
    from database.db import DB_PATH
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM messages WHERE receiver_id = ?", (call.from_user.id,)
        ) as cur:
            total = (await cur.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0", (call.from_user.id,)
        ) as cur:
            unread = (await cur.fetchone())[0]

    await call.answer(
        f"📊 Всего сообщений: {total}\n📬 Непрочитанных: {unread}",
        show_alert=True
    )


@router.callback_query(F.data.startswith("block:"))
async def cb_block(call: CallbackQuery):
    sender_hash = call.data.split(":")[1]
    await call.message.reply(
        "Заблокировать этого отправителя? Он больше не сможет писать тебе.",
        reply_markup=confirm_block_keyboard(sender_hash)
    )
    await call.answer()


@router.callback_query(F.data.startswith("block_confirm:"))
async def cb_block_confirm(call: CallbackQuery):
    sender_hash = call.data.split(":")[1]
    from database.db import block_sender
    await block_sender(call.from_user.id, sender_hash)
    await call.message.edit_text("🚫 Отправитель заблокирован.")
    await call.answer("Заблокировано", show_alert=False)


@router.callback_query(F.data == "block_cancel")
async def cb_block_cancel(call: CallbackQuery):
    await call.message.delete()
    await call.answer("Отменено")
