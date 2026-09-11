from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import get_language, save_language
from utils import safe_edit


LANG_TEXT = "🇷🇺 <b>Выберите язык</b>\n🇬🇧 <b>Choose language</b>"


def language_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Ru", callback_data="lang_ru"),
        InlineKeyboardButton(text="🇬🇧 En", callback_data="lang_en"),
    ]])


def register(dp, on_after_lang):
    """
    on_after_lang(callback_or_message, user_id) -> вызывается после сохранения языка,
    чтобы отправить подписку или меню. Реализация остаётся в bot.py.
    """

    @dp.message(F.text == "/lang")
    async def lang_cmd(message: Message):
        await message.answer(LANG_TEXT, reply_markup=language_keyboard(), parse_mode="HTML")

    @dp.message(F.text.startswith("/lang"))
    async def lang_cmd2(message: Message):
        await message.answer(LANG_TEXT, reply_markup=language_keyboard(), parse_mode="HTML")

    async def _save(callback: CallbackQuery, lang: str, ok_text: str):
        user_id = callback.from_user.id
        save_language(user_id, lang)
        await safe_edit(callback.message, ok_text, parse_mode="HTML")
        await on_after_lang(callback.message, user_id)
        await callback.answer()

    @dp.callback_query(F.data == "lang_ru")
    async def lang_ru(callback: CallbackQuery):
        await _save(callback, "ru", "✅ <b>Язык сохранён.</b>\nИзменить: /lang")

    @dp.callback_query(F.data == "lang_en")
    async def lang_en(callback: CallbackQuery):
        await _save(callback, "en", "✅ <b>Language saved.</b>\nChange: /lang")