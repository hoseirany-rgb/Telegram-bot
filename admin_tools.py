"""Section 13: Tools (QR, URL Shortener, URL/Virus Scanner, Whois, IP Lookup, Ping)."""
from __future__ import annotations

import asyncio

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from ..db_ext import xdb
from ..permission import require
from ...roles import ADMIN


def _shorten(url: str) -> str:
    # local placeholder; replace with API of choice
    import hashlib
    h = hashlib.md5(url.encode()).hexdigest()[:7]
    return f"https://short.bge/{h}"


async def _virusscan(url: str) -> str:
    # placeholder heuristic (no external calls to keep defensive build safe)
    bad = {"malware", "phish", "spam", "exe", "crack"}
    score = sum(w in url.lower() for w in bad)
    return "PENDING" if score == 0 else f"SUSPICIOUS:{score}"


@require(ADMIN)
async def cmd_qr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("استفاده: /qr <text|url>")
        return
    text = " ".join(context.args)
    try:
        import qrcode, io
        img = qrcode.make(text)
        buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
        await update.effective_message.reply_photo(buf, caption="QR ساخته شد.")
    except Exception as e:
        await update.effective_message.reply_text(f"خطای QR: {e}")


@require(ADMIN)
async def cmd_shorten(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("استفاده: /shorten <url>")
        return
    url = context.args[0]
    short = _shorten(url)
    await update.effective_message.reply_text(f"🔗 کوتاه‌شده: {short}")


@require(ADMIN)
async def cmd_scanurl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("استفاده: /scanurl <url>")
        return
    url = context.args[0]
    verdict = await _virusscan(url)
    await update.effective_message.reply_text(f"🔎 Verdict: {verdict}")


@require(ADMIN)
async def cmd_virusscan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_scanurl(update, context)


@require(ADMIN)
async def cmd_whois(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("/whois <domain>")
        return
    domain = context.args[0]
    # stub
    await update.effective_message.reply_text(
        f"Whois (stub) {domain}\nRegistrar: example\nCreated: unknown\nStatus: OK")


@require(ADMIN)
async def cmd_iplookup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.effective_message.reply_text("/iplookup <ip>")
        return
    ip = context.args[0]
    await update.effective_message.reply_text(f"IP Info (stub) {ip}\nCountry: ??\nASN: ??")


@require(ADMIN)
async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = context.args[0] if context.args else "1.1.1.1"
    try:
        proc = await asyncio.create_subprocess_exec(
            "ping", "-c", "1", "-W", "2", target,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, _ = await proc.communicate()
        await update.effective_message.reply_text(f"🏓 ping {target}\n{out.decode(errors='ignore')[:300]}")
    except Exception as e:
        await update.effective_message.reply_text(f"خطا: {e}")


def register(app: Application):
    app.add_handler(CommandHandler("qr", cmd_qr))
    app.add_handler(CommandHandler("shorten", cmd_shorten))
    app.add_handler(CommandHandler("scanurl", cmd_scanurl))
    app.add_handler(CommandHandler("virusscan", cmd_virusscan))
    app.add_handler(CommandHandler("whois", cmd_whois))
    app.add_handler(CommandHandler("iplookup", cmd_iplookup))
    app.add_handler(CommandHandler("ping", cmd_ping))
