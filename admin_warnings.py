"""Section 8: Warning system (warn/unwarn/history/risk score/reputation)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require, is_protected_target
from ...constants import DEFAULT_WARN_LIMIT
from ...roles import ADMIN, OWNER


async def _resolve(update, context):
    msg = update.effective_message
    if msg and msg.reply_to_message and msg.reply_to_message.from_user:
        return msg.reply_to_message.from_user
    if context.args and context.args[0].isdigit():
        from telegram import User
        return User(id=int(context.args[0]), first_name=context.args[0], is_bot=False)
    return None


@require(ADMIN)
async def cmd_warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await _resolve(update, context)
    if not target:
        await update.effective_message.reply_text("روی پیام ریپلای کنید یا آیدی بدهید.")
        return
    if await is_protected_target(context, update.effective_chat.id, target.id):
        await update.effective_message.reply_text("روی owner/admin اعمال نمی‌شود.")
        return
    reason = " ".join(context.args[1:]) or "اخطار ادمین"
    s = await xdb.get_group_settings(update.effective_chat.id)
    count, reasons = await xdb.group_warnings_get(update.effective_chat.id, target.id) if hasattr(xdb, "group_warnings_get") else await _warns_get(update.effective_chat.id, target.id)
    count += 1
    reasons.append(reason)
    await _warns_set(update.effective_chat.id, target.id, count, reasons[-10:])
    await xdb.risk_add(update.effective_chat.id, target.id, 1)
    await xdb.incr_stat(update.effective_chat.id, "warnings")
    await xdb.log(update.effective_chat.id, update.effective_user.id, "warn", target.id, reason=reason, count=count)
    limit = int(s.get("warn_limit", DEFAULT_WARN_LIMIT))
    if count >= limit:
        await _auto_action(context, update.effective_chat.id, target.id, s)
    await update.effective_message.reply_text(f"⚠️ اخطار: {count}/{limit}")


@require(ADMIN)
async def cmd_unwarn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await _resolve(update, context)
    if not target:
        return
    count, reasons = await _warns_get(update.effective_chat.id, target.id)
    if count <= 0:
        await update.effective_message.reply_text("اخطاری نیست.")
        return
    count -= 1
    reasons = reasons[:-1]
    await _warns_set(update.effective_chat.id, target.id, count, reasons)
    await update.effective_message.reply_text(f"♻️ اخطار: {count}")


@require(ADMIN)
async def cmd_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await _resolve(update, context)
    if not target:
        return
    count, reasons = await _warns_get(update.effective_chat.id, target.id)
    msg = "\n".join(f"• {r}" for r in reasons[-10:]) or "-"
    await update.effective_message.reply_text(
        f"📜 اخطارهای کاربر <code>{target.id}</code>: {count}\n{msg}",
        parse_mode="HTML")


@require(ADMIN)
async def cmd_warnlimit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("استفاده: /warnlimit 3")
        return
    v = max(1, min(10, int(context.args[0])))
    await xdb.update_group_settings(update.effective_chat.id, warn_limit=v)
    await update.effective_message.reply_text(f"حد اخطار: {v}")


@require(ADMIN)
async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await _resolve(update, context)
    if not target:
        return
    r = await xdb.risk_get(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(f"🧮 Risk Score <code>{target.id}</code>: {r['points']}", parse_mode="HTML")


@require(ADMIN)
async def cmd_reputation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = await _resolve(update, context)
    if not target:
        return
    r = await xdb.reputation_get(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(f"⭐ Reputation <code>{target.id}</code>: {r['score']}", parse_mode="HTML")


async def _warns_get(chat_id, user_id):
    return await _Warns(chat_id, user_id).get()


async def _warns_set(chat_id, user_id, count, reasons):
    await _Warns(chat_id, user_id).set(count, reasons)


class _Warns:
    def __init__(self, chat_id, user_id):
        self.chat_id = chat_id
        self.user_id = user_id

    async def get(self):
        import aiosqlite, json as _j
        async with aiosqlite.connect(xdb.path) as c:
            c.row_factory = aiosqlite.Row
            cur = await c.execute(
                "SELECT count, reasons FROM warnings WHERE chat_id=? AND user_id=?",
                (self.chat_id, self.user_id))
            r = await cur.fetchone()
        if not r:
            return 0, []
        return int(r["count"]), _j.loads(r["reasons"] or "[]")

    async def set(self, count, reasons):
        import aiosqlite, json as _j, time
        async with aiosqlite.connect(xdb.path) as c:
            if count <= 0:
                await c.execute(
                    "DELETE FROM warnings WHERE chat_id=? AND user_id=?",
                    (self.chat_id, self.user_id))
            else:
                await c.execute(
                    "INSERT OR REPLACE INTO warnings(chat_id, user_id, count, reasons, updated_at) VALUES(?,?,?,?,?)",
                    (self.chat_id, self.user_id, count, _j.dumps(reasons[-10:], ensure_ascii=False), time.time()))
            await c.commit()


async def _auto_action(context, chat_id, user_id, s):
    action = s.get("antispam_action", "kick")
    if action == "ban":
        await context.bot.ban_chat_member(chat_id, user_id)
        await xdb.log(chat_id, user_id, "auto_ban", user_id, source="warn_limit")
    elif action == "kick":
        await context.bot.ban_chat_member(chat_id, user_id)
        await context.bot.unban_chat_member(chat_id, user_id)
        await xdb.log(chat_id, user_id, "auto_kick", user_id, source="warn_limit")
    elif action == "mute":
        from telegram import ChatPermissions
        await context.bot.restrict_chat_member(chat_id, user_id, permissions=ChatPermissions(can_send_messages=False))
    elif action == "tempban":
        await context.bot.ban_chat_member(chat_id, user_id)
    await xdb.reputation_set(chat_id, user_id, max(0, 100 - 10 * (await _warns_get(chat_id, user_id))[0]))


def register(app: Application):
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("unwarn", cmd_unwarn))
    app.add_handler(CommandHandler("warnings", cmd_warnings))
    app.add_handler(CommandHandler("warnlimit", cmd_warnlimit))
    app.add_handler(CommandHandler("risk", cmd_risk))
    app.add_handler(CommandHandler("reputation", cmd_reputation))
