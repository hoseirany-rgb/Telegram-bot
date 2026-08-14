"""Section 4: Anti-Spam core (delete/sensitivity/flood/similar text + actions)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import DEFAULT_BURST_LIMIT, DEFAULT_BURST_WINDOW, DEFAULT_DUP_LIMIT, DEFAULT_DUP_WINDOW
from ...roles import ADMIN


@require(ADMIN)
async def cmd_antispam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        s = await xdb.get_group_settings(update.effective_chat.id)
        await update.effective_message.reply_text(
            "🤖 ضد اسپم\n"
            f"حذف اسپم: {'✅' if s.get('antispam_delete') else '❌'}\n"
            f"حساسیت: {s.get('antispam_sensitivity')}\n"
            f"Flood: حذف {'✅' if s.get('antispam_flood_delete') else '❌'} / پنجره {s.get('antispam_flood_window')}s / حساسیت {s.get('antispam_flood_sensitivity')}\n"
            f"تشخیص تکراری: {'✅' if s.get('antispam_duplicate') else '❌'} | مشابه: {'✅' if s.get('antispam_similar') else '❌'}\n"
            f"حذف خودکار: {'✅' if s.get('antispam_auto_del') else '❌'}"
        )
        return
    op = args[0]
    s = await xdb.get_group_settings(update.effective_chat.id)
    if op in {"delete", "dup", "sim", "autodel"}:
        new = not s.get(f"antispam_{op}" if op != "delete" else "antispam_delete", False)
        key = "antispam_delete" if op == "delete" else f"antispam_{op}"
        await xdb.update_group_settings(update.effective_chat.id, **{key: new})
        await update.effective_message.reply_text(f"{key} → {'ON' if new else 'OFF'}")
    elif op == "sens":
        if len(args) > 1 and args[1].isdigit():
            v = max(1, min(5, int(args[1])))
            await xdb.update_group_settings(update.effective_chat.id, antispam_sensitivity=v)
            await update.effective_message.reply_text(f"حساسیت: {v}")
    elif op == "flood":
        await xdb.update_group_settings(
            update.effective_chat.id,
            antispam_flood_delete=not s.get("antispam_flood_delete", True),
        )
        await update.effective_message.reply_text("Flood حذف → toggled")
    elif op == "flood_window" and len(args) > 1 and args[1].isdigit():
        v = max(2, int(args[1]))
        await xdb.update_group_settings(update.effective_chat.id, antispam_flood_window=v)
        await update.effective_message.reply_text(f"پنجره: {v}s")
    elif op == "flood_sens" and len(args) > 1 and args[1].isdigit():
        v = max(1, min(5, int(args[1])))
        await xdb.update_group_settings(update.effective_chat.id, antispam_flood_sensitivity=v)
    elif op == "action":
        if len(args) > 1 and args[1] in {"warn", "mute", "ban", "tempban", "kick"}:
            await xdb.update_group_settings(update.effective_chat.id, antispam_action=args[1])
            await update.effective_message.reply_text("اقدام: " + args[1])
    elif op in {"on", "off"}:
        v = op == "on"
        await xdb.update_group_settings(update.effective_chat.id, antispam_delete=v)
        await update.effective_message.reply_text(f"antispam_delete → {'ON' if v else 'OFF'}")
    else:
        await update.effective_message.reply_text("پارامتر نامعتبر.")


def register(app: Application):
    app.add_handler(CommandHandler("antispam", cmd_antispam))
