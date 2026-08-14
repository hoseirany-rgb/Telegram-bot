"""Section 11: Members (welcome, captcha, raid-lock, lang)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...roles import ADMIN


@require(ADMIN)
async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = await xdb.get_group_settings(update.effective_chat.id)
    if not args:
        await update.effective_message.reply_text(f"خوش‌آمد: {'✅' if s.get('welcome') else '❌'}")
        return
    arg = args[0].lower()
    if arg in {"on", "off", "1", "0"}:
        await xdb.update_group_settings(update.effective_chat.id, welcome=arg in {"on", "1"})
        await update.effective_message.reply_text("OK")


@require(ADMIN)
async def cmd_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = await xdb.get_group_settings(update.effective_chat.id)
    if not args:
        await update.effective_message.reply_text(f"کپچا: {'✅' if s.get('captcha') else '❌'}")
        return
    arg = args[0].lower()
    if arg in {"on", "off"}:
        await xdb.update_group_settings(update.effective_chat.id, captcha=arg == "on")


@require(ADMIN)
async def cmd_raidlock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = await xdb.get_group_settings(update.effective_chat.id)
    if not args:
        await update.effective_message.reply_text(f"Raid Lock: {'ON' if s.get('sec_anti_raid') else 'OFF'}")
        return
    if args[0] in {"on", "off"}:
        await xdb.update_group_settings(update.effective_chat.id, sec_anti_raid=(args[0] == "on"))


@require(ADMIN)
async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("استفاده: /lang fa|en")
        return
    await xdb.update_group_settings(update.effective_chat.id, lang=context.args[0].lower())
    await update.effective_message.reply_text("lang: " + context.args[0])


def register(app: Application):
    app.add_handler(CommandHandler("welcome", cmd_welcome))
    app.add_handler(CommandHandler("captcha", cmd_captcha))
    app.add_handler(CommandHandler("raidlock", cmd_raidlock))
    app.add_handler(CommandHandler("lang", cmd_lang))
