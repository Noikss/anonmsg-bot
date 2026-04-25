from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.db import (
    get_user, save_message, is_sender_blocked,
    save_sender_map, get_sender_id
)
from keyboards.inline import (
    block_sender_keyboard, confirm_block_keyboard,
    main_menu, share_link_keyboard
)
from utils.helpers import hash_sender

router = Router()


async def send_to_receiver(bot: Bot, receiver_id: int, sender_hash: str,
                           message: Message, header: str):
    kb = block_sender_keyboard(sender_hash)

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

    # --- Ответ на анонимное сообщение через Reply ---
    if message.reply_to_message and current_state != "sending":
        reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""

        sender_hash = None
        for line in reply_text.split("\n"):
            line = line.strip()
            if line.startswith("#") and len(line) == 9:
                sender_hash = line[1:]
                break

        if sender_hash:
            sender_id = await get_sender_id(message.from_user.id, sender_hash)
            if sender_id:
                header = "↩️ <b>Ответ на твоё анонимное сообщение</b>\n\n"
                try:
                    await send_to_receiver(bot, sender_id, sender_hash, message, header)
                    await message.answer("✅ Ответ отправлен.")
                except Exception:
                    await message.answer("❌ Не удалось отправить — пользователь заблокировал бота.")
                return
            else:
                await message.answer("❌ Не могу найти отправителя — данные устарели.")
                return

    # --- Режим отправки анонимного сообщения ---
    if current_state == "sending":
        receiver_id = data.get("receiver_id")
        sender_hash = hash_sender(message.from_user.id, receiver_id)

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
        except Exception:
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
