"""
AI 海外品牌搜尋系統 - Streamlit 前端。

啟動方式：
    streamlit run app.py
或直接雙擊 run_frontend.bat。
"""

import contextlib
import dataclasses
import hashlib
import io
import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from config import SearchConfig
from modules.search_profile import (
    REGION_COUNTRIES,
    SearchProfile,
)
from modules.search_pipeline import (
    match_existing_database_records,
    run_search_pipeline,
)
from modules.search_cost_estimator import (
    estimate_search_cost,
)
from modules.excel_exporter import (
    export_dataframe_to_excel_bytes,
    load_existing_records,
)


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


def render_exhibition_freshness() -> None:
    freshness = (
        get_exhibition_source_freshness()
    )

    lines = []
    has_stale = False

    for source in freshness:
        if source["is_live"]:
            lines.append(
                f"- **{source['name']}**："
                "即時查詢，一律最新"
            )
            continue

        if source["synced_at"] is None:
            lines.append(
                f"- **{source['name']}**："
                "⚠️ 找不到本地快取檔，"
                f"{source['note']}"
            )
            has_stale = True
            continue

        days_old = source["days_old"]
        synced_date_text = source[
            "synced_at"
        ].strftime("%Y-%m-%d")

        is_stale = (
            days_old
            >= EXHIBITION_STALE_DAYS
        )

        if is_stale:
            has_stale = True

        warning_mark = (
            "⚠️ " if is_stale else ""
        )

        lines.append(
            f"- **{source['name']}**："
            f"{warning_mark}上次同步 "
            f"{synced_date_text}"
            f"（{days_old} 天前）"
        )

    with st.expander(
        "📅 展覽資料來源新鮮度"
        + (
            "（有來源已超過 "
            f"{EXHIBITION_STALE_DAYS} 天沒同步）"
            if has_stale
            else ""
        ),
        expanded=has_stale,
    ):
        st.markdown(
            "\n".join(lines)
        )

        st.caption(
            "Bologna／North America 是本地快取檔，"
            "不會自動更新，需要人工執行對應的 sync 腳本"
            "（見專案根目錄 sync_bologna_catalog.py／"
            "update_bologna_details.py／"
            "sync_cpna_catalog.py）。"
        )


st.set_page_config(
    page_title="AI 海外品牌搜尋系統",
    layout="wide",
)


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


@st.cache_resource
def get_shared_run_state() -> dict:
    """
    跨瀏覽器連線／重新整理都共用的搜尋狀態。

    st.session_state 只綁定單一次瀏覽器連線，使用者不小心
    重新整理頁面就會產生全新的 session_state、找不到原本
    搜尋的執行緒與進度。st.cache_resource 建立的物件則是
    綁在後端服務本身（同一個 Python process），只要伺服器
    沒有重啟，不管重新整理幾次、換哪個瀏覽器分頁開啟，
    都能接回同一筆正在執行（或剛執行完）的搜尋狀態。
    """

    return {
        "running": False,
        "thread": None,
        "progress": {},
        "cancel_event": None,
        "result": None,
    }


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


def render_cost_estimate(estimate: dict) -> None:
    minutes = (
        estimate["total_seconds_estimate"] / 60
    )

    columns = st.columns(4)

    columns[0].metric(
        "預估 SerpAPI 查詢次數",
        f"{estimate['serpapi_calls_estimate']} 次",
    )

    columns[1].metric(
        "預估通過 AI 篩選家數",
        f"約 {estimate['accepted_total_estimate']} 家",
    )

    columns[2].metric(
        "預估 OpenAI 費用",
        f"US${estimate['openai_cost_usd_estimate']:.3f}",
    )

    columns[3].metric(
        "預估耗時",
        f"約 {minutes:.1f} 分鐘",
    )

    st.caption(
        "展覽候選符合數："
        f"Asia {estimate['asia_matched_count']} 家 / "
        "North America "
        f"{estimate['north_america_matched_count']} 家 / "
        f"Bologna {estimate['bologna_matched_count']} 家"
    )

    if estimate.get("live_fetch_error"):
        st.warning(
            "部分官方名錄查詢失敗，以上數字可能不準確："
            + estimate["live_fetch_error"]
        )


def render_search_tab() -> None:
    st.subheader("1. 設定搜尋條件")

    st.text_input(
        "這次搜尋的名稱／描述（給自己看的，不影響搜尋邏輯）",
        value=st.session_state.get(
            "query_text", "歐洲有機天然洗髮精"
        ),
        key="query_text",
    )

    col_left, col_right = st.columns(2)

    with col_left:
        st.text_area(
            "商品詞（請輸入英文，用逗號分隔，例如：shampoo, conditioner, hair care）",
            value=st.session_state.get(
                "product_keywords_text",
                "shampoo, conditioner, hair care, scalp care",
            ),
            key="product_keywords_text",
            height=80,
            help=(
                "這裡一定要用英文：系統會拿這些詞直接比對國外品牌"
                "網站上的英文內容，也會用來翻譯成其他語言去搜尋。"
                "輸入中文（例如「手工皂」）幾乎不會比對到任何結果。"
                "想找手工皂，請輸入 soap, handmade soap 這類英文詞。"
            ),
        )

        if contains_non_english_keyword(
            st.session_state.get(
                "product_keywords_text", ""
            )
        ):
            st.warning(
                "偵測到商品詞含有非英文字（例如中文）。"
                "商品詞必須是英文，否則系統幾乎找不到任何符合結果——"
                "請改成英文詞，例如把「手工皂」改成 soap, handmade soap。"
            )

        st.text_area(
            "排除詞（選填，請輸入英文，例如：nail, packaging）",
            value=st.session_state.get(
                "excluded_keywords_text",
                "hair removal, beauty equipment, packaging, nail, eyelash",
            ),
            key="excluded_keywords_text",
            height=80,
        )

    with col_right:
        st.text_area(
            "定位詞（請輸入英文，用逗號分隔，例如：organic, natural, vegan）",
            value=st.session_state.get(
                "positioning_keywords_text",
                "organic, natural, vegan",
            ),
            key="positioning_keywords_text",
            height=80,
            help=(
                "跟商品詞一樣，這裡也必須用英文，"
                "系統會拿去比對英文網站內容。"
            ),
        )

        if contains_non_english_keyword(
            st.session_state.get(
                "positioning_keywords_text", ""
            )
        ):
            st.warning(
                "偵測到定位詞含有非英文字。定位詞也必須是英文，"
                "例如 organic, natural, vegan，否則同樣幾乎找不到結果。"
            )

        st.multiselect(
            "地區（可複選；不選代表不限制地區）",
            options=(
                [NO_REGION_LABEL]
                + sorted(REGION_COUNTRIES.keys())
            ),
            default=st.session_state.get(
                "selected_regions", ["europe"]
            ),
            key="selected_regions",
            format_func=lambda option: (
                REGION_LABELS.get(option, option)
            ),
        )

    with st.expander("進階：國家細部設定（多數情況不用改）"):
        st.text_input(
            "只包含以下國家（用逗號分隔，選填）",
            value=st.session_state.get(
                "included_countries_text", ""
            ),
            key="included_countries_text",
            help=(
                "只要這裡有填國家，就只會搜這些國家，"
                "上面「地區」選單會被忽略（不用特地清空），"
                "避免地區跟國家同時生效、搜尋範圍變得比預期大。"
            ),
        )

        if st.session_state.get(
            "included_countries_text", ""
        ).strip() and st.session_state.get(
            "selected_regions", []
        ):
            st.caption(
                "已填國家，上面選的地區目前不會生效"
                "（以國家為準）。"
            )

        if contains_non_english_keyword(
            st.session_state.get(
                "included_countries_text", ""
            )
        ):
            st.warning(
                "國家請用英文名稱（例如 Korea、Japan），"
                "中文國名（例如「韓國」）比對不到展覽名錄的"
                "國家資料，會篩出 0 家。"
            )

        st.text_input(
            "排除以下國家（用逗號分隔，選填）",
            value=st.session_state.get(
                "excluded_countries_text", ""
            ),
            key="excluded_countries_text",
        )

    st.subheader("2. 執行設定")

    st.radio(
        "資料來源",
        options=SOURCE_OPTIONS,
        index=SOURCE_OPTIONS.index(
            st.session_state.get(
                "selected_source",
                SOURCE_OPTION_BOTH,
            )
        ),
        key="selected_source",
        help=(
            "只用 Google 搜尋：不查三大展覽官方名錄，"
            "省下展覽端的分析與台灣代理查證用量。\n\n"
            "只用展覽名錄：不執行 Google 搜尋，"
            "省下 Google 端的 SerpAPI 查詢用量，"
            "只用 Asia／North America／Bologna "
            "官方名錄本身收錄的公司。"
        ),
        horizontal=True,
    )

    render_exhibition_freshness()

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.number_input(
            "目標家數（每個來源各自的目標，實際總數最多約為此數字的2倍）",
            min_value=1,
            max_value=500,
            value=st.session_state.get(
                "target_count", 10
            ),
            key="target_count",
        )

    with col_b:
        st.checkbox(
            "查證台灣代理狀況（關閉可省下約六成查詢量，"
            "但需要自行確認台灣市場代理情況）",
            value=st.session_state.get(
                "check_taiwan_distributor", True
            ),
            key="check_taiwan_distributor",
        )

    with col_c:
        st.checkbox(
            "測試模式（只搜前2組英文關鍵字，快速驗證用）",
            value=st.session_state.get(
                "test_mode", False
            ),
            key="test_mode",
        )

    with st.expander("進階選項（一般不需要調整）"):
        st.checkbox(
            "強制重新分析已收錄的品牌",
            value=st.session_state.get(
                "force_refresh_brands", False
            ),
            key="force_refresh_brands",
        )

        st.checkbox(
            "強制重新查證台灣代理狀況",
            value=st.session_state.get(
                "force_refresh_taiwan", False
            ),
            key="force_refresh_taiwan",
        )

        st.checkbox(
            "開啟深度搜尋（Google 每組關鍵字多翻頁挖更深，"
            "會顯著增加查詢量與費用，開啟前請先確認預算）",
            value=st.session_state.get(
                "enable_deep_pagination", False
            ),
            key="enable_deep_pagination",
        )

    st.divider()
    st.subheader("3. 預估用量（建議執行前先看一次）")

    if st.button("估算這次搜尋的用量與費用"):
        profile = build_search_profile()
        config = build_search_config()

        with st.spinner("估算中..."):
            try:
                estimate = estimate_search_cost(
                    config, profile
                )
                st.session_state[
                    "last_estimate"
                ] = estimate
                st.session_state[
                    "last_estimate_fingerprint"
                ] = compute_run_fingerprint(
                    config, profile
                )

            except Exception as error:
                st.error(f"估算失敗：{error}")
                st.session_state[
                    "last_estimate"
                ] = None
                st.session_state[
                    "last_estimate_fingerprint"
                ] = None

            try:
                matched_existing = (
                    match_existing_database_records(
                        profile, OUTPUT_PATH
                    )
                )
                st.session_state[
                    "matched_existing_count"
                ] = len(matched_existing)

            except Exception as error:
                st.session_state[
                    "matched_existing_count"
                ] = None
                st.warning(
                    f"資料庫反查失敗：{error}"
                )

    if st.session_state.get("last_estimate"):
        render_cost_estimate(
            st.session_state["last_estimate"]
        )

    if (
        st.session_state.get(
            "matched_existing_count"
        )
        is not None
    ):
        st.info(
            "資料庫目前已收錄、且符合這次搜尋條件的公司："
            f"{st.session_state['matched_existing_count']} 家"
            "（這些不用花錢重新查詢，執行搜尋時會自動一併算入資料庫總數）"
        )

    st.divider()
    st.subheader("4. 執行搜尋")

    shared_state = get_shared_run_state()

    if shared_state["running"] and (
        shared_state["thread"] is None
        or not shared_state[
            "thread"
        ].is_alive()
    ):
        # 執行緒已經結束，但畫面還沒來得及收尾
        # （例如剛好在這個時間點重新整理頁面）。
        shared_state["running"] = False

    if shared_state["running"]:
        st.info(
            "目前有一個搜尋正在背景執行中"
        )

    if not shared_state["running"]:
        current_profile = (
            build_search_profile()
        )
        current_config = (
            build_search_config()
        )
        current_fingerprint = (
            compute_run_fingerprint(
                current_config,
                current_profile,
            )
        )

        last_estimate = st.session_state.get(
            "last_estimate"
        )
        last_estimate_fingerprint = (
            st.session_state.get(
                "last_estimate_fingerprint"
            )
        )

        estimate_is_fresh = (
            last_estimate is not None
            and last_estimate_fingerprint
            == current_fingerprint
        )

        can_start = estimate_is_fresh

        if not estimate_is_fresh:
            st.warning(
                "請先在上面點「估算這次搜尋的用量與費用」，"
                "且中途不要再更改任何設定，才能開始搜尋"
                "（避免設定改了卻沒重新估算，導致實際用量"
                "跟你看到的預估數字不一樣）。"
            )

        else:
            is_high_cost = (
                last_estimate[
                    "serpapi_calls_estimate"
                ]
                > COST_CONFIRMATION_SERPAPI_CALLS_THRESHOLD
                or last_estimate[
                    "openai_cost_usd_estimate"
                ]
                > COST_CONFIRMATION_USD_THRESHOLD
            )

            if is_high_cost:
                st.warning(
                    "這次預估用量偏高：約"
                    f"{last_estimate['serpapi_calls_estimate']}"
                    " 次 SerpAPI 查詢、OpenAI 費用約 US$"
                    f"{last_estimate['openai_cost_usd_estimate']:.3f}"
                    "，請確認後再繼續。"
                )

                can_start = st.checkbox(
                    "我了解這次預估費用較高，仍要繼續執行",
                    key=(
                        "confirm_high_cost_"
                        f"{current_fingerprint}"
                    ),
                )

        if st.button(
            "開始搜尋",
            type="primary",
            disabled=not can_start,
        ):
            profile = current_profile
            config = current_config

            shared_state["progress"] = {
                "stage": "準備中...",
                "current": 0,
                "total": 0,
                "accepted": 0,
            }
            shared_state["result"] = {
                "done": False,
                "summary": None,
                "error": None,
                "log": "",
            }
            shared_state[
                "cancel_event"
            ] = threading.Event()

            thread = threading.Thread(
                target=(
                    run_pipeline_in_background
                ),
                args=(
                    config,
                    profile,
                    shared_state["progress"],
                    shared_state[
                        "cancel_event"
                    ],
                    shared_state["result"],
                ),
                daemon=True,
            )

            shared_state["thread"] = thread
            shared_state["running"] = True

            thread.start()
            st.rerun()

    else:
        progress_state = shared_state[
            "progress"
        ]
        result_state = shared_state[
            "result"
        ]
        cancel_event = shared_state[
            "cancel_event"
        ]
        thread = shared_state["thread"]

        stage = progress_state.get(
            "stage", ""
        )
        current = progress_state.get(
            "current", 0
        )
        total = progress_state.get(
            "total", 0
        )
        accepted = progress_state.get(
            "accepted", 0
        )

        if total > 0:
            st.progress(
                min(current / total, 1.0),
                text=(
                    f"{stage}"
                    f"（第 {current}/{total} 筆，"
                    f"已收錄 {accepted} 家）"
                ),
            )
        else:
            st.info(f"{stage}")

        if cancel_event.is_set():
            st.caption(
                "正在停止（收集階段無法立即中斷，"
                "分析階段會在處理完目前這一筆後"
                "的幾秒內停止；已完成的部分不會遺失）..."
            )
        else:
            if st.button(
                "停止搜尋", type="secondary"
            ):
                cancel_event.set()
                st.rerun()

        if thread.is_alive():
            time.sleep(1)
            st.rerun()

        else:
            shared_state["running"] = False

            if result_state["error"]:
                st.error(
                    "搜尋執行失敗："
                    f"{result_state['error']}"
                )

            else:
                shared_state["last_summary"] = (
                    result_state["summary"]
                )

            shared_state["last_log"] = (
                result_state["log"]
            )

            st.rerun()

    if shared_state.get("last_summary"):
        summary = shared_state[
            "last_summary"
        ]

        if summary.get("cancelled"):
            st.warning(
                "搜尋已中止。"
                f"已保留本次找到 {summary.get('本次找到', 0)} 筆，"
                f"新增 {summary.get('新增品牌', 0)} 筆，"
                f"更新 {summary.get('更新品牌', 0)} 筆，"
                f"鎖定跳過 {summary.get('鎖定跳過', 0)} 筆，"
                f"資料庫總數 {summary.get('資料庫總數', 0)} 筆"
            )
        else:
            st.success(
                "搜尋完成！"
                f"本次找到 {summary.get('本次找到', 0)} 筆，"
                f"新增 {summary.get('新增品牌', 0)} 筆，"
                f"更新 {summary.get('更新品牌', 0)} 筆，"
                f"鎖定跳過 {summary.get('鎖定跳過', 0)} 筆，"
                f"資料庫總數 {summary.get('資料庫總數', 0)} 筆"
            )

    if shared_state.get("last_log"):
        with st.expander("查看本次執行紀錄（詳細日誌）"):
            st.code(
                shared_state["last_log"],
                language=None,
            )


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


def render_database_tab() -> None:
    st.subheader("資料庫瀏覽")

    records = load_existing_records(OUTPUT_PATH)

    if not records:
        st.info(
            f"目前找不到資料（{OUTPUT_PATH} 尚未建立或是空的）。"
            "執行一次搜尋之後，這裡就會顯示累積的資料。"
        )
        return

    dataframe = pd.DataFrame(records).fillna("")

    if "搜尋名稱" not in dataframe.columns:
        dataframe["搜尋名稱"] = ""

    st.caption(f"目前資料庫總筆數：{len(dataframe)}")

    filter_columns = st.columns(5)

    with filter_columns[0]:
        search_name_text = st.text_input(
            "搜尋名稱關鍵字搜尋"
        )

    with filter_columns[1]:
        classification_options = ["全部"] + sorted(
            value
            for value in dataframe.get(
                "AI分類", pd.Series(dtype=str)
            ).unique()
            if str(value).strip()
        )
        selected_classification = st.selectbox(
            "AI分類",
            classification_options,
        )

    with filter_columns[2]:
        taiwan_options = ["全部"] + sorted(
            value
            for value in dataframe.get(
                "台灣代理狀態", pd.Series(dtype=str)
            ).unique()
            if str(value).strip()
        )
        selected_taiwan_status = st.selectbox(
            "台灣代理狀態",
            taiwan_options,
        )

    with filter_columns[3]:
        country_options = ["全部"] + sorted(
            value
            for value in dataframe.get(
                "國家", pd.Series(dtype=str)
            ).unique()
            if str(value).strip()
        )
        selected_country = st.selectbox(
            "國家",
            country_options,
        )

    with filter_columns[4]:
        company_search_text = st.text_input(
            "公司名稱關鍵字搜尋"
        )

    filtered_dataframe = filter_database_dataframe(
        dataframe,
        search_name_text=search_name_text,
        selected_classification=selected_classification,
        selected_taiwan_status=selected_taiwan_status,
        selected_country=selected_country,
        company_search_text=company_search_text,
    )

    st.caption(
        f"篩選後筆數：{len(filtered_dataframe)}"
    )

    st.dataframe(
        filtered_dataframe.astype(str),
        width="stretch",
        height=520,
    )

    excel_bytes = export_dataframe_to_excel_bytes(
        filtered_dataframe,
        sheet_name="篩選結果",
    )

    st.download_button(
        "下載目前篩選結果（Excel）",
        data=excel_bytes,
        file_name="篩選結果.xlsx",
        mime=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
    )


def render_about_tab() -> None:
    st.subheader("關於這個系統")

    st.markdown(
        """
### 這是做什麼的

自動從 **Google 搜尋**、以及**三大美妝展覽官方名錄**
（Cosmoprof Asia／North America／Worldwide Bologna）
找出符合條件的海外品牌，用 AI 判斷是否適合代理、
是否已有台灣代理商，最後整理進 Excel 資料庫——
取代原本手動一家一家上網查、開 Excel 記錄的作法。

---

## 分頁 1：搜尋設定與執行

### 1. 設定搜尋條件

| 欄位 | 說明 |
|---|---|
| 搜尋名稱 | 給自己看的標籤（例如「歐洲有機洗髮精」），會存進每一筆結果，之後可以在「資料庫瀏覽」用這個名稱篩出同一批結果 |
| 商品詞 | 想找的商品類型，例如 `shampoo, conditioner`。**必須用英文**——系統會拿去比對國外網站的英文內容，也會自動翻譯成其他語言去搜尋，中文（例如「手工皂」）幾乎比對不到任何結果 |
| 定位詞 | 品牌定位，例如 `organic, natural, vegan`，同樣要英文 |
| 排除詞 | 選填，用來排除誤判的類別，例如 `nail, packaging` |
| 地區 | 可複選（歐洲／歐盟／亞洲／北美…），不選代表不限地區 |
| 只包含以下國家（進階） | 只要這裡有填國家，**就只搜這些國家，地區選單會被忽略**（兩者不會疊加，避免搜尋範圍比預期大） |
| 排除以下國家（進階） | 跟地區／包含國家疊加使用，例如「地區選歐洲、這裡填 Germany」＝歐洲扣掉德國 |

商品詞／定位詞／同義詞的自動擴充：`shampoo` 也會一併搜尋
`hair wash`、`hair cleanser` 這類同義詞或詞形變化，不用自己一一列出。

### 2. 執行設定

| 欄位 | 說明 |
|---|---|
| 資料來源 | 三選一：**Google 搜尋＋展覽名錄（預設）**／只用 Google／只用展覽名錄。關掉的來源完全不會產生查詢費用 |
| 目標家數 | Google 端跟展覽端各自的目標，實際結果最多約為這個數字的 2 倍，且受限於真實候選池大小（不會為了衝數字亂花錢） |
| 查證台灣代理狀況 | 關閉可省下約六成查詢量與費用，但要自行確認台灣市場代理情況 |
| 測試模式 | 只搜前 2 組英文關鍵字，快速驗證條件設得對不對，正式搜尋前建議先開這個試跑一次 |
| 進階選項 | 強制重新分析已收錄品牌／強制重新查台灣代理／開啟深度搜尋（Google 多翻頁挖更深，會顯著增加費用） |

### 3. 預估用量

執行前先按「估算這次搜尋的用量與費用」，會顯示：

- 預估 SerpAPI 查詢次數、預估通過 AI 篩選家數
- 預估 OpenAI 費用、預估耗時
- 三大展覽各自符合條件的家數
- 資料庫裡已經有多少符合這次條件的公司（不用花錢重查）

確認數字合理再按「開始搜尋」，避免結果或費用超出預期。

### 4. 執行搜尋

- 按下「開始搜尋」後會顯示**即時進度條**（第幾筆／共幾筆、已收錄幾家），不是乾等的轉圈圈
- 隨時可以按「**停止搜尋**」，通常幾秒內就會真的停下來，**已經分析、已經存檔的結果不會遺失**
- 就算不小心重新整理網頁，進度跟停止按鈕都還在（狀態存在後端，不會因為重新整理就失聯）
- 執行完成後可以展開「查看本次執行紀錄」看詳細日誌

---

## 分頁 2：資料庫瀏覽

- 顯示 `data/output.xlsx` 累積的所有品牌資料
- 篩選條件：搜尋名稱（關鍵字）、AI分類、台灣代理狀態、國家、公司名稱
- 「下載目前篩選結果」可以把篩選後的子集另外匯出成 Excel，欄寬格式跟主資料庫一致

### 人工確認欄位（防止修正被覆蓋）

品牌超過 30 天（或勾選「強制重新分析」）會被 AI 重新分析一次，
國家、商品類別等自動判斷欄位會被新結果覆蓋。如果同事已經在
Excel 裡手動核對／修正過某一筆資料，**在「人工確認」欄位填上
任何內容**（例如「是」、「V」），這一整筆資料之後就會被完全
鎖定、不再被覆蓋，直到你自己清空這一欄為止。

「後續連絡情況」「連絡人資料」這兩欄則永遠受保護，不需要鎖定
也不會被自動覆蓋。

---

## 資料放在哪裡

所有結果都存在專案資料夾底下的 `data/output.xlsx`，這份 Excel
就是資料庫，可以直接放在公司 NAS 上長期保存、多人共用查閱。

## 使用上的小提醒

- 商品詞／定位詞／國家名稱都要用**英文**，介面偵測到中文會跳出警告
- 「地區」跟「只包含以下國家」不會疊加，填了國家就以國家為準
- 建議先跑一次「測試模式」確認條件正確，再關掉測試模式跑正式搜尋
"""
    )


tab_search, tab_database, tab_about = st.tabs(
    [
        "搜尋設定與執行",
        "資料庫瀏覽",
        "關於／使用說明",
    ]
)

with tab_search:
    render_search_tab()

with tab_database:
    render_database_tab()

with tab_about:
    render_about_tab()
