"""Section 3: Anti-Promotion (name, bio, hidden links, short links, spam-wave,
raid, join-attack, mention-spam, emoji-spam, flood, bot-attack, fake-account)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN

FLAGS = [
    ("ad_name_check", "تشخیص تبلیغ نام"),
    ("ad_bio_check", "تشخیص تبلیغ بیو"),
    ("ad_hidden_link", "لینک مخفی"),
    ("ad_short_link", "Short Link"),
    ("ad_spam_wave", "Spam Wave"),
    ("ad_raid", "Raid"),
    ("ad_join_attack", "Join Attack"),
    ("ad_mention_spam", "Mention Spam"),
    ("ad_emoji_spam", "Emoji Spam"),
    ("ad_flood", "Flood"),
    ("ad_bot_attack", "Bot Attack"),
    ("ad_fake_account", "Fake Account"),
]
PARAMS = ["ad_severity", "ad_limit", "ad_auto_purge", "ad_purge_seconds"]


def cd(t, **kw):
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


@require(ADMIN)
async def cmd_antipromo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await xdb.get_group_settings(update.effective_chat.id)
    args = context.args or []
    if not args:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        rows = []
        for k, lbl in FLAGS:
            rows.append([InlineKeyboardButton(
                f"{'✅' if s.get(k) else '❌'} {lbl}",
                callback_data=cd("adp", c=update.effective_chat.id, k=k))])
        rows.append([InlineKeyboardButton(
            f"شدت: {s.get('ad_severity')}", callback_data=cd("adp", c=update.effective_chat.id, k="ad_severity"))])
        rows.append([InlineKeyboardButton(
            f"محدودیت: {s.get('ad_limit')}", callback_data=cd("adp", c=update.effective_chat.id, k="ad_limit"))])
        rows.append([InlineKeyboardButton(
            f"{'✅' if s.get('ad_auto_purge') else '❌'} پاکسازی خودکار",
            callback_data=cd("adp", c=update.effective_chat.id, k="ad_auto_purge"))])
        await update.effective_message.reply_text("🚫 ضد تبلیغ:", reply_markup=InlineKeyboardMarkup(rows))
        return
    op = args[0]
    if op in {k for k, _ in FLAGS}:
        new = not s.get(op)
        await xdb.update_group_settings(update.effective_chat.id, **{op: new})
        await update.effective_message.reply_text(f"{op} → {'ON' if new else 'OFF'}")
    elif op == "severity" and len(args) > 1 and args[1].isdigit():
        v = max(1, min(5, int(args[1])))
        await xdb.update_group_settings(update.effective_chat.id, ad_severity=v)
        await update.effective_message.reply_text(f"شدت بررسی: {v}")
    elif op == "limit" and len(args) > 1 and args[1].isdigit():
        v = max(1, int(args[1]))
        await xdb.update_group_settings(update.effective_chat.id, ad_limit=v)
        await update.effective_message.reply_text(f"محدودیت: {v}")
    elif op == "purge" and len(args) > 1 and args[1].isdigit():
        await xdb.update_group_settings(update.effective_chat.id, ad_purge_seconds=int(args[1]))
        await update.effective_message.reply_text("زمان پاکسازی به‌روز شد.")
    else:
        await update.effective_message.reply_text("دستور نامعتبر.")


@require(ADMIN)
async def cmd_adscan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await xdb.get_group_settings(update.effective_chat.id)
    await update.effective_message.reply_text(
        "🔍 اسکن تبلیغ فعال\n" +
        "\n".join(f"{'✅' if s.get(k) else '❌'} {lbl}" for k, lbl in FLAGS))


@require(ADMIN)
async def cmd_purgeads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await xdb.get_group_settings(update.effective_chat.id)
    secs = int(s.get("ad_purge_seconds", 60))
    await update.effective_message.reply_text(f"🧹 پاکسازی تبلیغات هر {secs} ثانیه اجرا می‌شود.")
    await xdb.log(update.effective_chat.id, update.effective_user.id, "purgeads")


async def on_callback(update, context):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("adp|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    k = out.get("k"); cid = int(out.get("c"))
    s = await xdb.get_group_settings(cid)
    if k == "ad_severity":
        new = (int(s.get("ad_severity", 2)) % 5) + 1
        await xdb.update_group_settings(cid, ad_severity=new)
    elif k == "ad_limit":
        new = (int(s.get("ad_limit", 3))) + 1
        await xdb.update_group_settings(cid, ad_limit=new)
    elif k == "ad_auto_purge":
        new = not s.get("ad_auto_purge", True)
        await xdb.update_group_settings(cid, ad_auto_purge=new)
    elif k in {kk for kk, _ in FLAGS}:
        new = not s.get(k)
        await xdb.update_group_settings(cid, **{k: new})
    await q.answer(f"{k} اعمال شد.")


def register(app: Application):
    app.add_handler(CommandHandler("antipromo", cmd_antipromo))
    app.add_handler(CommandHandler("adscan", cmd_adscan))
    app.add_handler(CommandHandler("purgeads", cmd_purgeads))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^adp\|"))
