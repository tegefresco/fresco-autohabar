from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import CHANNEL_USERNAME, CHANNEL_LINK
from database import save_subscription
from utils import safe_edit


SUBSCRIPTION_TEXT = (
    "✨ <b>Остался один шаг!</b>\n"
    "📢 Подпишитесь на канал ниже — и бот откроется полностью.\n\n"
    "🎁 <b>Что вас ждёт:</b>\n"
    "• 🤖 <b>Автопостинг</b> в группы — даже пока вы спите\n"
    "• 📊 <b>Живая статистика</b> — сколько и куда ушло\n"
    "• 💬 <b>Автоответ</b> на личные сообщения\n"
    "• 🔔 <b>Автоподписка</b> на канал, который требует бот-охранник.\n\n"
    "👇🏻 Подпишитесь и нажмите «✅ Я подписался»"
)


def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")],
    ])


async def is_subscribed(bot, user_id) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        subscribed = member.status in ("member", "administrator", "creator")
        save_subscription(user_id, subscribed)
        return subscribed
    except Exception as error:
        print("Ошибка проверки подписки:", error)
        return False


async def require_subscription(bot, message: Message) -> bool:
    if await is_subscribed(bot, message.from_user.id):
        return True
    await message.answer(SUBSCRIPTION_TEXT, reply_markup=subscription_keyboard(), parse_mode="HTML")
    return False


async def require_subscription_callback(bot, callback: CallbackQuery) -> bool:
    if await is_subscribed(bot, callback.from_user.id):
        return True
    await callback.answer(
        "❌ Вы не подписаны на канал.\nПодпишитесь и нажмите «Я подписался».",
        show_alert=True,
    )
    return False


def register(dp, bot, on_after_subscribe):
    """
    on_after_subscribe(message, user_id) -> вызывается после успешной подписки,
    чтобы отправить приветствие + меню. Реализация остаётся в bot.py.
    """

    @dp.callback_query(F.data == "check_subscription")
    async def check_subscription(callback: CallbackQuery):
        user_id = callback.from_user.id
        if not await is_subscribed(bot, user_id):
            await callback.answer(
                "❌ Вы ещё не подписались на канал.\nПодпишитесь и нажмите «✅ Я подписался».",
                show_alert=True,
            )
            return
        await safe_edit(
            callback.message,
            "✅ <b>Подписка подтверждена!</b>\nМожете пользоваться ботом.",
            parse_mode="HTML",
        )
        await on_after_subscribe(callback.message, user_id)
        await callback.answer()