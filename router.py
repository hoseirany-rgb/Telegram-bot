"""Aggregates registration and callback dispatch for all 15 sections.

Used by `bot.py` so that the section handlers and the enterprise handlers
share the same Application instance, the same dispatcher, and the same
unified database layer.
"""
from __future__ import annotations

import logging
from telegram.ext import Application

from .sections import (
    admin_admin,
    admin_ai,
    admin_antipromo,
    admin_autolock,
    admin_cleanup,
    admin_forcesub,
    admin_group,
    admin_locks,
    admin_members,
    admin_owner,
    admin_reports,
    admin_reports_user,
    admin_security,
    admin_tools,
    admin_warnings,
    sec_spam,
)

logger = logging.getLogger("botguardian.router")

_PREFIX_TO_MODULE = {
    "adm": admin_admin,
    "grp": admin_group,
    "lck": admin_locks,
    "adp": admin_antipromo,
    "sec": admin_security,
    "ai": admin_ai,
    "al": admin_autolock,
    "cl": admin_cleanup,
    "fs": admin_forcesub,
    "own": admin_owner,
}


def register_all(app: Application) -> None:
    """Register every section handler. Called from `bot.build_application`."""
    for sec in (
        admin_group, admin_locks, admin_antipromo, sec_spam, admin_forcesub,
        admin_cleanup, admin_autolock, admin_warnings, admin_security,
        admin_ai, admin_members, admin_reports, admin_tools,
        admin_reports_user, admin_owner, admin_admin,
    ):
        try:
            sec.register(app)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to register %s: %s", sec.__name__, exc)


async def dispatch_callback(update, context) -> bool:
    """Route callback queries that begin with a known section prefix."""
    q = update.callback_query
    if not q or not q.data:
        return False
    prefix = q.data.split("|", 1)[0]
    mod = _PREFIX_TO_MODULE.get(prefix)
    if mod is None:
        return False
    on_cb = getattr(mod, "on_callback", None)
    if on_cb is None:
        return False
    try:
        await on_cb(update, context)
        return True
    except Exception:
        logger.exception("Section callback error in %s", mod.__name__)
        try:
            await q.answer("خطا")
        except Exception:
            pass
        return True
