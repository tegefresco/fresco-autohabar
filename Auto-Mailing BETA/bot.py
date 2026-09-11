import re
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)

from config import BOT_TOKEN
from database import (
    init_db, get_language, save_language,
    get_subscription, save_subscription,
    is_prem, set_prem,
    count_user_accounts, get_user_accounts,
    remove_user_account, set_account_active,
)

import userbot

import language as language_mod
import subscription as sub_mod
from subscription import is_subscribed, require_subscription, require_subscription_callback
from subscription import SUBSCRIPTION_TEXT, subscription_keyboard
from utils import safe_delete, safe_edit


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

PHONE_RE = re.compile(r"^\+?\d[\d\s\-]{7,18}\d$")
CODE_RE = re.compile(r"^\d(?:\.\d){3,6}$")

MENU_BUTTONS = (
    "Авто-Рассылка", "Текст Сообщения", "Интервал", "Настройка групп",
    "Профили", "Prem BETA", "Статистика", "Помощь", "Инструкция",
)

code_timeout_tasks = {}
last_bot_messages = {}


async def answer_unique(message: Message, text: str, **kwargs):

    chat_id = message.chat.id
    key = (chat_id, text)

    old_message_id = last_bot_messages.get(key)

    if old_message_id:
        try:
            await bot.delete_message(
                chat_id=chat_id,
                message_id=old_message_id,
            )
        except Exception:
            pass

    new_message = await message.answer(text, **kwargs)

    last_bot_messages[key] = new_message.message_id

    return new_message



def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Авто-Рассылка", style="danger"),
             KeyboardButton(text="Текст Сообщения", style="danger")],
            [KeyboardButton(text="Интервал", style="danger"),
             KeyboardButton(text="Настройка групп", style="danger")],
            [KeyboardButton(text="Профили", style="success"),
             KeyboardButton(text="Prem BETA", style="success")],
            [KeyboardButton(text="Статистика", style="success"),
             KeyboardButton(text="Помощь", style="success")],
            [KeyboardButton(text="Инструкция", style="primary")],
        ],
        resize_keyboard=True,
    )


def add_account_button_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👤 Добавить аккаунт", callback_data="add_account")
    ]])


def add_account_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📲 По SMS-коду",
                callback_data="login_sms",
                style="success",
            )
        ],
        [
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data="back_to_welcome",
                style="danger",
            )
        ],
    ])


def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_account", style="danger")
    ]])


def phone_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def code_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👁 Посмотреть код", url="tg://user?id=777000")],
        [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="retry_code")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_code")],
    ])



def welcome_text():
    return (
        "🤖 <b>Auto-Task</b> - помощник для автоматизации действий в Telegram.\n\n"
        "<b>Например</b>, он позволяет отправлять сообщения сразу в несколько "
        "чатов в заданное время.\n\n"
        "<blockquote>🆓 Бесплатная версия Habar Jarvis бот.</blockquote> "
    )


def main_menu_text():
    return "📋 <b>Главное меню —></b>"


def add_account_text():
    return (
        "👤 <b>Добавить профиль</b>\n\n"
        "<blockquote>🔒 <b>Аккаунт используется ТОЛЬКО для авторассылки. "
        "Личная переписка не читается и не сохраняется.</b></blockquote>\n\n"
        "Выберите способ входа:"
    )


def phone_text():
    return (
        "📱 <b>Введите номер телефона:</b>\n\n"
        "Пример: <code>+998901234567</code>\n\n"
        "👇 Или нажмите кнопку ниже"
    )



async def on_after_lang(message, user_id):
    if not await is_subscribed(bot, user_id):
        await message.answer(SUBSCRIPTION_TEXT, reply_markup=subscription_keyboard(), parse_mode="HTML")
        return
    await message.answer(welcome_text(), reply_markup=add_account_button_keyboard(), parse_mode="HTML")
    await message.answer(main_menu_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")


async def on_after_subscribe(message, user_id):
    await message.answer(welcome_text(), reply_markup=add_account_button_keyboard(), parse_mode="HTML")
    await message.answer(main_menu_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")



language_mod.register(dp, on_after_lang)
sub_mod.register(dp, bot, on_after_subscribe)



def profiles_limit(user_id) -> int:
    return 5 if is_prem(user_id) else 1


def profiles_keyboard(user_id):
    accounts = get_user_accounts(user_id)
    limit = profiles_limit(user_id)
    rows = []

    for phone, active, username, first_name in accounts:
        status = "✅" if active else "🟢"
        short = phone if len(phone) <= 10 else phone[-10:]
        rows.append([
            InlineKeyboardButton(text=f"{status} {short}", callback_data=f"acc_toggle_{phone}", style="success"),
            InlineKeyboardButton(text="🗑", callback_data=f"acc_delete_{phone}", style="danger"),
        ])

    if len(accounts) < limit:
        rows.append([InlineKeyboardButton(text="➕ Добавить аккаунт", callback_data="add_account", style="success")])

    rows.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="profiles_close", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def profiles_text(user_id):
    accounts = get_user_accounts(user_id)
    limit = profiles_limit(user_id)
    count = len(accounts)
    header = f"👤 <b>Профили ({count}/{limit})</b>\n\n"
    if count == 0:
        body = "Аккаунты ещё не добавлены.\n\n"
    else:
        body = "Нажмите, чтобы выбрать аккаунт:\n\n"
    body += "💎 <b>С подпиской PRO можно добавить до 5 профилей.</b>"
    return header + body


async def show_profiles(message: Message, user_id: int):
    await message.answer(
        profiles_text(user_id),
        reply_markup=profiles_keyboard(user_id),
        parse_mode="HTML",
    )



@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    language = get_language(user_id)

    if language is None:
        await message.answer(
            language_mod.LANG_TEXT,
            reply_markup=language_mod.language_keyboard(),
            parse_mode="HTML",
        )
        return

    if not await is_subscribed(bot, user_id):
        await message.answer(SUBSCRIPTION_TEXT, reply_markup=subscription_keyboard(), parse_mode="HTML")
        return

    await message.answer(welcome_text(), reply_markup=add_account_button_keyboard(), parse_mode="HTML")
    await message.answer(main_menu_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")


@dp.message(Command("prem"))
async def prem_command(message: Message):
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)
    arg = args[1].strip().lower() if len(args) > 1 else "on"

    if arg in ("off", "0", "false", "выкл"):
        set_prem(user_id, False)
        await message.answer("💎 <b>PRO отключён.</b>\n\nЛимит профилей: <b>1</b>.", parse_mode="HTML")
        return

    set_prem(user_id, True)
    await message.answer("💎 <b>PRO активирован!</b>\n\nЛимит профилей: <b>5</b>.", parse_mode="HTML")



@dp.callback_query(F.data == "add_account")
async def add_account(callback: CallbackQuery):
    if not await require_subscription_callback(bot, callback):
        return

    user_id = callback.from_user.id
    if count_user_accounts(user_id) >= profiles_limit(user_id):
        await callback.answer(
            "❌ Достигнут лимит профилей.\n💎 Оформите PRO, чтобы добавить до 5 аккаунтов.",
            show_alert=True,
        )
        return

    await safe_edit(callback.message, add_account_text(), reply_markup=add_account_keyboard(), parse_mode="HTML")
    await callback.answer()


@dp.callback_query(F.data == "login_sms")
async def login_sms(callback: CallbackQuery):
    if not await require_subscription_callback(bot, callback):
        return
    await safe_delete(callback.message)
    await callback.message.answer(phone_text(), reply_markup=cancel_keyboard(), parse_mode="HTML")
    await callback.message.answer("👇", reply_markup=phone_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "back_to_welcome")
async def back_to_welcome(callback: CallbackQuery):
    await safe_edit(
        callback.message,
        welcome_text(),
        reply_markup=add_account_button_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data == "cancel_add_account")
async def cancel_add_account(callback: CallbackQuery):
    if not await require_subscription_callback(bot, callback):
        return
    await safe_edit(callback.message, add_account_text(), reply_markup=add_account_keyboard(), parse_mode="HTML")
    await callback.message.answer(main_menu_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()



async def code_timeout(user_id: int, code_message: Message):
    try:
        await asyncio.sleep(90)
        if not userbot.is_pending(user_id):
            return
        await userbot.cancel_pending(user_id)
        code_timeout_tasks.pop(user_id, None)
        await code_message.edit_text(
            "⏳ <b>Время истекло. Попробуйте снова.</b>\n",
            reply_markup=code_keyboard(),
            parse_mode="HTML",
        )
    except asyncio.CancelledError:
        pass
    except Exception as error:
        print("Ошибка таймера кода:", error)



async def handle_phone(message: Message, raw_phone: str):
    if not await require_subscription(bot, message):
        return

    user_id = message.from_user.id
    if count_user_accounts(user_id) >= profiles_limit(user_id):
        await message.answer(
            "❌ <b>Достигнут лимит профилей.</b>\n\n"
            "💎 Оформите PRO, чтобы добавить до 5 аккаунтов.",
            parse_mode="HTML",
        )
        return

    phone = raw_phone.strip().replace(" ", "").replace("-", "")
    if not phone.startswith("+"):
        phone = "+" + phone

    wait_message = await message.answer("⏳ <b>Отправляем код, подождите...</b>", parse_mode="HTML")

    try:
        await userbot.send_code(user_id, phone)
    except Exception as error:
        await safe_edit(
            wait_message,
            f"❌ <b>Не удалось отправить код</b>\n\n<code>{error}</code>",
            parse_mode="HTML",
        )
        return

    await safe_delete(wait_message)

    code_message = await message.answer(
        f"✅ <b>Код подтверждения отправлен!</b>\n\n"
        f"📱 Номер: <code>{phone}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ <b>ВАЖНО</b>\n\n"
        f"✏️ Введите код так: <b>1.2.3.4.5</b>",
        reply_markup=code_keyboard(),
        parse_mode="HTML",
    )

    old_task = code_timeout_tasks.pop(user_id, None)
    if old_task:
        old_task.cancel()
    code_timeout_tasks[user_id] = asyncio.create_task(code_timeout(user_id, code_message))

    await message.answer("👇", reply_markup=ReplyKeyboardRemove())


@dp.message(F.contact)
async def receive_phone_contact(message: Message):
    await handle_phone(message, message.contact.phone_number)


@dp.message(F.text.regexp(PHONE_RE))
async def receive_phone_text(message: Message):
    if message.text in MENU_BUTTONS:
        return
    await handle_phone(message, message.text)


async def on_account_added(message: Message, user_id: int):
    task = code_timeout_tasks.pop(user_id, None)
    if task:
        task.cancel()

    info = userbot.get_pending_info(user_id)
    phone = username = first_name = None
    if info:
        phone, username, first_name = info

    userbot.finish_login(user_id)
    display_name = first_name or "Аккаунт"
    name_part = f"{display_name} (@{username})" if username else display_name

    await message.answer(f"✅ <b>Аккаунт добавлен:</b> {name_part}", parse_mode="HTML")
    await show_profiles(message, user_id)


@dp.message(F.text.regexp(CODE_RE))
async def receive_code(message: Message):
    user_id = message.from_user.id
    if not userbot.is_pending(user_id):
        await message.answer("❌ Нет активного входа. Начните заново.")
        return

    task = code_timeout_tasks.pop(user_id, None)
    if task:
        task.cancel()

    code = message.text.replace(".", "").strip()
    result = await userbot.sign_in(user_id, code)

    if result == "ok":
        await on_account_added(message, user_id)
        return
    if result == "password_needed":
        userbot.set_waiting_password(user_id, True)
        await message.answer("🔐 <b>Введите пароль двухэтапной аутентификации:</b>", parse_mode="HTML")
        return
    await message.answer(f"❌ <b>Ошибка входа</b>\n\n<code>{result}</code>", parse_mode="HTML")


@dp.message()
async def receive_password(message: Message):
    user_id = message.from_user.id
    if not userbot.is_waiting_password(user_id):
        return
    result = await userbot.sign_in_password(user_id, message.text)
    if result == "ok":
        await on_account_added(message, user_id)
    else:
        await message.answer(f"❌ <b>Ошибка:</b>\n<code>{result}</code>", parse_mode="HTML")



@dp.callback_query(F.data == "view_code")
async def view_code(callback: CallbackQuery):
    await callback.answer("Код отправлен в приложение Telegram на этот номер.", show_alert=True)


@dp.callback_query(F.data == "retry_code")
async def retry_code(callback: CallbackQuery):
    user_id = callback.from_user.id
    task = code_timeout_tasks.pop(user_id, None)
    if task:
        task.cancel()
    await userbot.cancel_pending(user_id)

    await safe_edit(callback.message, phone_text(), reply_markup=cancel_keyboard(), parse_mode="HTML")
    await callback.message.answer("👇", reply_markup=phone_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "cancel_code")
async def cancel_code(callback: CallbackQuery):
    user_id = callback.from_user.id
    task = code_timeout_tasks.pop(user_id, None)
    if task:
        task.cancel()
    await userbot.cancel_pending(user_id)

    await safe_edit(callback.message, "❌ <b>Подключение аккаунта отменено.</b>", parse_mode="HTML")
    await callback.message.answer(main_menu_text(), reply_markup=main_menu_keyboard(), parse_mode="HTML")
    await callback.answer()



@dp.message(F.text == "✉️ Авто-Рассылка")
async def menu_auto_sending(message: Message):
    if not await require_subscription(bot, message):
        return
    await message.answer("✉️ <b>Авто-Рассылка</b>\n\nЗдесь позже будет запуск автоматической рассылки.", parse_mode="HTML")


@dp.message(F.text == "📝 Текст Сообщения")
async def menu_message_text(message: Message):
    if not await require_subscription(bot, message):
        return
    await message.answer("📝 <b>Текст Сообщения</b>\n\nЗдесь позже можно будет задать текст для рассылки.", parse_mode="HTML")


@dp.message(F.text == "⏱ Интервал")
async def menu_interval(message: Message):
    if not await require_subscription(bot, message):
        return
    await message.answer("⏱ <b>Интервал</b>\n\nЗдесь позже можно будет настроить интервал отправки.", parse_mode="HTML")


@dp.message(F.text == "👥 Настройка групп")
async def menu_groups(message: Message):
    if not await require_subscription(bot, message):
        return
    await message.answer("👥 <b>Настройка групп</b>\n\nЗдесь позже добавим управление группами.", parse_mode="HTML")


@dp.message(F.text == "👤 Профили")
async def menu_profiles(message: Message):
    if not await require_subscription(bot, message):
        return
    await show_profiles(message, message.from_user.id)


@dp.message(F.text == "💎 Prem BETA")
async def menu_prem(message: Message):
    if not await require_subscription(bot, message):
        return
    await message.answer("💎 <b>Prem BETA</b>\n\nЗдесь позже будет информация о премиум-возможностях.", parse_mode="HTML")


@dp.message(F.text == "📊 Статистика")
async def menu_stats(message: Message):
    if not await require_subscription(bot, message):
        return
    await message.answer("📊 <b>Статистика</b>\n\nЗдесь позже будет статистика рассылок.", parse_mode="HTML")


@dp.message(F.text == "🆘 Помощь")
async def menu_help(message: Message):
    if not await require_subscription(bot, message):
        return
    await message.answer("🆘 <b>Помощь</b>\n\nЗдесь позже будет раздел с поддержкой.", parse_mode="HTML")


@dp.message(F.text == "📖 Инструкция")
async def menu_instruction(message: Message):
    if not await require_subscription(bot, message):
        return
    await message.answer("📖 <b>Инструкция</b>\n\nЗдесь будет инструкция по использованию бота.", parse_mode="HTML")



@dp.callback_query(F.data == "profiles_close")
async def profiles_close(callback: CallbackQuery):
    await safe_delete(callback.message)
    await callback.answer()


@dp.callback_query(F.data == "proxy_settings")
async def proxy_settings(callback: CallbackQuery):
    await callback.answer("🌐 Настройка прокси скоро появится.", show_alert=True)


@dp.callback_query(F.data.startswith("acc_toggle_"))
async def acc_toggle(callback: CallbackQuery):
    user_id = callback.from_user.id
    phone = callback.data.replace("acc_toggle_", "", 1)
    accounts = {row[0]: row[1] for row in get_user_accounts(user_id)}
    if phone in accounts:
        set_account_active(user_id, phone, not bool(accounts[phone]))
    await safe_edit(
        callback.message,
        profiles_text(user_id),
        reply_markup=profiles_keyboard(user_id),
        parse_mode="HTML",
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("acc_delete_"))
async def acc_delete(callback: CallbackQuery):
    user_id = callback.from_user.id
    phone = callback.data.replace("acc_delete_", "", 1)
    remove_user_account(user_id, phone)
    await safe_edit(
        callback.message,
        profiles_text(user_id),
        reply_markup=profiles_keyboard(user_id),
        parse_mode="HTML",
    )
    await callback.answer("🗑 Аккаунт удалён")



async def main():
    init_db()
    print("================")
    print("🤖 Бот запущен!")
    print("================")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())