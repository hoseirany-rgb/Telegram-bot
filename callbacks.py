"""Unified callback dispatcher for BotGuardian Enterprise (merged build).

Supports every callback prefix produced by the merged bot:
- Enterprise defaults: ``set|``, ``cp|``, ``close``, ``warn|mute|...``
- Sections pack: ``adm|``, ``grp|``, ``lck|``, ``adp|``, ``sec|``,
  ``ai|``, ``al|``, ``cl|``, ``fs|``, ``own|``

Section callbacks are routed to the matching module's ``on_callback``
through `handlers.router.dispatch_callback`.
"""
from __future__ import annotations

import logging
from telegram import ChatPermissions, Update
from telegram.ext import ContextTypes

from ..db import db
from ..utils import (
    admin_panel,
    ban_user,
    is_protected_target,
    kick_user,
    mute_user,
    settings_keyboard,
    unban_user,
    unmute_user,
)
from .members import check_captcha

logger = logging.getLogger("botguardian.callbacks")


# ---- helpers used by both enterprise & section callbacks ---------------

def parse_cb(data: str) -> dict[str, str]:
    parts = data.split("|")
    out = {"action": parts[0]}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


async def _is_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
    except Exception:
        return False
    return getattr(member, "status", "") in {"creator", "administrator"}


_UNLOCK_ALL = ChatPermissions(
    can_send_messages=True, can_send_audios=True, can_send_documents=True,
    can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
    can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
    can_add_web_page_previews=True, can_invite_users=True, can_change_info=False,
    can_pin_messages=False, can_manage_topics=False,
)


# ---- top-level dispatcher ------------------------------------------------

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return

    # 1) Captcha
    if query.data.startswith("cp|"):
        await _on_captcha(update, context)
        return

    parsed = parse_cb(query.data)
    action = parsed.get("action", "")
    chat_id = int(parsed.get("c", "0") or 0)
    user_id = int(parsed.get("u", "0") or 0)

    # 2) Settings panel toggle (enterprise keyboard)
    if action == "set":
        if not await _is_admin(context, chat_id, query.from_user.id):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return
        key = parsed.get("k", "")
        cur = await db.get_group_settings(chat_id)
        new_val = not bool(cur.get(key, False))
        s = await db.update_group_settings(chat_id, **{key: new_val})
        try:
            await query.edit_message_reply_markup(reply_markup=settings_keyboard(chat_id, s))
        except Exception as exc:
            logger.debug("edit_markup failed: %s", exc)
        await query.answer(f"{key}: {'ON' if new_val else 'OFF'}")
        return

    # 3) Enterprise close button
    if action == "close":
        try:
            await query.delete_message()
        except Exception:
            pass
        await query.answer("بسته شد")
        return

    # 4) Enterprise user-action panel (warn/mute/unmute/kick/ban/unban/rst)
    if action in {"warn", "mute", "unmute", "kick", "ban", "unban", "rst"} and query.data.count("|") >= 2:
        if not chat_id:
            await query.answer("داده نامعتبر است.", show_alert=True)
            return
        if not await _is_admin(context, chat_id, query.from_user.id):
            await query.answer("دسترسی ندارید.", show_alert=True)
            return
        if not user_id:
            await query.answer("کاربر هدف مشخص نیست.", show_alert=True)
            return
        if await is_protected_target(context, chat_id, user_id):
            await query.answer("روی owner/admin اعمال نمی‌شود.", show_alert=True)
            return

        if action == "warn":
            count = await db.add_warning(chat_id, user_id, "اخطار توسط دکمه ادمین")
            await db.incr_stat(chat_id, "warnings")
            await query.answer(f"اخطار ثبت شد ({count})")
        elif action == "mute":
            await mute_user(context, chat_id, user_id)
            await db.incr_stat(chat_id, "mutes")
            await query.answer("کاربر میوت شد")
        elif action == "unmute":
            await unmute_user(context, chat_id, user_id)
            await query.answer("کاربر آن‌میوت شد")
        elif action == "kick":
            await kick_user(context, chat_id, user_id)
            await db.incr_stat(chat_id, "kicks")
            await query.answer("کاربر کیک شد")
        elif action == "ban":
            await ban_user(context, chat_id, user_id)
            await db.incr_stat(chat_id, "bans")
            await query.answer("کاربر بن شد")
        elif action == "unban":
            await unban_user(context, chat_id, user_id)
            await query.answer("کاربر آن‌بن شد")
        elif action == "rst":
            await db.reset_warnings(chat_id, user_id)
            await query.answer("اخطارها پاک شدند")
        await db.log(chat_id, query.from_user.id, f"cb:{action}", user_id)
        return

    # 5) Hand off to section callbacks (adm|grp|lck|adp|sec|ai|al|cl|fs|own|)
    from .router import dispatch_callback
    handled = await dispatch_callback(update, context)
    if not handled:
        # Final fallback: just call bot.answer so the user sees feedback
        await query.answer("OK")


async def _on_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return
    parsed = parse_cb(query.data)
    chat_id = int(parsed.get("c", "0") or 0)
    user_id = int(parsed.get("u", "0") or 0)
    answer = int(parsed.get("a", "-1") or -1)
    if query.from_user.id != user_id:
        await query.answer("این کپچا برای شما نیست.", show_alert=True)
        return
    ok, text = check_captcha(chat_id, user_id, answer)
    if ok:
        try:
            await context.bot.restrict_chat_member(chat_id, user_id, permissions=_UNLOCK_ALL)
        except Exception as exc:
            logger.debug("unlock after captcha failed: %s", exc)
        try:
            await query.edit_message_text("✅ کاربر تأیید شد.")
        except Exception:
            pass
        await query.answer(text)
    else:
        await query.answer(text, show_alert=True)


# Re-export admin_panel for command handlers / sections that need it.
__all__ = ["on_callback", "parse_cb", "admin_panel"]
