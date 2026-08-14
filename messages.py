from __future__ import annotations

import re
import time
import unicodedata
from collections import defaultdict, deque

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

from ..constants import DEFAULT_MUTE_SECONDS
from ..db import db
from ..utils import ban_user, extract_links, is_admin, kick_user, mute_user, safe_delete

USER_WINDOWS: dict[tuple[int, int], deque[tuple[float, str, int]]] = defaultdict(lambda: deque(maxlen=40))


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("ي", "ی").replace("ك", "ک").replace("‌", " ")
    text = re.sub(r"https?://\S+|www\.\S+|t\.me/\S+", " ", text)
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_forward(msg) -> bool:
    return bool(msg.forward_origin or msg.forward_from_chat or msg.is_automatic_forward)


async def apply_violation(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, reason: str, settings_dict: dict) -> int:
    count = await db.add_warning(chat_id, user_id, reason)
    await db.incr_stat(chat_id, "warnings")
    warn_limit = int(settings_dict.get("warn_limit", 3))
    action = settings_dict.get("action_on_limit", "kick")
    if count >= warn_limit:
        if action == "ban":
            await ban_user(context, chat_id, user_id)
            await db.incr_stat(chat_id, "bans")
        else:
            await kick_user(context, chat_id, user_id)
            await db.incr_stat(chat_id, "kicks")
        await db.reset_warnings(chat_id, user_id)
    elif count >= max(2, warn_limit - 1):
        await mute_user(context, chat_id, user_id, DEFAULT_MUTE_SECONDS)
        await db.incr_stat(chat_id, "mutes")
    return count


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    if not msg or not chat or not user:
        return
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    if await is_admin(update, context) or user.is_bot:
        return

    settings_dict = await db.get_group_settings(chat.id)
    if not settings_dict.get("enabled", True):
        return

    await db.incr_stat(chat.id, "messages")
    text = msg.text or msg.caption or ""
    links = extract_links(msg)
    now = time.time()
    key = (chat.id, user.id)
    window = USER_WINDOWS[key]
    norm = normalize_text(text)
    window.append((now, norm, len(links)))

    burst_window = int(settings_dict.get("burst_window", 8))
    burst_limit = int(settings_dict.get("burst_limit", 7))
    dup_window = int(settings_dict.get("duplicate_window", 90))
    dup_limit = int(settings_dict.get("duplicate_limit", 3))
    max_links = int(settings_dict.get("max_links", 1))

    while window and now - window[0][0] > max(burst_window, dup_window):
        window.popleft()

    burst_count = sum(1 for ts, _, _ in window if now - ts <= burst_window)
    dup_count = sum(1 for ts, fp, _ in window if fp and fp == norm and now - ts <= dup_window)

    reason = ""
    if settings_dict.get("antilink", False) and links:
        await db.incr_stat(chat.id, "links", len(links))
        reason = "ارسال لینک در این گروه محدود است."
    elif settings_dict.get("anti_forward", False) and is_forward(msg):
        reason = "ارسال پیام فورواردی مجاز نیست."
    elif settings_dict.get("antispam", True) and burst_count >= burst_limit:
        reason = "ارسال پشت‌سرهم به‌عنوان اسپم شناسایی شد."
    elif settings_dict.get("antispam", True) and norm and dup_count >= dup_limit:
        reason = "پیام تکراری/متن مشابه به‌عنوان اسپم شناسایی شد."
    elif settings_dict.get("antispam", True) and len(links) > max_links:
        reason = "تعداد لینک‌های پیام بیش از حد مجاز است."

    if not reason:
        return

    if await safe_delete(msg):
        await db.incr_stat(chat.id, "deletes")
    count = await apply_violation(context, chat.id, user.id, reason, settings_dict)
    await db.log(chat.id, user.id, "auto_moderation", user.id, reason=reason, warning_count=count)
    try:
        await context.bot.send_message(chat.id, f"⚠️ پیام کاربر <code>{user.id}</code> حذف شد. دلیل: {reason}", parse_mode="HTML")
    except Exception:
        pass
