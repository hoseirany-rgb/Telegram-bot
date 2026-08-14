"""Section 14: Public reporting by members."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...roles import PUBLIC


@require(PUBLIC)
async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if not msg.reply_to_message or not msg.reply_to_message.from_user:
        await msg.reply_text("روی پیام موردنظر ریپلای کنید و /report بزنید.")
        return
    target = msg.reply_to_message.from_user
    await xdb.incr_stat(update.effective_chat.id, "reports")
    await xdb.log(update.effective_chat.id, update.effective_user.id, "report", target.id,
                  text=(msg.reply_to_message.text or msg.reply_to_message.caption or "")[:200])
    await msg.reply_text(
        f"🚨 گزارش ثبت شد برای <a href=\"tg://user?id={target.id}\">{target.first_name or target.id}</a>",
        parse_mode="HTML")


def register(app: Application):
    app.add_handler(CommandHandler("report", cmd_report))
