from __future__ import annotations

import logging
import re
import time

from telegram import ChatPermissions, Message, MessageEntity
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"(?P<url>(?:https?://|t\.me/|telegram\.me/)[^\s,;]+|www\.[^\s,;]+)", re.IGNORECASE)


def extract_links(message: Message) -> list[str]:
    found: list[str] = []
    text = message.text or message.caption or ""
    for ent in (*((message.entities) or ()), *((message.caption_entities) or ())):
        if ent.type == MessageEntity.TEXT_LINK and ent.url:
            found.append(ent.url)
        elif ent.type == MessageEntity.URL:
            chunk = text[ent.offset: ent.offset + ent.length]
            if chunk:
                found.append(chunk)
    if not found and text:
        for m in URL_RE.finditer(text):
            found.append(m.group("url").rstrip(".,)!?;:"))
    return list(dict.fromkeys(found))


async def safe_delete(message: Message) -> bool:
    try:
        await message.delete()
        return True
    except (BadRequest, TelegramError) as exc:
        logger.debug("delete failed: %s", exc)
        return False


def _mute_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
        can_change_info=False,
        can_invite_users=False,
        can_pin_messages=False,
        can_manage_topics=False,
    )


def _unmute_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False,
        can_manage_topics=False,
    )


async def mute_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, duration: int = 1800) -> bool:
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=_mute_permissions(),
            until_date=int(time.time()) + duration,
        )
        return True
    except (BadRequest, TelegramError) as exc:
        logger.warning("mute failed for %s in %s: %s", user_id, chat_id, exc)
        return False


async def unmute_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        await context.bot.restrict_chat_member(chat_id=chat_id, user_id=user_id, permissions=_unmute_permissions())
        return True
    except (BadRequest, TelegramError) as exc:
        logger.warning("unmute failed for %s in %s: %s", user_id, chat_id, exc)
        return False


async def ban_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int, revoke_messages: bool = True) -> bool:
    try:
        await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id, revoke_messages=revoke_messages)
        return True
    except (BadRequest, TelegramError) as exc:
        logger.warning("ban failed for %s in %s: %s", user_id, chat_id, exc)
        return False


async def unban_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        await context.bot.unban_chat_member(chat_id=chat_id, user_id=user_id, only_if_banned=True)
        return True
    except (BadRequest, TelegramError) as exc:
        logger.warning("unban failed for %s in %s: %s", user_id, chat_id, exc)
        return False


async def kick_user(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    ok = await ban_user(context, chat_id, user_id, revoke_messages=True)
    if not ok:
        return False
    return await unban_user(context, chat_id, user_id)
