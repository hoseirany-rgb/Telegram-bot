from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_ids(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    out: list[int] = []
    for chunk in value.replace(",", " ").split():
        try:
            out.append(int(chunk))
        except ValueError:
            continue
    return tuple(out)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    owner_ids: tuple[int, ...]
    use_polling: bool
    webhook_url: str
    webhook_port: int
    webhook_secret: str
    db_path: Path
    default_lang: str


def load_settings() -> Settings:
    base_dir = Path(__file__).resolve().parent.parent
    db_path = Path(os.getenv("DB_PATH", str(base_dir / "data" / "botguardian.db")))
    if not db_path.is_absolute():
        db_path = (base_dir / db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return Settings(
        bot_token=os.getenv("BOT_TOKEN", "").strip(),
        owner_ids=_to_ids(os.getenv("OWNER_IDS")),
        use_polling=_to_bool(os.getenv("USE_POLLING"), True),
        webhook_url=os.getenv("WEBHOOK_URL", "").strip(),
        webhook_port=int(os.getenv("WEBHOOK_PORT", "8443") or 8443),
        webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip(),
        db_path=db_path,
        default_lang=(os.getenv("DEFAULT_LANG", "fa").strip().lower() or "fa"),
    )


settings = load_settings()
