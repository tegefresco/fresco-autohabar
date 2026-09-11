async def safe_delete(message):
    try:
        await message.delete()
    except Exception:
        pass


async def safe_edit(message, text, **kwargs):
    try:
        await message.edit_text(text, **kwargs)
    except Exception:
        try:
            await message.answer(text, **kwargs)
        except Exception:
            pass