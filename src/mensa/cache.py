import json
import time
from pathlib import Path

from pathvalidate import sanitize_filename
from platformdirs import user_cache_dir

from .constants import APP_NAME, CANTEENS_TTL

_CACHE_DIR = Path(user_cache_dir(APP_NAME))
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _path(key: str) -> Path:
    return _CACHE_DIR / f"{sanitize_filename(key)}.json"


def get(key: str, ttl: int = CANTEENS_TTL):
    p = _path(key)
    if not p.exists():
        return None
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - payload.get("_cached_at", 0) > ttl:
        return None
    return payload.get("data")


def set(key: str, value) -> None:
    p = _path(key)
    payload = {"_cached_at": time.time(), "data": value}
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def clear() -> int:
    count = 0
    for f in _CACHE_DIR.glob("*.json"):
        f.unlink()
        count += 1
    return count


def info() -> dict:
    files = list(_CACHE_DIR.glob("*.json"))
    return {
        "cache_dir": str(_CACHE_DIR),
        "num_entries": len(files),
        "total_bytes": sum(f.stat().st_size for f in files),
    }
