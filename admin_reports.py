"""Section 12: Reporting (daily/weekly/monthly/security/admin/user/spam/risk)."""
from __future__ import annotations

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...roles import ADMIN


def _fmt_row(day, r):
    return (f"{day}  msg:{r['messages']} link:{r['links']} warn:{r['warnings']} "
            f"ban:{r['bans']} kick:{r['kicks']} mute:{r['mutes']} del:{r['deletes']} "
            f"rep:{r['reports']} join:{r['joins']}")


@require(ADMIN)
async def cmd_dailyreport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await xdb.stats(update.effective_chat.id, 1)
    if not rows:
        await update.effective_message.reply_text("داده‌ای ثبت نشده.")
        return
    await update.effective_message.reply_text("🗓 گزارش روزانه\n" + _fmt_row(rows[0]["day"], rows[0]))


@require(ADMIN)
async def cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await xdb.stats(update.effective_chat.id, 7)
    body = "\n".join(_fmt_row(r["day"], r) for r in rows)
    await update.effective_message.reply_text("📅 گزارش هفتگی:\n" + body)


@require(ADMIN)
async def cmd_monthly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await xdb.stats(update.effective_chat.id, 30)
    body = "\n".join(_fmt_row(r["day"], r) for r in rows)
    if len(body) > 3500:
        body = body[:3500] + "\n..."
    await update.effective_message.reply_text("🗓 گزارش ماهانه:\n" + body)


@require(ADMIN)
async def cmd_secreport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await xdb.stats(update.effective_chat.id, 7)
    sec_hits = sum((r.get("risk_hits", 0) for r in rows))
    await update.effective_message.reply_text(
        f"🛡 گزارش امنیت (۷ روز)\nرخدادهای ریسک: {sec_hits}\n"
        f"ماژول‌های فعال: {sum(1 for r in rows)} لاگ")


@require(ADMIN)
async def cmd_adminreport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await xdb.admin_actions_24h(update.effective_chat.id)
    body = "\n".join(f"• actor={r['actor_id']} → {r['action']} ×{r['c']}" for r in rows) or "-"
    await update.effective_message.reply_text("👮 گزارش ادمین‌ها:\n" + body)


@require(ADMIN)
async def cmd_userstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = update.effective_message.reply_to_message.from_user if update.effective_message.reply_to_message else None
    if not target:
        await update.effective_message.reply_text("روی پیام ریپلای کنید.")
        return
    warns_count, reasons = await _w_get(update.effective_chat.id, target.id)
    risk = await xdb.risk_get(update.effective_chat.id, target.id)
    rep = await xdb.reputation_get(update.effective_chat.id, target.id)
    await update.effective_message.reply_text(
        f"👤 آمار کاربر <code>{target.id}</code>\n"
        f"اخطارها: {warns_count}\nRisk: {risk['points']}\nReputation: {rep['score']}",
        parse_mode="HTML")


@require(ADMIN)
async def cmd_spamstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await xdb.stats(update.effective_chat.id, 1)
    if not rows:
        await update.effective_message.reply_text("بدون داده.")
        return
    r = rows[0]
    await update.effective_message.reply_text(
        f"🚨 گزارش اسپم امروز: warns={r['warnings']} deletes={r['deletes']} links={r['links']}")


@require(ADMIN)
async def cmd_riskstats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await xdb.stats(update.effective_chat.id, 7)
    body = "\n".join(f"• {r['day']}: risk_hits={r.get('risk_hits', 0)}" for r in rows)
    await update.effective_message.reply_text("🧮 Risk Stats:\n" + body)


async def _w_get(chat_id, user_id):
    import aiosqlite, json as _j
    async with aiosqlite.connect(xdb.path) as c:
        c.row_factory = aiosqlite.Row
        cur = await c.execute(
            "SELECT count, reasons FROM warnings WHERE chat_id=? AND user_id=?",
            (chat_id, user_id))
        r = await cur.fetchone()
    if not r:
        return 0, []
    return int(r["count"]), _j.loads(r["reasons"] or "[]")


def register(app: Application):
    app.add_handler(CommandHandler("dailyreport", cmd_dailyreport))
    app.add_handler(CommandHandler("weekly", cmd_weekly))
    app.add_handler(CommandHandler("monthly", cmd_monthly))
    app.add_handler(CommandHandler("secreport", cmd_secreport))
    app.add_handler(CommandHandler("adminreport", cmd_adminreport))
    app.add_handler(CommandHandler("userstats", cmd_userstats))
    app.add_handler(CommandHandler("spamstats", cmd_spamstats))
    app.add_handler(CommandHandler("riskstats", cmd_riskstats))
