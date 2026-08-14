from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ..constants import CALLBACK_DATA_MAX


def cd(action: str, **kv: str | int) -> str:
    suffix = "|".join(f"{k}={v}" for k, v in kv.items())
    raw = action if not suffix else f"{action}|{suffix}"
    return raw[:CALLBACK_DATA_MAX]


def admin_panel(chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("⚠️ اخطار", callback_data=cd("warn", c=chat_id, u=user_id)), InlineKeyboardButton("🔇 میوت", callback_data=cd("mute", c=chat_id, u=user_id))],
        [InlineKeyboardButton("👢 کیک", callback_data=cd("kick", c=chat_id, u=user_id)), InlineKeyboardButton("🚫 بن", callback_data=cd("ban", c=chat_id, u=user_id))],
        [InlineKeyboardButton("🔊 آن‌میوت", callback_data=cd("unmute", c=chat_id, u=user_id)), InlineKeyboardButton("♻️ ریست اخطار", callback_data=cd("rst", c=chat_id, u=user_id))],
        [InlineKeyboardButton("✖️ بستن", callback_data=cd("close", c=chat_id))],
    ]
    return InlineKeyboardMarkup(rows)


def settings_keyboard(chat_id: int, settings_dict: dict) -> InlineKeyboardMarkup:
    def flag(name: str) -> str:
        return "✅" if settings_dict.get(name, False) else "❌"

    rows = [
        [InlineKeyboardButton(f"{flag('antispam')} Anti-spam", callback_data=cd("set", c=chat_id, k="antispam")), InlineKeyboardButton(f"{flag('antilink')} Anti-link", callback_data=cd("set", c=chat_id, k="antilink"))],
        [InlineKeyboardButton(f"{flag('anti_forward')} Anti-forward", callback_data=cd("set", c=chat_id, k="anti_forward")), InlineKeyboardButton(f"{flag('captcha')} Captcha", callback_data=cd("set", c=chat_id, k="captcha"))],
        [InlineKeyboardButton(f"{flag('welcome')} Welcome", callback_data=cd("set", c=chat_id, k="welcome")), InlineKeyboardButton("✖️ بستن", callback_data=cd("close", c=chat_id))],
    ]
    return InlineKeyboardMarkup(rows)


def captcha_keyboard(chat_id: int, user_id: int, choices: list[int]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(str(x), callback_data=cd("cp", c=chat_id, u=user_id, a=x)) for x in choices]
    return InlineKeyboardMarkup([row])
