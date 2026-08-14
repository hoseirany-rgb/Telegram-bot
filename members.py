from __future__ import annotations

import random
import time

from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from ..db import db
from ..utils import captcha_keyboard

CHALLENGES: dict[tuple[int, int], dict[str, int | float]] = {}


def _mute_perms() -> ChatPermissions:
    return ChatPermissions(can_send_messages=False)


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat or not msg.new_chat_members:
        return
    settings_dict = await db.get_group_settings(chat.id)
    for member in msg.new_chat_members:
        if member.is_bot:
            continue
        await db.incr_stat(chat.id, "joins")
        if settings_dict.get("captcha", False):
            a = random.randint(1, 9)
            b = random.randint(1, 9)
            answer = a + b
            choices = list({answer, answer + 1, max(1, answer - 1), random.randint(2, 18)})
            random.shuffle(choices)
            CHALLENGES[(chat.id, member.id)] = {"answer": answer, "expires": time.time() + 180, "tries": 0}
            await context.bot.restrict_chat_member(chat.id, member.id, permissions=_mute_perms())
            await chat.send_message(
                f"🛡 {member.mention_html()} خوش آمدی. برای فعال شدن چت، جواب را انتخاب کن:\n<b>{a} + {b} = ?</b>",
                reply_markup=captcha_keyboard(chat.id, member.id, choices),
                parse_mode="HTML",
            )
        elif settings_dict.get("welcome", True):
            await chat.send_message(f"👋 {member.mention_html()} خوش آمدی.", parse_mode="HTML")


def check_captcha(chat_id: int, user_id: int, answer: int) -> tuple[bool, str]:
    item = CHALLENGES.get((chat_id, user_id))
    if not item:
        return False, "چالش پیدا نشد یا منقضی شده است."
    if time.time() > float(item["expires"]):
        CHALLENGES.pop((chat_id, user_id), None)
        return False, "زمان کپچا تمام شد."
    item["tries"] = int(item["tries"]) + 1
    if answer == int(item["answer"]):
        CHALLENGES.pop((chat_id, user_id), None)
        return True, "تأیید شد ✅"
    if int(item["tries"]) >= 3:
        CHALLENGES.pop((chat_id, user_id), None)
        return False, "تلاش‌ها تمام شد."
    return False, "پاسخ اشتباه است."
