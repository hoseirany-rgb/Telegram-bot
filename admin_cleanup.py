"""Section 6: Cleanup (seconds, hourly, daily, weekly, monthly + media types)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN

FLAGS = [
    ("cleanup_seconds", "پاکسازی ثانیه‌ای"),
    ("cleanup_hourly", "پاکسازی ساعتی"),
    ("cleanup_daily", "پاکسازی روزانه"),
    ("cleanup_weekly", "پاکسازی هفتگی"),
    ("cleanup_monthly", "پاکسازی ماهانه"),
    ("cleanup_remaining_announce", "اعلام باقی"),
    ("cleanup_files", "فایل‌ها"),
    ("cleanup_gifs", "گیف"),
    ("cleanup_photos", "عکس"),
    ("cleanup_videos", "ویدیو"),
    ("cleanup_voice", "Voice"),
    ("cleanup_stickers", "Sticker"),
]


def cd(t, **kw):
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


@require(ADMIN)
async def cmd_cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = None
    if args:
        s = await xdb.get_group_settings(update.effective_chat.id)
    if not args:
        s = await xdb.get_group_settings(update.effective_chat.id)
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = []
        for k, lbl in FLAGS:
            rows.append([InlineKeyboardButton(
                f"{'✅' if s.get(k) else '❌'} {lbl}",
                callback_data=cd("cl", c=update.effective_chat.id, k=k))])
        rows.append([InlineKeyboardButton(
            f"⏰ ساعت پاکسازی: {s.get('cleanup_at', '00:00')}",
            callback_data=cd("cl", c=update.effective_chat.id, k="cleanup_at"))])
        await update.effective_message.reply_text("🧹 پاکسازی:", reply_markup=InlineKeyboardMarkup(rows))
        return
    op = args[0]
    if op in {k for k, _ in FLAGS}:
        new = not s.get(op, False)
        await xdb.update_group_settings(update.effective_chat.id, **{op: new})
        await update.effective_message.reply_text(f"{op} → {'ON' if new else 'OFF'}")
    elif op == "at" and len(args) > 1:
        await xdb.update_group_settings(update.effective_chat.id, cleanup_at=args[1])
        await update.effective_message.reply_text(f"زبان‌بندی ساعت: {args[1]}")
    elif op == "schedule":
        # schedule HH:MM
        await xdb.update_group_settings(update.effective_chat.id, cleanup_at=args[1] if len(args) > 1 else "00:00")
        await xdb.update_group_settings(update.effective_chat.id, cleanup_daily=True)
    elif op == "announce" and len(args) > 1 and args[1].isdigit():
        await xdb.update_group_settings(update.effective_chat.id, cleanup_remaining_announce=int(args[1]))
    else:
        await update.effective_message.reply_text("پارامتر نامعتبر.")


async def on_callback(update, context):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("cl|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    k = out.get("k"); cid = int(out.get("c"))
    if k not in {kk for kk, _ in FLAGS}:
        await q.answer(); return
    s = await xdb.get_group_settings(cid)
    new = not s.get(k, False)
    await xdb.update_group_settings(cid, **{k: new})
    s = await xdb.get_group_settings(cid)
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    rows = []
    for kk, lbl in FLAGS:
        rows.append([InlineKeyboardButton(
            f"{'✅' if s.get(kk) else '❌'} {lbl}",
            callback_data=cd("cl", c=cid, k=kk))])
    await q.edit_message_reply_markup(InlineKeyboardMarkup(rows))
    await q.answer(f"{k}: {'ON' if new else 'OFF'}")


def register(app: Application):
    app.add_handler(CommandHandler("cleanup", cmd_cleanup))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^cl\|"))
