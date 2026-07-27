"""
app.py（Streamlit 前端）用到的非畫面邏輯：設定解析、成本指紋、
展覽新鮮度檢查、資料庫篩選、背景執行緒包裝。

跟畫面排版（st.text_area／st.button 這些呼叫）分開放在這裡，
是為了讓這支檔案可以跟其他 modules/ 一起編譯成 .pyd 交付，
app.py 本身因為 Streamlit 的執行機制必須維持明文，
但這樣它就只剩畫面排版，沒有值得保護的商業邏輯。
"""

import contextlib
import dataclasses
import hashlib
import io
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from config import SearchConfig
from modules.search_pipeline import run_search_pipeline
from modules.search_profile import SearchProfile


OUTPUT_PATH = "data/output.xlsx"

REGION_LABELS = {
    "europe": "歐洲（Europe，含非歐盟國家）",
    "european union": "歐盟（European Union）",
    "eu": "歐盟（EU，同上，另一種寫法）",
    "asia": "亞洲（Asia）",
    "north america": "北美（North America）",
}

NO_REGION_LABEL = "不限制地區（全球）"

SOURCE_OPTION_BOTH = "Google 搜尋 + 展覽名錄（預設，兩者都要）"
SOURCE_OPTION_GOOGLE_ONLY = "只用 Google 搜尋"
SOURCE_OPTION_EXHIBITION_ONLY = (
    "只用展覽名錄（Asia／North America／Bologna）"
)
SOURCE_OPTIONS = [
    SOURCE_OPTION_BOTH,
    SOURCE_OPTION_GOOGLE_ONLY,
    SOURCE_OPTION_EXHIBITION_ONLY,
]

# 超過幾天沒同步就提醒使用者——展覽官方名錄不是即時抓取，
# 而是本地快取檔，久了可能還停留在舊一屆的資料。
EXHIBITION_STALE_DAYS = 30

# 預估用量超過這裡任一項門檻，執行前必須額外勾選確認，
# 避免手滑改錯設定（例如目標家數多打一個零）卻沒注意到，
# 執行到一半才發現用量遠超預期。門檻是經驗值，
# 可以依實際預算調整。
COST_CONFIRMATION_SERPAPI_CALLS_THRESHOLD = 150
COST_CONFIRMATION_USD_THRESHOLD = 1.0

BOLOGNA_CATALOG_PATH = (
    "data/exhibitions/cosmoprof_bologna_2026.json"
)
NORTH_AMERICA_METADATA_PATH = (
    "data/exhibitions/"
    "cosmoprof_north_america_2026_metadata.json"
)


def get_exhibition_source_freshness() -> list[dict]:
    """
    取得三大展覽來源各自的資料新鮮度。

    Asia 是每次執行都即時打官方 API，沒有「過期」的問題；
    Bologna／North America 是本地快取檔，需要人工執行對應的
    sync 腳本才會更新，這裡回報快取檔的同步時間，
    太久沒同步就提醒使用者。
    """

    now = datetime.now(timezone.utc)
    sources = []

    sources.append(
        {
            "name": "Cosmoprof Asia",
            "is_live": True,
            "synced_at": None,
            "days_old": None,
            "note": "每次執行都即時查詢官方 API，不需要同步",
        }
    )

    bologna_path = Path(
        BOLOGNA_CATALOG_PATH
    )

    if bologna_path.exists():
        synced_at = datetime.fromtimestamp(
            bologna_path.stat().st_mtime,
            tz=timezone.utc,
        )
        days_old = (
            now - synced_at
        ).days

        sources.append(
            {
                "name": (
                    "Cosmoprof Worldwide Bologna"
                ),
                "is_live": False,
                "synced_at": synced_at,
                "days_old": days_old,
                "note": (
                    "本地快取檔，需執行 "
                    "sync_bologna_catalog.py + "
                    "update_bologna_details.py 更新"
                ),
            }
        )

    else:
        sources.append(
            {
                "name": (
                    "Cosmoprof Worldwide Bologna"
                ),
                "is_live": False,
                "synced_at": None,
                "days_old": None,
                "note": "找不到本地快取檔，需先執行同步腳本",
            }
        )

    north_america_path = Path(
        NORTH_AMERICA_METADATA_PATH
    )

    if north_america_path.exists():
        try:
            metadata = json.loads(
                north_america_path.read_text(
                    encoding="utf-8"
                )
            )

            synced_at_text = metadata.get(
                "synced_at"
            )

            synced_at = (
                datetime.fromisoformat(
                    synced_at_text
                )
                if synced_at_text
                else None
            )

            days_old = (
                (now - synced_at).days
                if synced_at
                else None
            )

        except Exception:
            synced_at = None
            days_old = None

        sources.append(
            {
                "name": (
                    "Cosmoprof North America"
                ),
                "is_live": False,
                "synced_at": synced_at,
                "days_old": days_old,
                "note": (
                    "本地快取檔，需執行 "
                    "sync_cpna_catalog.py 更新"
                ),
            }
        )

    else:
        sources.append(
            {
                "name": (
                    "Cosmoprof North America"
                ),
                "is_live": False,
                "synced_at": None,
                "days_old": None,
                "note": "找不到本地快取檔，需先執行同步腳本",
            }
        )

    return sources


def parse_keyword_list(text: str) -> list[str]:
    if not text:
        return []

    return [
        keyword.strip()
        for keyword in text.split(",")
        if keyword.strip()
    ]


def contains_non_english_keyword(text: str) -> bool:
    """
    偵測商品詞／定位詞是否含有非英文字元。

    這兩個欄位會直接拿去跟國外品牌網站的英文內容做
    逐字比對，也是翻譯成其他語言的翻譯來源，
    用中文等非英文字輸入幾乎不會比對到任何候選，
    容易讓使用者誤以為系統壞掉、其實只是搜尋不到結果。
    """

    return bool(re.search(r"[^\x00-\x7F]", text))


def build_search_profile() -> SearchProfile:
    return SearchProfile(
        query=st.session_state.get(
            "query_text", ""
        ),
        product_keywords=parse_keyword_list(
            st.session_state.get(
                "product_keywords_text", ""
            )
        ),
        positioning_keywords=parse_keyword_list(
            st.session_state.get(
                "positioning_keywords_text", ""
            )
        ),
        excluded_keywords=parse_keyword_list(
            st.session_state.get(
                "excluded_keywords_text", ""
            )
        ),
        included_countries=parse_keyword_list(
            st.session_state.get(
                "included_countries_text", ""
            )
        ),
        excluded_countries=parse_keyword_list(
            st.session_state.get(
                "excluded_countries_text", ""
            )
        ),
        included_regions=(
            []
            if NO_REGION_LABEL
            in st.session_state.get(
                "selected_regions", []
            )
            else st.session_state.get(
                "selected_regions", []
            )
        ),
    )


def build_search_config() -> SearchConfig:
    selected_source = st.session_state.get(
        "selected_source", SOURCE_OPTION_BOTH
    )

    return SearchConfig(
        target_count=st.session_state.get(
            "target_count", 10
        ),
        enable_google_search=(
            selected_source
            != SOURCE_OPTION_EXHIBITION_ONLY
        ),
        enable_exhibition_search=(
            selected_source
            != SOURCE_OPTION_GOOGLE_ONLY
        ),
        test_mode=st.session_state.get(
            "test_mode", False
        ),
        check_taiwan_distributor=(
            st.session_state.get(
                "check_taiwan_distributor",
                True,
            )
        ),
        force_refresh_taiwan=(
            st.session_state.get(
                "force_refresh_taiwan",
                False,
            )
        ),
        force_refresh_brands=(
            st.session_state.get(
                "force_refresh_brands",
                False,
            )
        ),
        enable_deep_pagination=(
            st.session_state.get(
                "enable_deep_pagination",
                False,
            )
        ),
        show_cost_estimate=False,
        require_run_confirmation=False,
        require_language_switch_confirmation=False,
        output_path=OUTPUT_PATH,
    )


def compute_run_fingerprint(
    config: SearchConfig,
    profile: SearchProfile,
) -> str:
    """
    把這次執行會用到的所有設定做成一組指紋，
    用來判斷「上次估算用量時的設定」是否還等於現在的設定。

    只要使用者改了任何欄位（目標家數、地區、關鍵字……），
    指紋就會跟著變，逼使用者重新按一次「估算用量」才能
    開始搜尋，避免拿一份跟目前設定對不上的舊預估數字，
    誤以為這次執行的用量跟預估的一樣。
    """
    payload = {
        "config": dataclasses.asdict(config),
        "profile": dataclasses.asdict(profile),
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def run_pipeline_in_background(
    config,
    profile,
    progress_state: dict,
    cancel_event: threading.Event,
    result_state: dict,
) -> None:
    """
    在背景執行緒執行搜尋，讓主執行緒可以持續
    更新進度條、回應「停止搜尋」按鈕。

    progress_state／result_state 是簡單的 dict，
    背景執行緒寫入、主執行緒讀取——CPython 的 GIL
    讓單一 key 的讀寫足夠安全，不需要額外上鎖。
    """

    log_buffer = io.StringIO()

    def progress_callback(info: dict) -> None:
        progress_state.update(info)

    def cancel_check() -> bool:
        return cancel_event.is_set()

    try:
        with contextlib.redirect_stdout(
            log_buffer
        ):
            summary = run_search_pipeline(
                config,
                profile,
                progress_callback=(
                    progress_callback
                ),
                cancel_check=cancel_check,
            )

        result_state["summary"] = summary
        result_state["error"] = None

    except Exception as error:
        result_state["summary"] = None
        result_state["error"] = str(error)

    finally:
        result_state["log"] = (
            log_buffer.getvalue()
        )
        result_state["done"] = True


def filter_database_dataframe(
    dataframe: pd.DataFrame,
    *,
    search_name_text: str = "",
    selected_classification: str = "全部",
    selected_taiwan_status: str = "全部",
    selected_country: str = "全部",
    company_search_text: str = "",
) -> pd.DataFrame:
    """
    套用「資料庫瀏覽」分頁的五個篩選條件，回傳篩選後的結果。

    抽成獨立、不依賴 Streamlit 的純函式，方便直接測試，
    不用透過真的 Excel 檔案或畫面互動。
    """
    filtered_dataframe = dataframe.copy()

    if search_name_text.strip():
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["搜尋名稱"]
            .astype(str)
            .str.contains(
                search_name_text.strip(),
                case=False,
                na=False,
            )
        ]

    if selected_classification != "全部":
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["AI分類"]
            == selected_classification
        ]

    if selected_taiwan_status != "全部":
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["台灣代理狀態"]
            == selected_taiwan_status
        ]

    if selected_country != "全部":
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["國家"]
            == selected_country
        ]

    if company_search_text.strip():
        filtered_dataframe = filtered_dataframe[
            filtered_dataframe["公司名稱"]
            .astype(str)
            .str.contains(
                company_search_text.strip(),
                case=False,
                na=False,
            )
        ]

    return filtered_dataframe
