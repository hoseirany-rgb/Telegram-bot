"""Application entry point for BotGuardian Enterprise (Merged Build).

This binary glues together:
  * Enterprise handlers (`handlers/commands.py`, ``messages.py``,
    ``members.py``, ``callbacks.py``) which give us antispam/antilink/
    captcha/warn/mute/kick/ban/report/settings
  * Section pack (`handlers/router.py`, ``handlers/sections/*``) which
    adds locks, antipromo, forcesub, cleanup, autolock, advanced warnings
    (risk/rep), security modules, AI tooling, reports and the owner panel
    for a total of 15 extra admin sections and 70+ commands.

Both layers share the same `Database` from `botguardian.db`, which exposes
every table the sections need (risk / reputation / global_meta / restore)
on top of the enterprise schema.
"""
from __future__ import annotations

import logging
import sys

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from .config import settings
from .constants import ALLOWED_UPDATES
from .db import db
from .handlers.callbacks import on_callback
from .handlers.commands import (
    cmd_anti_forward,
    cmd_antilink,
    cmd_ban,
    cmd_help,
    cmd_id,
    cmd_kick,
    cmd_mute,
    cmd_pin,
    cmd_start,
    cmd_stats,
    cmd_unban,
    cmd_unmute,
)
# Note: cmd_settings/userinfo/warn/warnings/unwarn/warnlimit/welcome/captcha/
# antispam/report/dailyreport are owned by the section pack (registered
# later via `register_all`). Importing them here keeps admins discoverable
# via /start greeting but we intentionally don't re-register them.
from .handlers.members import handle_new_members
from .handlers.messages import handle_message
from .handlers.router import register_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("botguardian")


# Top-level command list shown in the bot menu. Section commands remain
# usable by users even if they aren't displayed in this list (PTB has a
# 100-entry cap, we keep the most useful ones).
COMMANDS = [
    BotCommand("start", "Start"),
    BotCommand("help", "Help"),
    BotCommand("settings", "Settings panel"),
    BotCommand("dashboard", "Group dashboard"),
    BotCommand("userinfo", "User info"),
    BotCommand("warn", "Warn a user"),
    BotCommand("warnings", "Show warnings"),
    BotCommand("unwarn", "Remove one warning"),
    BotCommand("warnlimit", "Set warning limit"),
    BotCommand("mute", "Mute a user"),
    BotCommand("unmute", "Unmute a user"),
    BotCommand("kick", "Kick a user"),
    BotCommand("ban", "Ban a user"),
    BotCommand("unban", "Unban a user"),
    BotCommand("report", "Report a replied message"),
    BotCommand("pin", "Pin replied message"),
    BotCommand("stats", "7-day stats"),
    BotCommand("dailyreport", "Today summary"),
    BotCommand("id", "Show chat/user ids"),
    BotCommand("antispam", "Toggle anti-spam"),
    BotCommand("antilink", "Toggle anti-link"),
    BotCommand("anti_forward", "Toggle anti-forward"),
    BotCommand("captcha", "Toggle join captcha"),
    BotCommand("welcome", "Toggle welcome"),
    BotCommand("lock", "Locks panel"),
    BotCommand("antipromo", "Anti-promotion"),
    BotCommand("forcesub", "Force-subscribe"),
    BotCommand("cleanup", "Auto-cleanup"),
    BotCommand("autolock", "Auto-lock"),
    BotCommand("security", "Security modules"),
    BotCommand("ai", "AI controls"),
    BotCommand("owner", "Owner panel"),
]


def build_application() -> Application:
    if not settings.bot_token:
        logger.error("BOT_TOKEN is empty. Copy .env.example to .env and set it.")
        sys.exit(2)

    app = ApplicationBuilder().token(settings.bot_token).build()

    # -------- Enterprise built-in commands (only the ones not covered
    #          by the section pack) ---------------------------------
    enterprise_cmds = [
        ("start", cmd_start), ("help", cmd_help),
        ("mute", cmd_mute), ("unmute", cmd_unmute),
        ("kick", cmd_kick), ("ban", cmd_ban), ("unban", cmd_unban),
        ("pin", cmd_pin),
        ("stats", cmd_stats), ("id", cmd_id),
        ("antilink", cmd_antilink), ("anti_forward", cmd_anti_forward),
        # /settings /userinfo /warn /warnings /unwarn /warnlimit
        # /welcome /captcha /antispam /report /dailyreport
        # are owned by the sections (richer UI, JSON panel, risk/rep).
    ]
    for cmd, handler in enterprise_cmds:
        app.add_handler(CommandHandler(cmd, handler))

    # -------- Sections pack (15 sections, 70+ commands) --------
    # `register_all` mounts every Command/Callback handler from
    # `handlers/sections/*` into the same app.
    register_all(app)

    # Captcha keyboard uses bare `cp|...` callbacks; the sections use
    # `adm|grp|lck|adp|sec|ai|al|cl|fs|own|`. Dispatcher routes both.
    app.add_handler(CallbackQueryHandler(on_callback))
    # Welcome message in PM
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members), group=1)
    # Auto-moderation (anti-spam / anti-link / anti-forward / burst / dup)
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message), group=2)
    return app


async def _post_init(app: Application) -> None:
    await db.init()
    try:
        await app.bot.set_my_commands(COMMANDS)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("set_my_commands failed: %s", exc)
    logger.info("BotGuardian Enterprise (Merged) is ready.")


async def _on_error(update: object, context) -> None:  # pragma: no cover - logged only
    logger.exception("Unhandled bot exception", exc_info=context.error)


def run() -> None:
    app = build_application()
    app.post_init = _post_init
    app.add_error_handler(_on_error)
    if settings.use_polling:
        logger.info("Starting in polling mode")
        app.run_polling(allowed_updates=ALLOWED_UPDATES, drop_pending_updates=True)
    else:
        if not settings.webhook_url:
            logger.error("WEBHOOK_URL is empty while USE_POLLING=false")
            sys.exit(2)
        logger.info("Starting in webhook mode")
        app.run_webhook(
            listen="0.0.0.0",
            port=settings.webhook_port,
            url_path=settings.bot_token,
            webhook_url=f"{settings.webhook_url.rstrip('/')}/{settings.bot_token}",
            secret_token=settings.webhook_secret or None,
            allowed_updates=ALLOWED_UPDATES,
        )


if __name__ == "__main__":
    run()
