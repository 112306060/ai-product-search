"""
追蹤同一組搜尋條件（商品/定位/地區/國家）重複執行時，
每次新增的品牌家數，方便判斷這組關鍵字是不是快被搜完了，
該換個角度（不同定位詞、相近品類）繼續搜尋。
"""

import json
from datetime import datetime
from pathlib import Path

from modules.cache_manager import make_cache_key
from modules.search_profile import SearchProfile


COVERAGE_DIR = Path("data/coverage")
COVERAGE_DIR.mkdir(parents=True, exist_ok=True)

# 連續幾次新增家數都低於門檻，視為這組條件快被搜完了。
LOW_YIELD_THRESHOLD = 2
LOW_YIELD_RUN_COUNT = 3


def build_profile_signature(
    profile: SearchProfile,
) -> str:
    """
    把搜尋條件（不含國家/地區以外的細節）
    整理成穩定的簽章字串，同一組條件重複執行
    會對應到同一份歷史紀錄。
    """

    parts = [
        "products:"
        + ",".join(
            sorted(
                profile.normalized_product_keywords()
            )
        ),
        "positioning:"
        + ",".join(
            sorted(
                profile.normalized_positioning_keywords()
            )
        ),
        "regions:"
        + ",".join(
            sorted(
                profile.normalized_included_regions()
            )
        ),
        "countries:"
        + ",".join(
            sorted(
                profile.normalized_included_countries()
            )
        ),
    ]

    return "|".join(parts)


def get_coverage_path(
    profile: SearchProfile,
) -> Path:
    signature = build_profile_signature(
        profile
    )

    key = make_cache_key(signature)

    return COVERAGE_DIR / f"{key}.json"


def load_coverage_history(
    profile: SearchProfile,
) -> dict:
    path = get_coverage_path(profile)

    if not path.exists():
        return {
            "signature": (
                build_profile_signature(
                    profile
                )
            ),
            "query": profile.query,
            "runs": [],
        }

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except (OSError, json.JSONDecodeError):
        return {
            "signature": (
                build_profile_signature(
                    profile
                )
            ),
            "query": profile.query,
            "runs": [],
        }


def record_run(
    profile: SearchProfile,
    new_count: int,
    total_count: int,
) -> dict:
    """
    記錄本次執行新增與累計的品牌家數。
    """

    history = load_coverage_history(
        profile
    )

    history["query"] = profile.query

    history["runs"].append(
        {
            "date": (
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            ),
            "new_count": new_count,
            "total_count": total_count,
        }
    )

    path = get_coverage_path(profile)

    path.write_text(
        json.dumps(
            history,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return history


def summarize_coverage(
    history: dict,
) -> str:
    runs = history.get("runs", [])

    if not runs:
        return (
            "這是這組搜尋條件第一次執行，"
            "尚無歷史資料可比較。"
        )

    total = runs[-1]["total_count"]

    recent_runs = runs[
        -LOW_YIELD_RUN_COUNT:
    ]

    recent_new_counts = [
        run["new_count"]
        for run in recent_runs
    ]

    lines = [
        "這組搜尋條件累計執行 "
        f"{len(runs)} 次，"
        f"目前累計找到 {total} 家。",
    ]

    is_low_yield = (
        len(recent_runs)
        >= LOW_YIELD_RUN_COUNT
        and all(
            count <= LOW_YIELD_THRESHOLD
            for count in recent_new_counts
        )
    )

    if is_low_yield:
        lines.append(
            f"最近 {LOW_YIELD_RUN_COUNT} 次"
            "新增家數都偏低"
            f"（{recent_new_counts}），"
            "這組關鍵字可能快被搜完了，"
            "建議換個角度"
            "（不同定位詞、相近品類）"
            "再搜尋。"
        )

    else:
        lines.append(
            "最近幾次新增家數："
            f"{recent_new_counts}"
        )

    return "\n".join(lines)
