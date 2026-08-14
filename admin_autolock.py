"""Section 7: Automatic locking (mode, time, days, auto-open, holiday, events)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN


def cd(t, **kw):
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


@require(ADMIN)
async def cmd_autolock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = await xdb.get_group_settings(update.effective_chat.id)
    if not args:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = [
            [InlineKeyboardButton(
                f"{'✅' if s.get('autolock_enabled') else '❌'} قفل خودکار",
                callback_data=cd("al", c=update.effective_chat.id, k="autolock_enabled"))],
            [InlineKeyboardButton(
                f"حالت: {s.get('autolock_mode')}",
                callback_data=cd("al", c=update.effective_chat.id, k="autolock_mode"))],
            [InlineKeyboardButton(
                f"⏰ ساعت قفل: {s.get('autolock_time')}",
                callback_data=cd("al", c=update.effective_chat.id, k="autolock_time"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('autolock_open_auto') else '❌'} باز شدن خودکار",
                callback_data=cd("al", c=update.effective_chat.id, k="autolock_open_auto"))],
            [InlineKeyboardButton(
                f"روزها: {s.get('autolock_days')}",
                callback_data=cd("al", c=update.effective_chat.id, k="autolock_days"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('autolock_holiday') else '❌'} تعطیلی",
                callback_data=cd("al", c=update.effective_chat.id, k="autolock_holiday"))],
            [InlineKeyboardButton(
                f"مناسبت‌ها: {s.get('autolock_events') or '-'}",
                callback_data=cd("al", c=update.effective_chat.id, k="autolock_events"))],
        ]
        await update.effective_message.reply_text(
            f"وضعیت فعلی: {'قفل' if s.get('autolock_status') else 'باز'}",
            reply_markup=InlineKeyboardMarkup(rows))
        return
    op = args[0]
    if op == "on":
        await xdb.update_group_settings(update.effective_chat.id, autolock_enabled=True)
    elif op == "off":
        await xdb.update_group_settings(update.effective_chat.id, autolock_enabled=False)
    elif op == "mode":
        await xdb.update_group_settings(update.effective_chat.id, autolock_mode=args[1] if len(args) > 1 else "soft")
    elif op == "time":
        await xdb.update_group_settings(update.effective_chat.id, autolock_time=args[1] if len(args) > 1 else "22:00-06:00")
    elif op == "open":
        await xdb.update_group_settings(update.effective_chat.id, autolock_open_auto=not s.get("autolock_open_auto", True))
    elif op == "days":
        await xdb.update_group_settings(update.effective_chat.id, autolock_days=args[1] if len(args) > 1 else "0,1,2,3,4,5,6")
    elif op == "holiday":
        await xdb.update_group_settings(update.effective_chat.id, autolock_holiday=True)
    elif op == "event":
        await xdb.update_group_settings(update.effective_chat.id, autolock_events=" ".join(args[1:]) if len(args) > 1 else "")
    elif op == "close":
        await xdb.update_group_settings(update.effective_chat.id, autolock_status=False)
    elif op == "lock":
        await xdb.update_group_settings(update.effective_chat.id, autolock_status=True)
    else:
        await update.effective_message.reply_text("پارامتر نامعتبر.")
    await update.effective_message.reply_text("OK")


async def on_callback(update, context):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("al|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    k = out.get("k"); cid = int(out.get("c"))
    s = await xdb.get_group_settings(cid)
    if k in {"autolock_enabled", "autolock_open_auto", "autolock_holiday"}:
        await xdb.update_group_settings(cid, **{k: not s.get(k, False)})
    elif k == "autolock_mode":
        await xdb.update_group_settings(cid, autolock_mode="hard" if s.get("autolock_mode") == "soft" else "soft")
    elif k == "autolock_time":
        await xdb.update_group_settings(cid, autolock_time="00:00-23:59" if s.get("autolock_time") != "00:00-23:59" else "22:00-06:00")
    elif k == "autolock_days":
        await xdb.update_group_settings(cid, autolock_days="5,6" if s.get("autolock_days") != "5,6" else "0,1,2,3,4,5,6")
    elif k == "autolock_events":
        await xdb.update_group_settings(cid, autolock_events="nowruz, yalda")
    await q.answer("OK")


def register(app: Application):
    app.add_handler(CommandHandler("autolock", cmd_autolock))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^al\|"))
