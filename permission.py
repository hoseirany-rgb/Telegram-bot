"""Permission decorators and runtime checks.

Usage:
    @require(ADMIN)
    async def cmd_lock(update, context): ...
"""
from __future__ import annotations

from functools import wraps
from typing import Callable

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from ..config import settings
from ..roles import ADMIN, OWNER, PUBLIC, SPECIAL

PROTECTED_STATUSES = {"creator", "administrator"}


async def _status(context, chat_id: int, user_id: int) -> str:
    if user_id in settings.owner_ids:
        return OWNER
    if chat_id and context and context.bot:
        try:
            m = await context.bot.get_chat_member(chat_id, user_id)
            st = getattr(m, "status", "")
            if st in {"creator"}:
                return OWNER
            if st in PROTECTED_STATUSES:
                return ADMIN
        except Exception:
            pass
    return PUBLIC


def _deny_text(required: str) -> str:
    table = {
        OWNER:   "این فرمان فقط برای مالک ربات قابل اجراست.",
        ADMIN:   "این فرمان فقط برای ادمین‌های گروه قابل اجراست.",
        SPECIAL: "این فرمان فقط برای کاربران ویژه قابل اجراست.",
        PUBLIC:  "این فرمان در دسترس نیست.",
    }
    return table.get(required, "دسترسی ندارید.")


def require(required: str = ADMIN) -> Callable:
    """Decorator that enforces permission tier at command entry."""

    def wrap(fn: Callable):
        @wraps(fn)
        async def inner(update: Update, context: ContextTypes.DEFAULT_TYPE):
            msg = update.effective_message
            chat = update.effective_chat
            user = update.effective_user
            if not chat or not user or not msg:
                return
            ok, why = await _check(context, chat, user, required)
            if not ok:
                await msg.reply_text(why or _deny_text(required))
                return None
            return await fn(update, context)

        return inner

    return wrap


async def _check(context, chat, user, required: str):
    # Private chat: only OWNER can run admin commands
    if chat.type == ChatType.PRIVATE and required in {ADMIN}:
        if user.id in settings.owner_ids:
            return True, None
        return False, _deny_text(required)

    level = await _status(context, chat.id, user.id)
    rank = {PUBLIC: 0, SPECIAL: 1, ADMIN: 2, OWNER: 3}
    if rank[level] >= rank[required]:
        return True, None
    return False, _deny_text(required)


async def is_owner(user_id: int) -> bool:
    return user_id in settings.owner_ids


async def is_protected_target(context, chat_id: int, user_id: int) -> bool:
    if user_id in settings.owner_ids:
        return True
    try:
        m = await context.bot.get_chat_member(chat_id, user_id)
        return getattr(m, "status", "") in PROTECTED_STATUSES
    except Exception:
        return False
