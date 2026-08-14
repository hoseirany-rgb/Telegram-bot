"""Permission tiers used across BotGuardian sections.

Public      : Any chat member
Special     : VIP / Whitelist users (exempt from locks/filters)
Admin       : Group creator or any administrator
Owner       : The bot's OWNER_IDS env values (super-admin)
"""
from __future__ import annotations

OWNER = "OWNER"
ADMIN = "ADMIN"
SPECIAL = "SPECIAL"
PUBLIC = "PUBLIC"

__all__ = ["OWNER", "ADMIN", "SPECIAL", "PUBLIC"]
