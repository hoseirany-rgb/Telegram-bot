"""Section 9: Security modules (Raid/Nuke/Bot/Clone/Fake/Scam/Phishing/Crypto/
Porn/Violence/Malware/Proxy/VPN/Session Hijack)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN

MODULES = [
    ("sec_anti_raid", "Anti Raid"),
    ("sec_anti_nuke", "Anti Nuke"),
    ("sec_anti_bot", "Anti Bot"),
    ("sec_anti_clone", "Anti Clone"),
    ("sec_anti_fake", "Anti Fake"),
    ("sec_anti_scam", "Anti Scam"),
    ("sec_anti_phishing", "Anti Phishing"),
    ("sec_anti_crypto", "Anti Crypto Spam"),
    ("sec_anti_porn", "Anti Porn"),
    ("sec_anti_violence", "Anti Violence"),
    ("sec_anti_malware", "Anti Malware"),
    ("sec_anti_proxy", "Anti Proxy"),
    ("sec_anti_vpn", "Anti VPN"),
    ("sec_anti_session_hijack", "Anti Session Hijack"),
]


def cd(t, **kw):
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


@require(ADMIN)
async def cmd_security(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = await xdb.get_group_settings(update.effective_chat.id)
    if not args:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = []
        for k, lbl in MODULES:
            rows.append([InlineKeyboardButton(
                f"{'✅' if s.get(k) else '❌'} {lbl}",
                callback_data=cd("sec", c=update.effective_chat.id, k=k))])
        rows.append([InlineKeyboardButton(
            f"سطح امنیت: {s.get('sec_level')}",
            callback_data=cd("sec", c=update.effective_chat.id, k="sec_level"))])
        await update.effective_message.reply_text("🛡 ماژول‌های امنیتی:", reply_markup=InlineKeyboardMarkup(rows))
        return
    op = args[0]
    if op in {k for k, _ in MODULES}:
        new = not s.get(op, False)
        await xdb.update_group_settings(update.effective_chat.id, **{op: new})
        await update.effective_message.reply_text(f"{op}: {'ON' if new else 'OFF'}")
    elif op == "level" and len(args) > 1 and args[1].isdigit():
        v = max(1, min(3, int(args[1])))
        await xdb.update_group_settings(update.effective_chat.id, sec_level=v)
        await update.effective_message.reply_text(f"سطح امنیت: {v}")
    elif op == "all":
        v = args[1] == "on"
        await xdb.update_group_settings(update.effective_chat.id, **{k: v for k, _ in MODULES})
        await update.effective_message.reply_text("همه روشن" if v else "همه خاموش")
    else:
        await update.effective_message.reply_text("پارامتر نامعتبر.")


async def on_callback(update, context):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("sec|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    k = out.get("k"); cid = int(out.get("c"))
    s = await xdb.get_group_settings(cid)
    if k == "sec_level":
        v = (int(s.get("sec_level", 1)) % 3) + 1
        await xdb.update_group_settings(cid, sec_level=v)
    elif k in {kk for kk, _ in MODULES}:
        await xdb.update_group_settings(cid, **{k: not s.get(k, False)})
    await q.answer("OK")


def register(app: Application):
    app.add_handler(CommandHandler("security", cmd_security))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^sec\|"))
