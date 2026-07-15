"""
AI 海外品牌搜尋系統 - Streamlit 前端。

啟動方式：
    streamlit run app.py
或直接雙擊 run_frontend.bat。
"""

import contextlib
import io
import re
import threading
import time

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

            except Exception as error:
                st.error(f"估算失敗：{error}")
                st.session_state[
                    "last_estimate"
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
            "（就算重新整理這個頁面也看得到、"
            "也能按停止——不會像之前一樣失聯）。"
        )

    if not shared_state["running"]:
        if st.button(
            "開始搜尋", type="primary"
        ):
            profile = build_search_profile()
            config = build_search_config()

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
                f"資料庫總數 {summary.get('資料庫總數', 0)} 筆"
            )
        else:
            st.success(
                "搜尋完成！"
                f"本次找到 {summary.get('本次找到', 0)} 筆，"
                f"新增 {summary.get('新增品牌', 0)} 筆，"
                f"更新 {summary.get('更新品牌', 0)} 筆，"
                f"資料庫總數 {summary.get('資料庫總數', 0)} 筆"
            )

    if shared_state.get("last_log"):
        with st.expander("查看本次執行紀錄（詳細日誌）"):
            st.code(
                shared_state["last_log"],
                language=None,
            )


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

自動從 Google 搜尋、以及三大美妝展覽官方名錄
（Cosmoprof Asia／North America／Worldwide Bologna）
找出符合條件的海外品牌，並用 AI 判斷是否適合代理、
是否已有台灣代理商，最後整理進 Excel 資料庫。

### 欄位說明

- **商品詞／定位詞**：描述你想找的商品類型跟品牌定位，
  系統會自動幫每個詞擴充同義詞／詞形變化（例如
  shampoo 也會一併搜尋 hair wash、hair cleanser）。
- **地區**：限制只找特定地區的公司；不選代表不限制地區（全球）。
- **目標家數**：Google 端跟展覽端各自的目標，
  實際結果最多約為這個數字的 2 倍，但會受限於真實候選池大小
  （系統會自動判斷候選池是否已經到頂，不會為了衝數字而亂花錢）。

### 預估用量怎麼看

執行前先按「估算這次搜尋的用量與費用」，
確認 SerpAPI 查詢次數／預估費用／預估耗時可以接受，
再按「開始搜尋」，避免搜出來的結果或費用超出預期。

### 資料放在哪裡

所有結果都存在專案資料夾底下的 `data/output.xlsx`，
這份 Excel 就是資料庫，可以直接放在 NAS 上，
或用「資料庫瀏覽」分頁篩選、下載子集。

### 台灣代理查證要不要開

如果會自行確認台灣市場代理狀況，可以在「執行設定」裡
關閉「查證台灣代理狀況」，能省下約六成的查詢量與費用。
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
