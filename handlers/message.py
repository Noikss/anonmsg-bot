import logging
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    get_user, save_message, is_sender_blocked,
    save_sender_map, get_sender_id
)
from keyboards.inline import (
    received_msg_keyboard, confirm_block_keyboard,
    main_menu, share_link_keyboard, cancel_reply_keyboard
)
from utils.helpers import hash_sender

router = Router()
logger = logging.getLogger(__name__)


class ReplyState(StatesGroup):
    waiting_reply = State()


async def send_to_receiver(bot: Bot, receiver_id: int, sender_hash: str,
                           message: Message, header: str):
    kb = received_msg_keyboard(sender_hash)

    if message.text:
        await bot.send_message(receiver_id, header + message.text, parse_mode="HTML", reply_markup=kb)
    elif message.photo:
        await bot.send_photo(receiver_id, message.photo[-1].file_id,
                             caption=header + (message.caption or ""), parse_mode="HTML", reply_markup=kb)
    elif message.voice:
        await bot.send_voice(receiver_id, message.voice.file_id)
        await bot.send_message(receiver_id, header, parse_mode="HTML", reply_markup=kb)
    elif message.video:
        await bot.send_video(receiver_id, message.video.file_id,
                             caption=header + (message.caption or ""), parse_mode="HTML", reply_markup=kb)
    elif message.document:
        await bot.send_document(receiver_id, message.document.file_id,
                                caption=header + (message.caption or ""), parse_mode="HTML", reply_markup=kb)
    elif message.sticker:
        await bot.send_sticker(receiver_id, message.sticker.file_id)
        await bot.send_message(receiver_id, header, parse_mode="HTML", reply_markup=kb)
    elif message.video_note:
        await bot.send_video_note(receiver_id, message.video_note.file_id)
        await bot.send_message(receiver_id, header, parse_mode="HTML", reply_markup=kb)
    else:
        return False
    return True


@router.message(F.func(lambda m: True))
async def handle_any_message(message: Message, bot: Bot, state: FSMContext):
    data = await state.get_data()
    current_state = await state.get_state()

    # --- Режим ожидания ответа (нажали кнопку "Ответить") ---
    if current_state == ReplyState.waiting_reply.state:
        sender_hash = data.get("reply_hash")
        sender_id = data.get("reply_to_id")

        if not sender_id:
            await message.answer("❌ Не удалось найти отправителя.")
            await state.clear()
            return

        header = f"↩️ <b>Ответ на твоё анонимное сообщение</b>\n<code>#{sender_hash[:8]}</code>\n\n"
        try:
            await send_to_receiver(bot, sender_id, sender_hash, message, header)
            await message.answer("✅ Ответ отправлен.")
        except Exception as e:
            logger.error(f"reply send error: {e}")
            await message.answer("❌ Не удалось отправить.")
        await state.clear()
        return

    # --- Режим отправки анонимного сообщения ---
    if current_state == "sending":
        receiver_id = data.get("receiver_id")
        sender_hash = hash_sender(message.from_user.id, receiver_id)
        logger.info(f"SENDING: from={message.from_user.id} to={receiver_id} hash={sender_hash}")

        if await is_sender_blocked(receiver_id, sender_hash):
            await message.answer("🚫 Получатель заблокировал тебя.")
            return

        await save_sender_map(receiver_id, sender_hash, message.from_user.id)

        text_content = message.text or message.caption or ""
        media_type = None
        file_id = None
        if message.photo:
            media_type, file_id = "photo", message.photo[-1].file_id
        elif message.voice:
            media_type, file_id = "voice", message.voice.file_id
        elif message.video:
            media_type, file_id = "video", message.video.file_id
        elif message.document:
            media_type, file_id = "document", message.document.file_id
        elif message.sticker:
            media_type, file_id = "sticker", message.sticker.file_id
        elif message.video_note:
            media_type, file_id = "video_note", message.video_note.file_id
        elif not message.text:
            await message.answer("❌ Этот тип сообщений не поддерживается.")
            return

        await save_message(receiver_id, sender_hash, text_content, media_type, file_id)

        header = f"💌 <b>Анонимное сообщение</b>\n<code>#{sender_hash[:8]}</code>\n\n"
        try:
            ok = await send_to_receiver(bot, receiver_id, sender_hash, message, header)
            if ok:
                await message.answer("✅ Сообщение отправлено анонимно!")
            else:
                await message.answer("❌ Этот тип сообщений не поддерживается.")
        except Exception as e:
            logger.error(f"deliver error: {e}")
            await message.answer("❌ Не удалось доставить сообщение.")

        await state.clear()
        return

    # --- Главное меню ---
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

@router.callback_query(F.data.startswith("reply:"))
async def cb_reply(call: CallbackQuery, state: FSMContext):
    sender_hash = call.data.split(":")[1]
    sender_id = await get_sender_id(call.from_user.id, sender_hash)

    if not sender_id:
        await call.answer("❌ Не могу найти отправителя.", show_alert=True)
        return

    await state.set_state(ReplyState.waiting_reply)
    await state.update_data(reply_hash=sender_hash, reply_to_id=sender_id)
    await call.message.answer(
        "✏️ Напиши ответ — отправлю анонимно:",
        reply_markup=cancel_reply_keyboard()
    )
    await call.answer()


@router.callback_query(F.data == "cancel_reply")
async def cb_cancel_reply(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("❌ Ответ отменён.")
    await call.answer()


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
