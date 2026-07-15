import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Windows 路徑長度有上限，像涵蓋率追蹤這種把一長串
# 關鍵字（含同義詞展開後）組成簽章字串的用法，
# 清理後可能還是太長，超過上限會直接寫入失敗。
MAX_CACHE_KEY_LENGTH = 100


def make_cache_key(value: str) -> str:
    """
    將品牌名稱轉成安全的快取檔名。

    清理後太長時會截斷並補上內容雜湊，
    避免超出 Windows 路徑長度上限，
    同時仍保留足夠的辨識度與唯一性。
    """
    cleaned = value.strip().lower()
    cleaned = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", cleaned)
    cleaned = cleaned.strip("_")

    if not cleaned:
        return "unknown"

    if len(cleaned) > MAX_CACHE_KEY_LENGTH:
        digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:10]
        truncated_length = MAX_CACHE_KEY_LENGTH - len(digest) - 1
        cleaned = cleaned[:truncated_length] + "_" + digest

    return cleaned


def get_cache_path(cache_type: str, cache_key: str) -> Path:
    folder = CACHE_DIR / cache_type
    folder.mkdir(parents=True, exist_ok=True)

    return folder / f"{make_cache_key(cache_key)}.json"


def load_cache(
    cache_type: str,
    cache_key: str,
    expire_days: int,
) -> dict[str, Any] | None:
    """
    讀取尚未過期的快取。
    過期、損壞或不存在時回傳 None。
    """
    cache_path = get_cache_path(cache_type, cache_key)

    if not cache_path.exists():
        return None

    try:
        with cache_path.open("r", encoding="utf-8") as file:
            cached = json.load(file)

        checked_at_text = cached.get("checked_at")
        data = cached.get("data")

        if not checked_at_text or not isinstance(data, dict):
            return None

        checked_at = datetime.fromisoformat(checked_at_text)
        expires_at = checked_at + timedelta(days=expire_days)

        if datetime.now() >= expires_at:
            print(f"[CACHE EXPIRED] {cache_type}: {cache_key}")
            return None

        print(f"[CACHE HIT] {cache_type}: {cache_key}")
        return data

    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"[CACHE READ FAILED] {cache_path}: {exc}")
        return None


def save_cache(
    cache_type: str,
    cache_key: str,
    data: dict[str, Any],
) -> None:
    """
    將結果及查詢時間寫入 JSON 快取。
    """
    cache_path = get_cache_path(cache_type, cache_key)

    payload = {
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "data": data,
    }

    try:
        with cache_path.open("w", encoding="utf-8") as file:
            json.dump(
                payload,
                file,
                ensure_ascii=False,
                indent=2,
            )

        print(f"[CACHE SAVED] {cache_type}: {cache_key}")

    except OSError as exc:
        print(f"[CACHE WRITE FAILED] {cache_path}: {exc}")