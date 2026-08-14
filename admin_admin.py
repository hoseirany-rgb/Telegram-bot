"""Inline admin action panel on a user (warn/mute/kick/ban/unmute/unban/close)."""
from __future__ import annotations

from html import escape

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require, is_protected_target
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN


def cd(t: str, **kw) -> str:
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


def panel(chat_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚠️ Warn", callback_data=cd("adm", c=chat_id, u=user_id, a="warn")),
         InlineKeyboardButton("🔇 Mute", callback_data=cd("adm", c=chat_id, u=user_id, a="mute"))],
        [InlineKeyboardButton("👢 Kick", callback_data=cd("adm", c=chat_id, u=user_id, a="kick")),
         InlineKeyboardButton("🚫 Ban", callback_data=cd("adm", c=chat_id, u=user_id, a="ban"))],
        [InlineKeyboardButton("🔊 Unmute", callback_data=cd("adm", c=chat_id, u=user_id, a="unmute")),
         InlineKeyboardButton("✅ Unban", callback_data=cd("adm", c=chat_id, u=user_id, a="unban"))],
        [InlineKeyboardButton("♻️ Reset warns", callback_data=cd("adm", c=chat_id, u=user_id, a="rst"))],
        [InlineKeyboardButton("✖️ Close", callback_data=cd("adm", c=chat_id, a="close"))],
    ])


@require(ADMIN)
async def cmd_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    target = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
    elif context.args and context.args[0].isdigit():
        from telegram import User
        target = User(id=int(context.args[0]), first_name=context.args[0], is_bot=False)
    if not target:
        await msg.reply_text("روی پیام ریپلای کنید یا آیدی بدهید.")
        return
    await msg.reply_text(
        f"👤 <a href=\"tg://user?id={target.id}\">{escape(target.first_name or str(target.id))}</a>\nID: <code>{target.id}</code>",
        parse_mode="HTML",
        reply_markup=panel(update.effective_chat.id, target.id),
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("adm|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    chat_id = int(out.get("c", 0) or 0)
    user_id = int(out.get("u", 0) or 0)
    a = out.get("a", "")
    if a == "close":
        await q.delete_message(); return
    if await is_protected_target(context, chat_id, user_id):
        await q.answer("روی owner/admin اعمال نمی‌شود.", show_alert=True); return
    if a == "warn":
        await xdb.global_inc_warn(chat_id, user_id, "از دکمه ادمین")
    elif a == "mute":
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
    elif a == "unmute":
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(
            can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True,
            can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True,
            can_add_web_page_previews=True))
    elif a == "kick":
        await context.bot.ban_chat_member(chat_id, user_id); await context.bot.unban_chat_member(chat_id, user_id)
    elif a == "ban":
        await context.bot.ban_chat_member(chat_id, user_id, revoke_messages=True)
    elif a == "unban":
        await context.bot.unban_chat_member(chat_id, user_id, only_if_banned=True)
    elif a == "rst":
        await xdb.set_warning_reset(chat_id, user_id)
    await xdb.log(chat_id, q.from_user.id, f"cb:{a}", user_id)
    await q.answer("OK")


def register(app: Application):
    app.add_handler(CommandHandler("userinfo", cmd_userinfo))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^adm\|"))
