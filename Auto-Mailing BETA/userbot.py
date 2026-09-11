import os
import uuid

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from config import API_ID, API_HASH
from database import add_user_account

SESSIONS_DIR = "sessions"

os.makedirs(SESSIONS_DIR, exist_ok=True)

pending_logins: dict[int, dict] = {}


async def send_code(user_id: int, phone: str) -> None:
    old_data = pending_logins.pop(user_id, None)

    if old_data:
        try:
            await old_data["client"].disconnect()
        except Exception:
            pass

    session_name = os.path.join(
        SESSIONS_DIR,
        f"login_{user_id}_{uuid.uuid4().hex[:8]}"
    )

    client = TelegramClient(session_name, API_ID, API_HASH)

    await client.connect()

    try:
        sent = await client.send_code_request(phone)
    except Exception:
        await client.disconnect()
        raise

    pending_logins[user_id] = {
        "client": client,
        "phone": phone,
        "phone_code_hash": sent.phone_code_hash,
        "session_name": session_name,
        "waiting_password": False,
    }


async def resend_code(user_id: int) -> str:
    data = pending_logins.get(user_id)

    if not data:
        return "no_pending"

    client = data["client"]
    phone = data["phone"]

    try:
        sent = await client.send_code_request(phone)

        data["phone_code_hash"] = sent.phone_code_hash
        data["waiting_password"] = False

        return phone

    except Exception as error:
        return f"error: {error}"


async def sign_in(user_id: int, code: str) -> str:
    data = pending_logins.get(user_id)

    if not data:
        return "no_pending"

    client = data["client"]
    phone = data["phone"]

    try:
        await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=data["phone_code_hash"],
        )

        await _save_account(user_id, data)

        return "ok"

    except SessionPasswordNeededError:
        data["waiting_password"] = True
        return "password_needed"

    except Exception as error:
        return f"error: {error}"


async def sign_in_password(user_id: int, password: str) -> str:
    data = pending_logins.get(user_id)

    if not data:
        return "no_pending"

    client = data["client"]

    try:
        await client.sign_in(password=password)

        await _save_account(user_id, data)

        return "ok"

    except Exception as error:
        return f"error: {error}"


async def _save_account(user_id: int, data: dict) -> None:
    client = data["client"]
    phone = data["phone"]
    session_name = data["session_name"]

    username = None
    first_name = None

    try:
        me = await client.get_me()

        if me:
            username = me.username
            first_name = me.first_name

    except Exception as error:
        print("Не удалось получить me:", error)

    try:
        add_user_account(
            user_id,
            phone,
            session_name,
            username=username,
            first_name=first_name
        )

    except Exception as error:
        print("Не удалось сохранить аккаунт в БД:", error)

    data["username"] = username
    data["first_name"] = first_name


async def cancel_pending(user_id: int) -> None:
    data = pending_logins.pop(user_id, None)

    if not data:
        return

    try:
        await data["client"].disconnect()
    except Exception:
        pass


def get_pending_info(user_id: int):
    data = pending_logins.get(user_id)

    if not data:
        return None

    return (
        data.get("phone"),
        data.get("username"),
        data.get("first_name")
    )


def finish_login(user_id: int) -> None:
    pending_logins.pop(user_id, None)


def is_pending(user_id: int) -> bool:
    return user_id in pending_logins


def is_waiting_password(user_id: int) -> bool:
    data = pending_logins.get(user_id)

    return bool(data and data.get("waiting_password"))


def set_waiting_password(user_id: int, value: bool = True) -> None:
    if user_id in pending_logins:
        pending_logins[user_id]["waiting_password"] = value