"""
記錄每一次搜尋執行過的條件與結果，讓使用者事後可以回頭查
「上次搜了什麼、找到多少家」——跟 coverage_tracker.py 不同，
這裡是給人瀏覽的完整執行清單，不是拿來判斷單一條件是否
搜到飽和。

一行一筆 JSON（append-only），寫入失敗只印警告，
不讓搜尋本身因為歷史紀錄寫不進去而失敗。
"""

import json
from datetime import datetime
from pathlib import Path


HISTORY_PATH = Path("data/search_history.jsonl")


def build_history_entry(
    profile,
    config,
    summary: dict,
) -> dict:
    return {
        "時間": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "搜尋名稱": profile.query,
        "商品詞": list(profile.product_keywords),
        "定位詞": list(profile.positioning_keywords),
        "排除詞": list(profile.excluded_keywords),
        "地區": list(profile.included_regions),
        "包含國家": list(profile.included_countries),
        "排除國家": list(profile.excluded_countries),
        "目標家數": config.target_count,
        "Google搜尋": config.enable_google_search,
        "展覽名錄": config.enable_exhibition_search,
        "測試模式": config.test_mode,
        "查台灣代理": config.check_taiwan_distributor,
        "本次找到": summary.get("本次找到", 0),
        "新增品牌": summary.get("新增品牌", 0),
        "更新品牌": summary.get("更新品牌", 0),
        "鎖定跳過": summary.get("鎖定跳過", 0),
        "資料庫總數": summary.get("資料庫總數", 0),
        "中止": bool(summary.get("cancelled", False)),
    }


def record_search_run(
    profile,
    config,
    summary: dict,
) -> None:
    entry = build_history_entry(
        profile, config, summary
    )

    try:
        HISTORY_PATH.parent.mkdir(
            parents=True, exist_ok=True
        )

        with HISTORY_PATH.open(
            "a", encoding="utf-8"
        ) as history_file:
            history_file.write(
                json.dumps(
                    entry, ensure_ascii=False
                )
                + "\n"
            )

    except OSError as error:
        print(
            "[SEARCH HISTORY WRITE FAILED] "
            f"{error}"
        )


def load_search_history() -> list[dict]:
    """
    讀取所有搜尋歷史紀錄，時間新到舊排序。

    毀損的單行資料略過，不中斷其餘紀錄的讀取。
    """
    if not HISTORY_PATH.exists():
        return []

    entries = []

    for line in HISTORY_PATH.read_text(
        encoding="utf-8"
    ).splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            entries.append(json.loads(line))

        except json.JSONDecodeError:
            continue

    entries.reverse()

    return entries
