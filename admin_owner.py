"""Section 15: Owner panel (bot-wide management, license, subscription, users,
groups, plugins, updates, monitoring)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import OWNER
from ...config import settings


def cd(t, **kw):
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


@require(OWNER)
async def cmd_owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or ["panel"]
    op = args[0]
    if op == "panel":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = [
            [InlineKeyboardButton("📊 مانیتورینگ", callback_data=cd("own", k="monitor"))],
            [InlineKeyboardButton("📜 لایسنس", callback_data=cd("own", k="license"))],
            [InlineKeyboardButton("💳 اشتراک", callback_data=cd("own", k="subs"))],
            [InlineKeyboardButton("👥 کاربران", callback_data=cd("own", k="users"))],
            [InlineKeyboardButton("👪 گروه‌ها", callback_data=cd("own", k="groups"))],
            [InlineKeyboardButton("🔌 پلاگین‌ها", callback_data=cd("own", k="plugins"))],
            [InlineKeyboardButton("🔄 بروزرسانی", callback_data=cd("own", k="update"))],
        ]
        await update.effective_message.reply_text("پنل مالک ربات:", reply_markup=InlineKeyboardMarkup(rows))
    elif op == "license":
        await xdb.global_set("license", {
            "issued_to": update.effective_user.id,
            "issued_at": "now",
            "type": "enterprise",
        })
        await update.effective_message.reply_text("لایسنس enterprise ثبت شد.")
    elif op == "monitor":
        groups = await xdb.global_get("group_count", 0)
        await update.effective_message.reply_text(
            f"مانیتورینگ: تعداد گروه‌ها ≈ {groups}\n"
            f"Owner IDs: {len(settings.owner_ids)}")
    elif op == "plugins":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = [[InlineKeyboardButton("🔌 antispam", callback_data=cd("own", k="plugin", v="antispam"))],
                [InlineKeyboardButton("🔌 ai", callback_data=cd("own", k="plugin", v="ai"))]]
        await update.effective_message.reply_text("پلاگین‌ها:", reply_markup=InlineKeyboardMarkup(rows))
    elif op == "update":
        await update.effective_message.reply_text("بروزرسانی: نسخه فعلی enterprise-1.0 (defensive).")
    elif op == "users":
        await update.effective_message.reply_text("آمار کاربران ربات: (نیاز به جدول users؛ در نسخه بعدی افزوده می‌شود)")
    elif op == "groups":
        await update.effective_message.reply_text("آمار گروه‌ها (نیاز به شمارنده).")
    elif op == "subs":
        await update.effective_message.reply_text("اشتراک‌ها: enterprise (دائمی).")
    else:
        await update.effective_message.reply_text("پارامتر نامعتبر.")


async def on_callback(update, context):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("own|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    k = out.get("k")
    await q.answer(f"{k} انتخاب شد.")


from ...config import settings  # noqa: F401  (kept for legacy callers)


def register(app: Application):
    app.add_handler(CommandHandler("owner", cmd_owner))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^own\|"))
