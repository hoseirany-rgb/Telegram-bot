"""Section 1: Group Management (settings panel, admin list, backup, transfer)."""
from __future__ import annotations

from html import escape
from json import dumps

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...constants import CALLBACK_DATA_MAX
from ...roles import ADMIN, OWNER, SPECIAL

SECTION = "group"


def cd(t: str, **kw) -> str:
    sfx = "|".join(f"{k}={v}" for k, v in kw.items())
    raw = t if not sfx else f"{t}|{sfx}"
    return raw[:CALLBACK_DATA_MAX]


LOCK_LABELS = {
    "lock_link": "لینک", "lock_hyperlink": "هایپرلینک",
    "lock_bot": "ربات", "lock_channel_post": "پست کانال",
    "lock_forward": "فوروارد", "lock_username": "یوزرنیم",
    "lock_lang": "زبان‌ها", "lock_font": "فونت",
    "lock_english": "انگلیسی", "lock_video": "فیلم",
    "lock_video_note": "فیلم سلفی", "lock_gif": "گیف",
    "lock_story": "استوری", "lock_phone": "شماره تلفن",
    "lock_tag": "تگ", "lock_inline": "اینلاین",
    "lock_msg_pv": "MsgPv",
}


def label_for(key: str) -> str:
    return LOCK_LABELS.get(key, key)


# --- commands ---
@require(ADMIN)
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await xdb.get_group_settings(update.effective_chat.id)
    await update.effective_message.reply_text(
        "⚙️ پنل تنظیمات گروه\nیکی از بخش‌ها را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔒 قفل‌ها", callback_data=cd("grp", op="locks", c=update.effective_chat.id))],
            [InlineKeyboardButton("🚫 ضد تبلیغ", callback_data=cd("grp", op="antipromo", c=update.effective_chat.id))],
            [InlineKeyboardButton("🤖 ضد اسپم", callback_data=cd("grp", op="antispam", c=update.effective_chat.id))],
            [InlineKeyboardButton("📡 عضویت اجباری", callback_data=cd("grp", op="forcesub", c=update.effective_chat.id))],
            [InlineKeyboardButton("🧹 پاکسازی", callback_data=cd("grp", op="cleanup", c=update.effective_chat.id))],
            [InlineKeyboardButton("🌙 قفل خودکار", callback_data=cd("grp", op="autolock", c=update.effective_chat.id))],
            [InlineKeyboardButton("⚠️ هشدار", callback_data=cd("grp", op="warn", c=update.effective_chat.id))],
            [InlineKeyboardButton("🛡 امنیت", callback_data=cd("grp", op="security", c=update.effective_chat.id))],
            [InlineKeyboardButton("🧠 هوش مصنوعی", callback_data=cd("grp", op="ai", c=update.effective_chat.id))],
            [InlineKeyboardButton("✖️ بستن", callback_data=cd("grp", op="close", c=update.effective_chat.id))],
        ]),
    )


@require(ADMIN)
async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = await xdb.stats(update.effective_chat.id, days=1)
    today = s[0] if s else {}
    txt = (
        "📊 داشبورد گروه\n"
        f"پیام‌های امروز: {today.get('messages', 0)}\n"
        f"لینک‌ها: {today.get('links', 0)}\n"
        f"اخطارها: {today.get('warnings', 0)}\n"
        f"بن‌ها: {today.get('bans', 0)} | کیک: {today.get('kicks', 0)} | میوت: {today.get('mutes', 0)}\n"
        f"ورودها: {today.get('joins', 0)} | گزارش‌ها: {today.get('reports', 0)}"
    )
    await update.effective_message.reply_text(txt)


@require(OWNER)
async def cmd_setowner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("استفاده: /setowner <user_id>")
        return
    await xdb.update_group_settings(update.effective_chat.id, owner_id=int(context.args[0]))
    await update.effective_message.reply_text(f"مالک گروه روی {context.args[0]} تنظیم شد.")


@require(OWNER)
async def cmd_promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message.reply_to_message.from_user if update.effective_message.reply_to_message else None
    if not target:
        await update.effective_message.reply_text("روی پیام کاربر ریپلای کنید.")
        return
    await context.bot.promote_chat_member(
        update.effective_chat.id, target.id,
        can_change_info=True, can_delete_messages=True, can_invite_users=True,
        can_restrict_members=True, can_pin_messages=True, can_promote_members=False,
    )
    await xdb.log(update.effective_chat.id, update.effective_user.id, "promote", target.id)
    await update.effective_message.reply_text(f"کاربر {target.first_name} ادمین شد.")


@require(OWNER)
async def cmd_demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message.reply_to_message.from_user if update.effective_message.reply_to_message else None
    if not target:
        await update.effective_message.reply_text("روی پیام ریپلای کنید.")
        return
    await context.bot.promote_chat_member(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(f"کاربر {target.first_name} تنزل یافت.")


@require(OWNER)
async def cmd_adminrights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("روی پیام ریپلای کنید و mask را بنویسید.")
        return
    if not context.args:
        await update.effective_message.reply_text("mask لازم است: change_info | delete_messages | invite_users | restrict_members | pin_messages")
        return
    mask = {
        "change_info": False, "delete_messages": False, "invite_users": False,
        "restrict_members": False, "pin_messages": False, "promote_members": False,
        "manage_video_chats": False, "manage_chat": False, "anonymous": False,
    }
    for a in context.args[0].split(","):
        a = a.strip()
        if a in mask:
            mask[a] = True
    kw = {f"can_{k}": v for k, v in mask.items()}
    await context.bot.promote_chat_member(update.effective_chat.id, update.effective_message.reply_to_message.from_user.id, **kw)
    await update.effective_message.reply_text("دسترسی‌های ادمین تنظیم شد.")


@require(ADMIN)
async def cmd_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("استفاده: /vip add|del|list <user_id>")
        return
    op = args[0].lower()
    s = await xdb.get_group_settings(update.effective_chat.id)
    vips = list(s.get("vip_users", []))
    if op == "add" and len(args) > 1 and args[1].isdigit():
        vips.append(int(args[1]))
        await xdb.update_group_settings(update.effective_chat.id, vip_users=vips)
        await update.effective_message.reply_text(f"کاربر {args[1]} به ویژه‌ها اضافه شد.")
    elif op == "del" and len(args) > 1 and args[1].isdigit():
        vips = [v for v in vips if v != int(args[1])]
        await xdb.update_group_settings(update.effective_chat.id, vip_users=vips)
        await update.effective_message.reply_text("کاربر از ویژه‌ها حذف شد.")
    elif op == "list":
        msg = "کاربران ویژه:\n" + "\n".join(f"• <code>{v}</code>" for v in vips) or "خالی"
        await update.effective_message.reply_text(msg, parse_mode="HTML")
    else:
        await update.effective_message.reply_text("دستور نامعتبر.")


@require(ADMIN)
async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = await xdb.get_group_settings(update.effective_chat.id)
    bl = dict(s.get("blacklist", {"users": [], "words": []}))
    op = args[0] if args else "list"
    if op == "user" and len(args) > 1 and args[1].isdigit():
        bl.setdefault("users", []).append(int(args[1]))
        await xdb.update_group_settings(update.effective_chat.id, blacklist=bl)
        await update.effective_message.reply_text("کاربر به بلک‌لیست افزوده شد.")
    elif op == "word" and len(args) > 1:
        bl.setdefault("words", []).append(args[1])
        await xdb.update_group_settings(update.effective_chat.id, blacklist=bl)
        await update.effective_message.reply_text("کلمه به بلک‌لیست افزوده شد.")
    elif op == "list":
        u = "\n".join(f"• <code>{v}</code>" for v in bl.get("users", [])) or "-"
        w = "\n".join(f"• {v}" for v in bl.get("words", [])) or "-"
        await update.effective_message.reply_text(f"کاربران:\n{u}\nکلمات:\n{w}", parse_mode="HTML")
    else:
        await update.effective_message.reply_text("استفاده: user | word | list")


@require(ADMIN)
async def cmd_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    s = await xdb.get_group_settings(update.effective_chat.id)
    wl = dict(s.get("whitelist", {"users": [], "words": []}))
    op = args[0] if args else "list"
    if op == "user" and len(args) > 1 and args[1].isdigit():
        wl.setdefault("users", []).append(int(args[1]))
        await xdb.update_group_settings(update.effective_chat.id, whitelist=wl)
        await update.effective_message.reply_text("کاربر به وایت‌لیست افزوده شد.")
    elif op == "word" and len(args) > 1:
        wl.setdefault("words", []).append(args[1])
        await xdb.update_group_settings(update.effective_chat.id, whitelist=wl)
        await update.effective_message.reply_text("کلمه به وایت‌لیست افزوده شد.")
    elif op == "list":
        u = "\n".join(f"• <code>{v}</code>" for v in wl.get("users", [])) or "-"
        w = "\n".join(f"• {v}" for v in wl.get("words", [])) or "-"
        await update.effective_message.reply_text(f"کاربران:\n{u}\nکلمات:\n{w}", parse_mode="HTML")
    else:
        await update.effective_message.reply_text("استفاده: user | word | list")


@require(ADMIN)
async def cmd_audit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n = int(context.args[0]) if context.args and context.args[0].isdigit() else 20
    rows = await xdb.recent_audit(update.effective_chat.id, limit=n)
    if not rows:
        await update.effective_message.reply_text("رویدادی ثبت نشده.")
        return
    lines = []
    for r in rows:
        dt = r["created_at"]
        lines.append(f"• #{r['id']} {r['action']} target={r['target_id']} actor={r['actor_id']}")
    await update.effective_message.reply_text("🧾 گزارش فعالیت‌ها\n" + "\n".join(lines))


@require(ADMIN)
async def cmd_adminlog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await xdb.admin_actions_24h(update.effective_chat.id)
    if not rows:
        await update.effective_message.reply_text("در ۲۴ ساعت گذشته اقدامی ثبت نشده.")
        return
    lines = [f"• actor=<code>{r['actor_id']}</code> → {r['action']} ×{r['c']}" for r in rows]
    await update.effective_message.reply_text("لاگ مدیریتی ۲۴ ساعت:\n" + "\n".join(lines), parse_mode="HTML")


@require(ADMIN)
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    blob = await xdb.dump_group(update.effective_chat.id)
    body = dumps(blob, ensure_ascii=False, indent=2)
    if len(body) > 3500:
        body = body[:3500] + "\n..."
    await update.effective_message.reply_text("📦 بکاپ تنظیمات:\n```json\n" + body + "\n```", parse_mode="MARKDOWN")


@require(OWNER)
async def cmd_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_message.reply_to_message or not update.effective_message.reply_to_message.document:
        await update.effective_message.reply_text("روی فایل JSON پاسخ دهید.")
        return
    file = await update.effective_message.reply_to_message.document.get_file()
    data = await file.download_as_bytearray()
    import json as _j
    try:
        blob = _j.loads(bytes(data).decode("utf-8"))
    except Exception as e:
        await update.effective_message.reply_text(f"JSON نامعتبر: {e}")
        return
    await xdb.restore_group(update.effective_chat.id, blob)
    await update.effective_message.reply_text("✅ تنظیمات از بکاپ بازیابی شد.")


@require(OWNER)
async def cmd_resetsettings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or context.args[0] != "confirm":
        await update.effective_message.reply_text("برای تأیید: /resetsettings confirm")
        return
    await xdb.reset_group(update.effective_chat.id)
    await update.effective_message.reply_text("♻️ تنظیمات ریست شد.")


@require(OWNER)
async def cmd_transfercfg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].lstrip("-").isdigit():
        await update.effective_message.reply_text("استفاده: /transfercfg <chat_id>")
        return
    src = int(context.args[0])
    await xdb.copy_group_to(src, update.effective_chat.id)
    await update.effective_message.reply_text(f"تنظیمات از {src} کپی شد.")


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not q or not q.data or not q.data.startswith("grp|"):
        return
    parts = q.data.split("|")
    out = {"action": parts[0]}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1); out[k] = v
    op = out.get("op")
    if op == "close":
        await q.delete_message()
        return
    await q.answer(f"بخش {op} باز می‌شود...")
    await q.edit_message_text(f"بخش: {op}\n(در فایل مربوط پیاده شده)")


def register(app: Application):
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("setowner", cmd_setowner))
    app.add_handler(CommandHandler("promote", cmd_promote))
    app.add_handler(CommandHandler("demote", cmd_demote))
    app.add_handler(CommandHandler("adminrights", cmd_adminrights))
    app.add_handler(CommandHandler("vip", cmd_vip))
    app.add_handler(CommandHandler("blacklist", cmd_blacklist))
    app.add_handler(CommandHandler("whitelist", cmd_whitelist))
    app.add_handler(CommandHandler("audit", cmd_audit))
    app.add_handler(CommandHandler("adminlog", cmd_adminlog))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("restore", cmd_restore))
    app.add_handler(CommandHandler("resetsettings", cmd_resetsettings))
    app.add_handler(CommandHandler("transfercfg", cmd_transfercfg))
    app.add_handler(CallbackQueryHandler(on_callback, pattern=r"^grp\|"))
