from __future__ import annotations

ALLOWED_UPDATES: list[str] = [
    "message",
    "edited_message",
    "callback_query",
    "my_chat_member",
    "chat_member",
]

CALLBACK_DATA_MAX = 64
DEFAULT_WARN_LIMIT = 3
DEFAULT_MUTE_SECONDS = 30 * 60
DEFAULT_BURST_WINDOW = 8
DEFAULT_BURST_LIMIT = 7
DEFAULT_DUP_WINDOW = 90
DEFAULT_DUP_LIMIT = 3
DEFAULT_MAX_LINKS = 1

EMOJI = {
    "shield": "🛡",
    "warn": "⚠️",
    "mute": "🔇",
    "unmute": "🔊",
    "ban": "🚫",
    "kick": "👢",
    "ok": "✅",
    "close": "✖️",
}

PROTECTED_STATUSES = {"creator", "administrator"}
URL_ENTITY_TYPES = {"url", "text_link"}
