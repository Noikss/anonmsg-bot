from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu(bot_username: str, token: str) -> InlineKeyboardMarkup:
    link = f"https://t.me/{bot_username}?start={token}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_link")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="my_stats")],
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", switch_inline_query=link)],
    ])


def share_link_keyboard(bot_username: str, token: str) -> InlineKeyboardMarkup:
    link = f"https://t.me/{bot_username}?start={token}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться", url=f"https://t.me/share/url?url={link}&text=Напиши мне анонимно!")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_main")],
    ])


def block_sender_keyboard(sender_hash: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚫 Заблокировать отправителя", callback_data=f"block:{sender_hash}")],
    ])


def confirm_block_keyboard(sender_hash: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, заблокировать", callback_data=f"block_confirm:{sender_hash}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="block_cancel"),
        ]
    ])
