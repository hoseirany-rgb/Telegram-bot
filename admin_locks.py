"""Section 2: Locks (link/hyperlink/bot/channel-post/forward/username/lang/font/
english/video/video-note/gif/story/phone/tag/inline/MsgPv)."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN

LABELS = [
    ("lock_link", "لینک"),
    ("lock_hyperlink", "هایپرلینک"),
    ("lock_bot", "ربات"),
    ("lock_channel_post", "پست کانال"),
    ("lock_forward", "فوروارد"),
    ("lock_username", "یوزرنیم"),
    ("lock_lang", "زبان‌ها"),
    ("lock_font", "فونت"),
    ("lock_english", "انگلیسی"),
    ("lock_video", "فیلم"),
    ("lock_video_note", "فیلم سلفی"),
    ("lock_gif", "گیف"),
    ("lock_story", "استوری"),
    ("lock_phone", "شماره تلفن"),
    ("lock_tag", "تگ"),
    ("lock_inline", "اینلاین"),
    ("lock_msg_pv", "MsgPv"),
]


def cd(t: str, **kw) -> str:
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


def kb(chat_id, s):
    rows = []
    pairs = list(LABELS)
    for i in range(0, len(pairs), 2):
        chunk = pairs[i:i+2]
        rows.append([
            InlineKeyboardButton(
                f"{'✅' if s.get(k, False) else '❌'} {lab}",
                callback_data=cd("lck", c=chat_id, k=k),
            ) for k, lab in chunk
        ])
    rows.append([InlineKeyboardButton("🔒 همه", callback_data=cd("lck", c=chat_id, k="all"))])
    rows.append([InlineKeyboardButton("✖️ بستن", callback_data=cd("lck", c=chat_id, k="close"))])
    return InlineKeyboardMarkup(rows)


@require(ADMIN)
async def cmd_lock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await xdb.get_group_settings(update.effective_chat.id)
    if not context.args:
        await update.effective_message.reply_text("🔐 پنل قفل‌ها:", reply_markup=kb(update.effective_chat.id, s))
        return
    arg = context.args[0]
    if arg == "all":
        cur = not all(s.get(k, False) for _, _ in LABELS)
        patch = {k: cur for k, _ in LABELS}
        await xdb.update_group_settings(update.effective_chat.id, **patch)
        await update.effective_message.reply_text(f"همه قفل‌ها {'روشن' if cur else 'خاموش'} شد.")
        return
    if any(arg == k for k, _ in LABELS):
        cur = not s.get(arg, False)
        await xdb.update_group_settings(update.effective_chat.id, **{arg: cur})
        await update.effective_message.reply_text(f"{arg} → {'ON' if cur else 'OFF'}")
        return
    await update.effective_message.reply_text("کلید نامعتبر.")


async def on_callback(update, context):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("lck|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    k = out.get("k"); cid = int(out.get("c"))
    if k == "close":
        await q.delete_message(); return
    s = await xdb.get_group_settings(cid)
    if k == "all":
        cur = not all(s.get(kk, False) for kk, _ in LABELS)
        await xdb.update_group_settings(cid, **{kk: cur for kk, _ in LABELS})
    else:
        cur = not s.get(k, False)
        await xdb.update_group_settings(cid, **{k: cur})
    s = await xdb.get_group_settings(cid)
    await q.edit_message_reply_markup(kb(cid, s))
    await q.answer(f"{k}: {'ON' if cur else 'OFF'}")


def register(app: Application):
    app.add_handler(CommandHandler("lock", cmd_lock))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^lck\|"))
