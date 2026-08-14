from __future__ import annotations

from html import escape

from telegram import Update
from telegram.constants import ChatType, ParseMode
from telegram.ext import ContextTypes

from ..config import settings
from ..db import db
from ..utils import admin_panel, ban_user, is_admin, is_protected_target, kick_user, mute_user, settings_keyboard, unban_user, unmute_user


async def _require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if await is_admin(update, context):
        return True
    if update.effective_message:
        await update.effective_message.reply_text("فقط ادمین‌های گروه به این دستور دسترسی دارند.")
    return False


async def _resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user
    if context.args:
        first = context.args[0].lstrip("@").strip()
        if first.isdigit():
            from telegram import User
            return User(id=int(first), first_name=first, is_bot=False)
    return None


async def _ensure_actionable(update: Update, context: ContextTypes.DEFAULT_TYPE, target) -> bool:
    if not target or not update.effective_chat or not update.effective_user:
        if update.effective_message:
            await update.effective_message.reply_text("روی پیام کاربر ریپلای کنید یا آیدی عددی او را بدهید.")
        return False
    if target.id == update.effective_user.id:
        await update.effective_message.reply_text("امکان اعمال این دستور روی خودتان وجود ندارد.")
        return False
    if await is_protected_target(context, update.effective_chat.id, target.id):
        await update.effective_message.reply_text("روی owner/admin اعمال نمی‌شود.")
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_chat:
        return
    if update.effective_chat.type == ChatType.PRIVATE:
        await update.effective_message.reply_text(
            "👋 سلام! من BotGuardian Enterprise هستم.\n"
            "من را به سوپرگروه اضافه کنید و /settings را اجرا کنید."
        )
        return
    await update.effective_message.reply_text(
        "🛡 BotGuardian فعال است.\n"
        "دستورات اصلی: /settings /warn /mute /kick /ban /stats /dailyreport /id"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "/settings پنل تنظیمات\n"
        "/antispam on|off\n/antilink on|off\n/anti_forward on|off\n"
        "/captcha on|off\n/welcome on|off\n"
        "/warnlimit <n>\n/warnings <reply|id>\n/unwarn <reply|id>\n"
        "/warn /mute /unmute /kick /ban /unban\n"
        "/report روی پیام ریپلای کنید\n/stats\n/dailyreport\n/id"
    )


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    chat = update.effective_chat
    settings_dict = await db.get_group_settings(chat.id)
    await update.effective_message.reply_text("⚙️ تنظیمات زنده گروه", reply_markup=settings_keyboard(chat.id, settings_dict))


async def cmd_userinfo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _resolve_target(update, context)
    if not target:
        await update.effective_message.reply_text("روی پیام کاربر ریپلای کنید یا آیدی عددی بدهید.")
        return
    count, reasons = await db.get_warnings(update.effective_chat.id, target.id)
    reason_text = "\n".join(f"- {escape(r)}" for r in reasons[-5:]) or "-"
    await update.effective_message.reply_text(
        f"👤 <a href=\"tg://user?id={target.id}\">{escape(target.first_name or str(target.id))}</a>\n"
        f"ID: <code>{target.id}</code>\nاخطارها: {count}\n{reason_text}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel(update.effective_chat.id, target.id),
    )


async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    target = await _resolve_target(update, context)
    if not await _ensure_actionable(update, context, target):
        return
    reason = " ".join(context.args[1:]).strip() or "اخطار توسط ادمین"
    count = await db.add_warning(update.effective_chat.id, target.id, reason)
    await db.incr_stat(update.effective_chat.id, "warnings")
    await db.log(update.effective_chat.id, update.effective_user.id, "warn", target.id, reason=reason, warning_count=count)
    await update.effective_message.reply_text(f"⚠️ اخطار ثبت شد: {count}")


async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target = await _resolve_target(update, context)
    if not target:
        await update.effective_message.reply_text("روی پیام کاربر ریپلای کنید یا آیدی عددی بدهید.")
        return
    count, reasons = await db.get_warnings(update.effective_chat.id, target.id)
    body = "\n".join(f"- {r}" for r in reasons[-10:]) or "-"
    await update.effective_message.reply_text(f"اخطارهای کاربر <code>{target.id}</code>: {count}\n{body}", parse_mode=ParseMode.HTML)


async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    target = await _resolve_target(update, context)
    if not await _ensure_actionable(update, context, target):
        return
    count, reasons = await db.get_warnings(update.effective_chat.id, target.id)
    new_count = max(0, count - 1)
    new_reasons = reasons[:-1] if reasons else []
    await db.set_warning_count(update.effective_chat.id, target.id, new_count, new_reasons)
    await db.log(update.effective_chat.id, update.effective_user.id, "unwarn", target.id, old_count=count, new_count=new_count)
    await update.effective_message.reply_text(f"♻️ اخطار کم شد: {new_count}")


async def cmd_warnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("استفاده: /warnlimit 3")
        return
    limit = max(1, min(10, int(context.args[0])))
    await db.update_group_settings(update.effective_chat.id, warn_limit=limit)
    await update.effective_message.reply_text(f"حد اخطار روی {limit} تنظیم شد.")


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    target = await _resolve_target(update, context)
    if not await _ensure_actionable(update, context, target):
        return
    minutes = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 30
    await mute_user(context, update.effective_chat.id, target.id, minutes * 60)
    await db.incr_stat(update.effective_chat.id, "mutes")
    await db.log(update.effective_chat.id, update.effective_user.id, "mute", target.id, minutes=minutes)
    await update.effective_message.reply_text(f"🔇 کاربر {minutes} دقیقه میوت شد.")


async def cmd_unmute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    target = await _resolve_target(update, context)
    if not target:
        await update.effective_message.reply_text("روی پیام کاربر ریپلای کنید یا آیدی عددی بدهید.")
        return
    await unmute_user(context, update.effective_chat.id, target.id)
    await db.log(update.effective_chat.id, update.effective_user.id, "unmute", target.id)
    await update.effective_message.reply_text("🔊 کاربر آن‌میوت شد.")


async def cmd_kick(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    target = await _resolve_target(update, context)
    if not await _ensure_actionable(update, context, target):
        return
    await kick_user(context, update.effective_chat.id, target.id)
    await db.incr_stat(update.effective_chat.id, "kicks")
    await db.log(update.effective_chat.id, update.effective_user.id, "kick", target.id)
    await update.effective_message.reply_text("👢 کاربر کیک شد.")


async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    target = await _resolve_target(update, context)
    if not await _ensure_actionable(update, context, target):
        return
    await ban_user(context, update.effective_chat.id, target.id)
    await db.incr_stat(update.effective_chat.id, "bans")
    await db.log(update.effective_chat.id, update.effective_user.id, "ban", target.id)
    await update.effective_message.reply_text("🚫 کاربر بن شد.")


async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    target = await _resolve_target(update, context)
    if not target:
        await update.effective_message.reply_text("آیدی عددی کاربر را بدهید.")
        return
    await unban_user(context, update.effective_chat.id, target.id)
    await db.log(update.effective_chat.id, update.effective_user.id, "unban", target.id)
    await update.effective_message.reply_text("✅ کاربر آن‌بن شد.")


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    if not msg or not msg.reply_to_message or not msg.reply_to_message.from_user:
        await update.effective_message.reply_text("روی پیام موردنظر ریپلای کنید و /report بزنید.")
        return
    target = msg.reply_to_message.from_user
    await db.incr_stat(update.effective_chat.id, "reports")
    await db.log(update.effective_chat.id, update.effective_user.id, "report", target.id, text=(msg.reply_to_message.text or msg.reply_to_message.caption or "")[:200])
    await msg.reply_text(
        f"🚨 گزارش ثبت شد برای <a href=\"tg://user?id={target.id}\">{escape(target.first_name or str(target.id))}</a>",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_panel(update.effective_chat.id, target.id),
    )


async def cmd_pin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    if not update.effective_message.reply_to_message:
        await update.effective_message.reply_text("روی پیام ریپلای کنید.")
        return
    await context.bot.pin_chat_message(update.effective_chat.id, update.effective_message.reply_to_message.message_id)
    await update.effective_message.reply_text("📌 پیام سنجاق شد.")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    rows = await db.get_stats(update.effective_chat.id, 7)
    if not rows:
        await update.effective_message.reply_text("هنوز آماری ثبت نشده است.")
        return
    lines = ["<code>day      msg links warns bans kicks mutes dels reps joins</code>"]
    for r in rows:
        lines.append(f"<code>{r['day']} {r['messages']:>4} {r['links']:>5} {r['warnings']:>5} {r['bans']:>4} {r['kicks']:>5} {r['mutes']:>5} {r['deletes']:>4} {r['reports']:>4} {r['joins']:>5}</code>")
    await update.effective_message.reply_text("📊 آمار ۷ روز اخیر\n" + "\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_dailyreport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _require_admin(update, context):
        return
    rows = await db.get_stats(update.effective_chat.id, 1)
    if not rows:
        await update.effective_message.reply_text("برای امروز هنوز داده‌ای ثبت نشده است.")
        return
    r = rows[0]
    await update.effective_message.reply_text(
        f"🗓 گزارش روزانه\nتاریخ: {r['day']}\nپیام‌ها: {r['messages']}\nلینک‌ها: {r['links']}\nاخطارها: {r['warnings']}\nحذف‌ها: {r['deletes']}\nگزارش‌ها: {r['reports']}\nمیوت: {r['mutes']}\nکیک: {r['kicks']}\nبن: {r['bans']}\nورودها: {r['joins']}"
    )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"chat_id: <code>{update.effective_chat.id}</code>\nuser_id: <code>{update.effective_user.id}</code>",
        parse_mode=ParseMode.HTML,
    )


async def _toggle(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str) -> None:
    if not await _require_admin(update, context):
        return
    arg = (context.args[0].lower() if context.args else "")
    if arg in {"on", "1", "true", "yes", "روشن"}:
        value = True
    elif arg in {"off", "0", "false", "no", "خاموش"}:
        value = False
    else:
        await update.effective_message.reply_text("استفاده: on | off")
        return
    await db.update_group_settings(update.effective_chat.id, **{key: value})
    await db.log(update.effective_chat.id, update.effective_user.id, f"toggle:{key}", value=value)
    await update.effective_message.reply_text(f"{key} → {'ON' if value else 'OFF'}")


async def cmd_antispam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, "antispam")


async def cmd_antilink(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, "antilink")


async def cmd_anti_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, "anti_forward")


async def cmd_captcha(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, "captcha")


async def cmd_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _toggle(update, context, "welcome")
