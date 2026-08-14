"""Section 5: Mandatory Join / Force-Subscribe (channels + groups + ad mode)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN

EXTRA_KEYS = ["forcesub_channels", "forcesub_groups"]


def cd(t, **kw):
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


@require(ADMIN)
async def cmd_forcesub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await xdb.get_group_settings(update.effective_chat.id)
    args = context.args or []
    if not args:
        fs_chans = ", ".join(s.get("forcesub_channels", [])) or "-"
        fs_grps = ", ".join(s.get("forcesub_groups", [])) or "-"
        await update.effective_message.reply_text(
            "📡 عضویت اجباری\n"
            f"وضعیت: {'✅ روشن' if s.get('forcesub_enabled') else '❌ خاموش'}\n"
            f"کانال‌ها: {fs_chans}\nگروه‌ها: {fs_grps}\n"
            f"پیام‌های مجاز قبل از عضویت: {s.get('forcesub_msg_allowed')}\n"
            f"زمان پاکسازی پیام‌های غیرعضو: {s.get('forcesub_purge_secs')}s\n"
            f"اد اجباری: {'✅' if s.get('forcesub_ad_required') else '❌'} (تعداد: {s.get('forcesub_ad_count')}, حالت: {s.get('forcesub_ad_mode')})"
        )
        return
    op = args[0]
    if op == "on" or op == "off":
        await xdb.update_group_settings(update.effective_chat.id, forcesub_enabled=(op == "on"))
        await update.effective_message.reply_text("forcesub → " + op)
    elif op == "add" and len(args) > 1:
        what = "forcesub_channels" if args[1].startswith("@") or args[1].startswith("-") else "forcesub_groups"
        lst = list(s.get(what, []))
        if args[1] not in lst:
            lst.append(args[1])
        await xdb.update_group_settings(update.effective_chat.id, **{what: lst})
        await update.effective_message.reply_text(f"اضافه شد: {args[1]}")
    elif op == "del" and len(args) > 1:
        what = "forcesub_channels"
        lst = [x for x in s.get(what, []) if x != args[1]]
        lstg = [x for x in s.get("forcesub_groups", []) if x != args[1]]
        await xdb.update_group_settings(update.effective_chat.id, forcesub_channels=lst, forcesub_groups=lstg)
        await update.effective_message.reply_text("حذف شد.")
    elif op == "messages" and len(args) > 1 and args[1].isdigit():
        await xdb.update_group_settings(update.effective_chat.id, forcesub_msg_allowed=int(args[1]))
        await update.effective_message.reply_text("OK")
    elif op == "count" and len(args) > 1 and args[1].isdigit():
        await xdb.update_group_settings(update.effective_chat.id, forcesub_ad_count=int(args[1]))
    elif op == "adoff":
        await xdb.update_group_settings(update.effective_chat.id, forcesub_ad_required=False)
    elif op == "adcount" and len(args) > 1 and args[1].isdigit():
        await xdb.update_group_settings(update.effective_chat.id, forcesub_ad_count=int(args[1]))
    elif op == "mode" and len(args) > 1:
        await xdb.update_group_settings(update.effective_chat.id, forcesub_ad_mode=args[1])
        await update.effective_message.reply_text(f"حالت: {args[1]}")
    else:
        await update.effective_message.reply_text("پارامتر نامعتبر.")


async def on_callback(update, context):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("fs|"):
        return
    await q.answer("بخش forcesub")


def register(app: Application):
    app.add_handler(CommandHandler("forcesub", cmd_forcesub))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^fs\|"))
