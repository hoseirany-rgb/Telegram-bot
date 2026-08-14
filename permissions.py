from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..config import settings
from ..constants import PROTECTED_STATUSES


async def get_member(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int):
    return await context.bot.get_chat_member(chat_id, user_id)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or not update.effective_user:
        return False
    if update.effective_user.id in settings.owner_ids:
        return True
    try:
        member = await get_member(context, update.effective_chat.id, update.effective_user.id)
    except Exception:
        return False
    return getattr(member, "status", "") in PROTECTED_STATUSES


async def is_protected_target(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    if user_id in settings.owner_ids:
        return True
    try:
        member = await get_member(context, chat_id, user_id)
    except Exception:
        return False
    return getattr(member, "status", "") in PROTECTED_STATUSES
