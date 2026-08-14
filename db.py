"""Unified DB layer for BotGuardian Enterprise.

This module merges the original enterprise `Database` (settings/warnings/
stats/audit) with the section extensions stored in `handlers/db_ext.py`
(extra settings + risk/reputation/global_meta + restore/copy helpers).

All section handlers continue to use `xdb` from `handlers/db_ext.py`; here
we expose everything under both names so legacy import paths keep working.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import aiosqlite

from .config import settings
from .constants import DEFAULT_WARN_LIMIT

# ---------------------------------------------------------------------------
# Defaults and allowed-stat columns (merged)
# ---------------------------------------------------------------------------

ALLOWED_STAT_COLUMNS = {
    "messages", "links", "warnings", "bans", "kicks", "mutes",
    "deletes", "reports", "joins", "scans", "risk_hits",
}

DEFAULT_GROUP_SETTINGS: dict[str, Any] = {
    # original enterprise flags
    "enabled": True,
    "antispam": True,
    "antilink": False,
    "anti_forward": False,
    "captcha": False,
    "welcome": True,
    "warn_limit": DEFAULT_WARN_LIMIT,
    "action_on_limit": "kick",
    "burst_limit": 7,
    "burst_window": 8,
    "duplicate_limit": 3,
    "duplicate_window": 90,
    "max_links": 1,
    "antispam_action": "kick",
    # locks
    "lock_link": False, "lock_hyperlink": False, "lock_bot": True,
    "lock_channel_post": False, "lock_forward": False, "lock_username": False,
    "lock_lang": False, "lock_font": False, "lock_english": False,
    "lock_video": False, "lock_video_note": False, "lock_gif": False,
    "lock_story": False, "lock_phone": False, "lock_tag": False,
    "lock_inline": False, "lock_msg_pv": False,
    # antipromo
    "ad_name_check": True, "ad_bio_check": True, "ad_severity": 2,
    "ad_limit": 3, "ad_auto_purge": True, "ad_purge_seconds": 60,
    "ad_hidden_link": True, "ad_short_link": True, "ad_spam_wave": True,
    "ad_raid": True, "ad_join_attack": True, "ad_mention_spam": True,
    "ad_emoji_spam": True, "ad_flood": True, "ad_bot_attack": True,
    "ad_fake_account": True,
    # antispam extended
    "antispam_delete": True, "antispam_sensitivity": 2,
    "antispam_flood_delete": True, "antispam_flood_window": 8,
    "antispam_flood_sensitivity": 2, "antispam_duplicate": True,
    "antispam_similar": True, "antispam_auto_del": True,
    # forcesub
    "forcesub_enabled": False, "forcesub_msg_allowed": 3,
    "forcesub_purge_secs": 600, "forcesub_ad_required": False,
    "forcesub_ad_count": 0, "forcesub_ad_mode": "soft",
    "forcesub_channels": [], "forcesub_groups": [],
    # cleanup
    "cleanup_seconds": False, "cleanup_hourly": False,
    "cleanup_remaining_announce": True, "cleanup_schedule": None,
    "cleanup_daily": False, "cleanup_weekly": False, "cleanup_monthly": False,
    "cleanup_files": False, "cleanup_gifs": False, "cleanup_photos": False,
    "cleanup_videos": False, "cleanup_voice": False, "cleanup_stickers": False,
    "cleanup_at": "00:00",
    # autolock
    "autolock_enabled": False, "autolock_mode": "soft",
    "autolock_time": "22:00-06:00", "autolock_status": False,
    "autolock_open_auto": True, "autolock_days": "0,1,2,3,4,5,6",
    "autolock_holiday": False, "autolock_events": "",
    # security
    "sec_anti_raid": False, "sec_anti_nuke": False, "sec_anti_bot": False,
    "sec_anti_clone": False, "sec_anti_fake": False, "sec_anti_scam": False,
    "sec_anti_phishing": False, "sec_anti_crypto": False, "sec_anti_porn": False,
    "sec_anti_violence": False, "sec_anti_malware": False, "sec_anti_proxy": False,
    "sec_anti_vpn": False, "sec_anti_session_hijack": False, "sec_level": 1,
    # ai
    "ai_msg_scan": False, "ai_link_scan": False, "ai_user_scan": False,
    "ai_behavior_scan": False, "ai_risk_scan": False, "ai_ad_detect": False,
    "ai_scam_detect": False, "ai_summary": False, "ai_suggest": False,
    "ai_enabled": False,
    # misc
    "vip_users": [],
    "blacklist": {"users": [], "words": []},
    "whitelist": {"users": [], "words": []},
    "owner_id": None,
    "autolock_open_at": None,
    "lang": "fa",
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS group_settings (
    chat_id INTEGER PRIMARY KEY,
    settings TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS warnings (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    count INTEGER NOT NULL DEFAULT 0,
    reasons TEXT NOT NULL DEFAULT '[]',
    updated_at REAL NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS stats (
    chat_id INTEGER NOT NULL,
    day TEXT NOT NULL,
    messages INTEGER NOT NULL DEFAULT 0,
    links INTEGER NOT NULL DEFAULT 0,
    warnings INTEGER NOT NULL DEFAULT 0,
    bans INTEGER NOT NULL DEFAULT 0,
    kicks INTEGER NOT NULL DEFAULT 0,
    mutes INTEGER NOT NULL DEFAULT 0,
    deletes INTEGER NOT NULL DEFAULT 0,
    reports INTEGER NOT NULL DEFAULT 0,
    joins INTEGER NOT NULL DEFAULT 0,
    scans INTEGER NOT NULL DEFAULT 0,
    risk_hits INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, day)
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,
    target_id INTEGER,
    action TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_chat_idx ON audit(chat_id, created_at);
CREATE TABLE IF NOT EXISTS risk (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    last_event INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS reputation (
    chat_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    score INTEGER NOT NULL DEFAULT 100,
    updated_at REAL NOT NULL,
    PRIMARY KEY (chat_id, user_id)
);
CREATE TABLE IF NOT EXISTS global_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

STAT_COLUMNS_CSV = (
    "messages, links, warnings, bans, kicks, mutes, deletes, reports, "
    "joins, scans, risk_hits"
)


class Database:
    """Async wrapper around the merged SQLite schema."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- init --
    async def init(self) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.executescript(SCHEMA)
            await conn.commit()

    # ------------------------------------------------------- group settings --
    async def get_group_settings(self, chat_id: int) -> dict[str, Any]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT settings FROM group_settings WHERE chat_id=?",
                (chat_id,),
            )
            row = await cur.fetchone()
        merged = dict(DEFAULT_GROUP_SETTINGS)
        if row:
            try:
                merged.update(json.loads(row["settings"] or "{}"))
            except Exception:
                pass
        return merged

    async def update_group_settings(self, chat_id: int, **patch: Any) -> dict[str, Any]:
        current = await self.get_group_settings(chat_id)
        for k, v in patch.items():
            if v is None:
                continue
            current[k] = v
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO group_settings(chat_id, settings) VALUES(?, ?)",
                (chat_id, json.dumps(current, ensure_ascii=False)),
            )
            await conn.commit()
        return current

    async def dump_group(self, chat_id: int) -> dict[str, Any]:
        return await self.get_group_settings(chat_id)

    async def restore_group(self, chat_id: int, blob: dict[str, Any]) -> None:
        cleaned: dict[str, Any] = {
            k: v for k, v in blob.items() if k in DEFAULT_GROUP_SETTINGS
        }
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO group_settings(chat_id, settings) VALUES(?, ?)",
                (chat_id, json.dumps(cleaned, ensure_ascii=False)),
            )
            await conn.commit()

    async def reset_group(self, chat_id: int) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO group_settings(chat_id, settings) VALUES(?, ?)",
                (chat_id, json.dumps({}, ensure_ascii=False)),
            )
            await conn.commit()

    async def copy_group_to(self, src: int, dst: int) -> None:
        blob = await self.get_group_settings(src)
        await self.restore_group(dst, blob)

    # ------------------------------------------------------------ warnings --
    async def add_warning(self, chat_id: int, user_id: int, reason: str) -> int:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT count, reasons FROM warnings WHERE chat_id=? AND user_id=?",
                (chat_id, user_id),
            )
            row = await cur.fetchone()
            count = (int(row["count"]) if row else 0) + 1
            reasons = json.loads(row["reasons"] if row else "[]")
            reasons.append(reason)
            await conn.execute(
                "INSERT OR REPLACE INTO warnings(chat_id, user_id, count, reasons, updated_at) "
                "VALUES(?, ?, ?, ?, ?)",
                (
                    chat_id, user_id, count,
                    json.dumps(reasons[-10:], ensure_ascii=False),
                    time.time(),
                ),
            )
            await conn.commit()
        return count

    async def set_warning_count(
        self, chat_id: int, user_id: int, count: int, reasons: list[str]
    ) -> None:
        async with aiosqlite.connect(self.path) as conn:
            if count <= 0:
                await conn.execute(
                    "DELETE FROM warnings WHERE chat_id=? AND user_id=?",
                    (chat_id, user_id),
                )
            else:
                await conn.execute(
                    "INSERT OR REPLACE INTO warnings(chat_id, user_id, count, reasons, updated_at) "
                    "VALUES(?, ?, ?, ?, ?)",
                    (
                        chat_id, user_id, count,
                        json.dumps(reasons[-10:], ensure_ascii=False),
                        time.time(),
                    ),
                )
            await conn.commit()

    async def reset_warnings(self, chat_id: int, user_id: int) -> None:
        await self.set_warning_count(chat_id, user_id, 0, [])

    async def set_warning_reset(self, chat_id: int, user_id: int) -> None:
        """Section-style reset (used by `admin_admin` callback)."""
        await self.reset_warnings(chat_id, user_id)

    async def global_inc_warn(
        self, chat_id: int, user_id: int, reason: str
    ) -> int:
        """Section-style increment from a callback button."""
        return await self.add_warning(chat_id, user_id, reason)

    async def get_warnings(self, chat_id: int, user_id: int) -> tuple[int, list[str]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT count, reasons FROM warnings WHERE chat_id=? AND user_id=?",
                (chat_id, user_id),
            )
            row = await cur.fetchone()
        if not row:
            return 0, []
        return int(row["count"]), json.loads(row["reasons"] or "[]")

    async def group_warnings_get(
        self, chat_id: int, user_id: int
    ) -> tuple[int, list[str]]:
        """Alias used by some section handlers."""
        return await self.get_warnings(chat_id, user_id)

    # --------------------------------------------------------------- stats --
    async def incr_stat(self, chat_id: int, column: str, delta: int = 1) -> None:
        if column not in ALLOWED_STAT_COLUMNS:
            raise ValueError(f"Unsupported stat column: {column}")
        day = time.strftime("%Y-%m-%d")
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                f"INSERT INTO stats(chat_id, day, {STAT_COLUMNS_CSV}) "
                f"VALUES(?, ?, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0) "
                f"ON CONFLICT(chat_id, day) DO NOTHING",
                (chat_id, day),
            )
            await conn.execute(
                f"UPDATE stats SET {column}={column}+? WHERE chat_id=? AND day=?",
                (delta, chat_id, day),
            )
            await conn.commit()

    async def get_stats(self, chat_id: int, days: int = 7) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                f"SELECT day, {STAT_COLUMNS_CSV} FROM stats "
                f"WHERE chat_id=? ORDER BY day DESC LIMIT ?",
                (chat_id, days),
            )
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def stats(self, chat_id: int, days: int = 1) -> list[dict[str, Any]]:
        """Alias used by section handlers."""
        return await self.get_stats(chat_id, days)

    # --------------------------------------------------------------- audit --
    async def log(
        self,
        chat_id: int,
        actor_id: int,
        action: str,
        target_id: int | None = None,
        **payload: Any,
    ) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT INTO audit(chat_id, actor_id, target_id, action, payload, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (
                    chat_id, actor_id, target_id, action,
                    json.dumps(payload, ensure_ascii=False), time.time(),
                ),
            )
            await conn.commit()

    async def recent_audit(self, chat_id: int, limit: int = 20) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT id, actor_id, target_id, action, payload, created_at "
                "FROM audit WHERE chat_id=? ORDER BY id DESC LIMIT ?",
                (chat_id, limit),
            )
            rows = await cur.fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                d["payload"] = json.loads(d["payload"] or "{}")
            except Exception:
                d["payload"] = {}
            out.append(d)
        return out

    async def admin_actions_24h(self, chat_id: int) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT actor_id, action, COUNT(*) AS c "
                "FROM audit WHERE chat_id=? AND created_at>=? "
                "GROUP BY actor_id, action ORDER BY c DESC",
                (chat_id, time.time() - 86400),
            )
            return [dict(r) for r in await cur.fetchall()]

    # ------------------------------------------------------------- risk --
    async def risk_add(self, chat_id: int, user_id: int, points: int) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT INTO risk(chat_id, user_id, points, last_event) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(chat_id, user_id) DO UPDATE SET "
                "points=points+excluded.points, last_event=excluded.last_event",
                (chat_id, user_id, points, time.time()),
            )
            await conn.commit()

    async def risk_get(self, chat_id: int, user_id: int) -> dict[str, Any]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT points, last_event FROM risk WHERE chat_id=? AND user_id=?",
                (chat_id, user_id),
            )
            r = await cur.fetchone()
        return dict(r) if r else {"points": 0, "last_event": 0}

    # -------------------------------------------------------- reputation --
    async def reputation_set(self, chat_id: int, user_id: int, score: int) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO reputation(chat_id, user_id, score, updated_at) "
                "VALUES(?,?,?,?)",
                (chat_id, user_id, score, time.time()),
            )
            await conn.commit()

    async def reputation_get(self, chat_id: int, user_id: int) -> dict[str, Any]:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT score, updated_at FROM reputation WHERE chat_id=? AND user_id=?",
                (chat_id, user_id),
            )
            r = await cur.fetchone()
        return dict(r) if r else {"score": 100, "updated_at": 0}

    # ----------------------------------------------------------- global_kv --
    async def global_get(self, key: str, default: Any = None) -> Any:
        async with aiosqlite.connect(self.path) as conn:
            conn.row_factory = aiosqlite.Row
            cur = await conn.execute(
                "SELECT value FROM global_meta WHERE key=?", (key,)
            )
            r = await cur.fetchone()
        if not r:
            return default
        try:
            return json.loads(r["value"])
        except Exception:
            return default

    async def global_set(self, key: str, value: Any) -> None:
        async with aiosqlite.connect(self.path) as conn:
            await conn.execute(
                "INSERT OR REPLACE INTO global_meta(key, value) VALUES(?,?)",
                (key, json.dumps(value, ensure_ascii=False)),
            )
            await conn.commit()


db = Database(settings.db_path)
