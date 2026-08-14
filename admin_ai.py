"""Section 10: AI features (message/link/user/behavior/risk analysis, ad/scam
detection, summary, suggested action)."""
from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN

PROVIDERS = {"stub": "هوش داخلی (Stub)", "openai": "OpenAI", "gemini": "Gemini"}


def cd(t, **kw):
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


@require(ADMIN)
async def cmd_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = await xdb.get_group_settings(update.effective_chat.id)
    if not args:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = [
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_enabled') else '❌'} فعال",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_enabled"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_msg_scan') else '❌'} تحلیل پیام",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_msg_scan"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_link_scan') else '❌'} تحلیل لینک",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_link_scan"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_user_scan') else '❌'} تحلیل کاربر",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_user_scan"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_behavior_scan') else '❌'} تحلیل رفتار",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_behavior_scan"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_risk_scan') else '❌'} تحلیل ریسک",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_risk_scan"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_ad_detect') else '❌'} تشخیص تبلیغ",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_ad_detect"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_scam_detect') else '❌'} تشخیص کلاهبرداری",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_scam_detect"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_summary') else '❌'} خلاصه گفتگو",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_summary"))],
            [InlineKeyboardButton(
                f"{'✅' if s.get('ai_suggest') else '❌'} پیشنهاد اقدام",
                callback_data=cd("ai", c=update.effective_chat.id, k="ai_suggest"))],
        ]
        await update.effective_message.reply_text("🧠 تنظیمات AI:", reply_markup=InlineKeyboardMarkup(rows))
        return
    op = args[0]
    if op in {"msg", "link", "user", "behavior", "risk", "ad", "scam", "summary", "suggest"}:
        mapk = {"msg": "ai_msg_scan", "link": "ai_link_scan", "user": "ai_user_scan",
                "behavior": "ai_behavior_scan", "risk": "ai_risk_scan", "ad": "ai_ad_detect",
                "scam": "ai_scam_detect", "summary": "ai_summary", "suggest": "ai_suggest"}
        new = not s.get(mapk[op], False)
        await xdb.update_group_settings(update.effective_chat.id, **{mapk[op]: new})
    elif op in {"on", "off"}:
        await xdb.update_group_settings(update.effective_chat.id, ai_enabled=(op == "on"))
    elif op == "provider" and len(args) > 1:
        await xdb.global_set("ai_provider", args[1])
    else:
        await update.effective_message.reply_text("پارامتر نامعتبر.")
    await update.effective_message.reply_text("OK")


@require(ADMIN)
async def cmd_aiscan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message.reply_to_message if update.effective_message else None
    if not target:
        await update.effective_message.reply_text("روی پیام ریپلای کنید.")
        return
    text = target.text or target.caption or ""
    await update.effective_message.reply_text(
        f"🔬 AI Scan Result (stub)\n"
        f"• length={len(text)}\n"
        f"• tokens={len(text.split())}\n"
        f"• risk=low | الف) تبلیغ: خیر | ب) کلاهبرداری: خیر"
    )


@require(ADMIN)
async def cmd_aisummary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sample = "خلاصه: گفتگوی اخیر فعال بوده، ۳ پیام حاوی لینک، ۱ اخطار صادر شد."
    await update.effective_message.reply_text(f"📝 AI Summary (stub)\n{sample}")


@require(ADMIN)
async def cmd_aisuggest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text("💡 پیشنهاد اقدام: کاربر پرخطر → Mute ۳۰ دقیقه + کاهش Reputation")


async def on_callback(update, context):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("ai|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    k = out.get("k"); cid = int(out.get("c"))
    s = await xdb.get_group_settings(cid)
    if k == "ai_enabled":
        await xdb.update_group_settings(cid, ai_enabled=not s.get("ai_enabled", False))
    elif k.startswith("ai_"):
        await xdb.update_group_settings(cid, **{k: not s.get(k, False)})
    await q.answer("OK")


def register(app: Application):
    app.add_handler(CommandHandler("ai", cmd_ai))
    app.add_handler(CommandHandler("aiscan", cmd_aiscan))
    app.add_handler(CommandHandler("aisummary", cmd_aisummary))
    app.add_handler(CommandHandler("aisuggest", cmd_aisuggest))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^ai\|"))
