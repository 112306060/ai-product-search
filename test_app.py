"""
測試 app.py（Streamlit 前端）裡不依賴真人操作畫面
也能驗證的核心邏輯：

- build_search_profile() / build_search_config()
- compute_run_fingerprint()（成本硬性關卡的指紋比對）
- 開始搜尋按鈕的三種狀態（未估算 / 低用量 / 高用量需確認）
- get_exhibition_source_freshness()（展覽來源新鮮度提醒）
- contains_non_english_keyword()
- filter_database_dataframe()（資料庫瀏覽的篩選邏輯）

前四類直接呼叫函式或用 st.session_state 模擬輸入即可驗證，
不需要真的執行搜尋、不會呼叫任何收費 API。
「按鈕三種狀態」需要透過 streamlit.testing.v1.AppTest 跑過
一次真正的估算流程（會呼叫展覽官方名錄，本身不收費但需要
幾秒到十幾秒），因此執行速度比其他測試慢一些，是預期中的。
"""

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pandas as pd
import streamlit as st

import app
from modules import app_logic
from config import SearchConfig
from modules.search_profile import SearchProfile


# ---------------------------------------------------------------------------
# contains_non_english_keyword
# ---------------------------------------------------------------------------

def test_contains_non_english_keyword_detects_chinese():
    assert app_logic.contains_non_english_keyword("手工皂") is True
    assert app_logic.contains_non_english_keyword("shampoo, 手工皂") is True


def test_contains_non_english_keyword_allows_english():
    assert app_logic.contains_non_english_keyword("shampoo, conditioner") is False
    assert app_logic.contains_non_english_keyword("") is False


# ---------------------------------------------------------------------------
# build_search_profile / build_search_config
# ---------------------------------------------------------------------------

def test_build_search_profile_parses_keywords_and_regions():
    st.session_state["query_text"] = "歐洲有機天然洗髮精"
    st.session_state["product_keywords_text"] = "shampoo, conditioner"
    st.session_state["positioning_keywords_text"] = "organic, natural"
    st.session_state["excluded_keywords_text"] = "nail, packaging"
    st.session_state["selected_regions"] = ["europe"]
    st.session_state["included_countries_text"] = ""
    st.session_state["excluded_countries_text"] = ""

    profile = app_logic.build_search_profile()

    assert profile.product_keywords == ["shampoo", "conditioner"]
    assert profile.positioning_keywords == ["organic", "natural"]
    assert profile.excluded_keywords == ["nail", "packaging"]
    assert profile.included_regions == ["europe"]
    assert profile.included_countries == []


def test_build_search_profile_no_region_label_means_unrestricted():
    st.session_state["query_text"] = "test"
    st.session_state["product_keywords_text"] = "shampoo"
    st.session_state["positioning_keywords_text"] = "organic"
    st.session_state["excluded_keywords_text"] = ""
    st.session_state["selected_regions"] = [app_logic.NO_REGION_LABEL]
    st.session_state["included_countries_text"] = ""
    st.session_state["excluded_countries_text"] = ""

    profile = app_logic.build_search_profile()

    assert profile.included_regions == []


def test_build_search_profile_included_countries_parsed():
    st.session_state["query_text"] = "test"
    st.session_state["product_keywords_text"] = "hair product"
    st.session_state["positioning_keywords_text"] = "professional"
    st.session_state["excluded_keywords_text"] = ""
    st.session_state["selected_regions"] = ["europe"]
    st.session_state["included_countries_text"] = "Italy, Spain"
    st.session_state["excluded_countries_text"] = ""

    profile = app_logic.build_search_profile()

    assert profile.included_countries == ["Italy", "Spain"]
    # 有填國家時，地區會被忽略（resolved_included_countries 的行為），
    # 但 build_search_profile 本身兩者都如實記錄下來，是後續函式的責任。
    assert set(profile.resolved_included_countries()) == {
        "italy",
        "spain",
    }


def test_build_search_config_source_toggle_google_only():
    st.session_state["selected_source"] = app_logic.SOURCE_OPTION_GOOGLE_ONLY
    st.session_state["target_count"] = 10
    st.session_state["test_mode"] = False
    st.session_state["check_taiwan_distributor"] = True
    st.session_state["force_refresh_taiwan"] = False
    st.session_state["force_refresh_brands"] = False
    st.session_state["enable_deep_pagination"] = False

    config = app_logic.build_search_config()

    assert config.enable_google_search is True
    assert config.enable_exhibition_search is False


def test_build_search_config_source_toggle_exhibition_only():
    st.session_state["selected_source"] = (
        app_logic.SOURCE_OPTION_EXHIBITION_ONLY
    )
    st.session_state["target_count"] = 10
    st.session_state["test_mode"] = False
    st.session_state["check_taiwan_distributor"] = True
    st.session_state["force_refresh_taiwan"] = False
    st.session_state["force_refresh_brands"] = False
    st.session_state["enable_deep_pagination"] = False

    config = app_logic.build_search_config()

    assert config.enable_google_search is False
    assert config.enable_exhibition_search is True


def test_build_search_config_source_toggle_both():
    st.session_state["selected_source"] = app_logic.SOURCE_OPTION_BOTH
    st.session_state["target_count"] = 10
    st.session_state["test_mode"] = False
    st.session_state["check_taiwan_distributor"] = True
    st.session_state["force_refresh_taiwan"] = False
    st.session_state["force_refresh_brands"] = False
    st.session_state["enable_deep_pagination"] = False

    config = app_logic.build_search_config()

    assert config.enable_google_search is True
    assert config.enable_exhibition_search is True


# ---------------------------------------------------------------------------
# compute_run_fingerprint
# ---------------------------------------------------------------------------

def build_fingerprint_test_profile(**overrides) -> SearchProfile:
    fields = dict(
        query="test",
        product_keywords=["shampoo"],
        positioning_keywords=["organic"],
        excluded_keywords=[],
        included_regions=["europe"],
        included_countries=[],
        excluded_countries=[],
    )
    fields.update(overrides)
    return SearchProfile(**fields)


def test_fingerprint_is_stable_for_identical_settings():
    config = SearchConfig(target_count=10, test_mode=True)
    profile = build_fingerprint_test_profile()

    fingerprint_a = app_logic.compute_run_fingerprint(config, profile)
    fingerprint_b = app_logic.compute_run_fingerprint(config, profile)

    assert fingerprint_a == fingerprint_b


def test_fingerprint_changes_when_target_count_changes():
    profile = build_fingerprint_test_profile()

    fingerprint_before = app_logic.compute_run_fingerprint(
        SearchConfig(target_count=10), profile
    )
    fingerprint_after = app_logic.compute_run_fingerprint(
        SearchConfig(target_count=500), profile
    )

    assert fingerprint_before != fingerprint_after


def test_fingerprint_changes_when_profile_changes():
    config = SearchConfig(target_count=10)

    fingerprint_before = app_logic.compute_run_fingerprint(
        config,
        build_fingerprint_test_profile(),
    )
    fingerprint_after = app_logic.compute_run_fingerprint(
        config,
        build_fingerprint_test_profile(
            product_keywords=["conditioner"]
        ),
    )

    assert fingerprint_before != fingerprint_after


# ---------------------------------------------------------------------------
# get_exhibition_source_freshness
# ---------------------------------------------------------------------------

def test_exhibition_freshness_reports_missing_local_files():
    scratch_dir = Path(tempfile.mkdtemp())

    try:
        missing_bologna = scratch_dir / "no_bologna.json"
        missing_north_america = (
            scratch_dir / "no_north_america.json"
        )

        with mock.patch.object(
            app_logic,
            "BOLOGNA_CATALOG_PATH",
            str(missing_bologna),
        ), mock.patch.object(
            app_logic,
            "NORTH_AMERICA_METADATA_PATH",
            str(missing_north_america),
        ):
            sources = app_logic.get_exhibition_source_freshness()

        by_name = {
            source["name"]: source for source in sources
        }

        assert by_name["Cosmoprof Asia"]["is_live"] is True
        assert (
            by_name["Cosmoprof Worldwide Bologna"][
                "synced_at"
            ]
            is None
        )
        assert (
            by_name["Cosmoprof North America"]["synced_at"]
            is None
        )

    finally:
        shutil.rmtree(scratch_dir)


def test_exhibition_freshness_reports_recent_sync():
    scratch_dir = Path(tempfile.mkdtemp())

    try:
        bologna_path = scratch_dir / "bologna.json"
        bologna_path.write_text("{}", encoding="utf-8")

        north_america_path = (
            scratch_dir / "north_america_metadata.json"
        )
        north_america_path.write_text(
            '{"synced_at": "'
            + datetime.now(timezone.utc).isoformat()
            + '"}',
            encoding="utf-8",
        )

        with mock.patch.object(
            app_logic,
            "BOLOGNA_CATALOG_PATH",
            str(bologna_path),
        ), mock.patch.object(
            app_logic,
            "NORTH_AMERICA_METADATA_PATH",
            str(north_america_path),
        ):
            sources = app_logic.get_exhibition_source_freshness()

        by_name = {
            source["name"]: source for source in sources
        }

        assert (
            by_name["Cosmoprof Worldwide Bologna"][
                "days_old"
            ]
            == 0
        )
        assert (
            by_name["Cosmoprof North America"]["days_old"]
            == 0
        )

    finally:
        shutil.rmtree(scratch_dir)


# ---------------------------------------------------------------------------
# filter_database_dataframe
# ---------------------------------------------------------------------------

def build_filter_test_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "搜尋名稱": "歐洲有機洗髮精",
                "公司名稱": "Alpha Organic",
                "AI分類": "品牌官網",
                "台灣代理狀態": "未找到代理證據",
                "國家": "Italy",
            },
            {
                "搜尋名稱": "歐洲有機洗髮精",
                "公司名稱": "Beta Natural",
                "AI分類": "電商平台",
                "台灣代理狀態": "已有官方代理",
                "國家": "Spain",
            },
            {
                "搜尋名稱": "日本保養品",
                "公司名稱": "Gamma Skincare",
                "AI分類": "品牌官網",
                "台灣代理狀態": "未找到代理證據",
                "國家": "Japan",
            },
        ]
    )


def test_filter_by_search_name():
    dataframe = build_filter_test_dataframe()

    result = app_logic.filter_database_dataframe(
        dataframe,
        search_name_text="歐洲",
    )

    assert len(result) == 2
    assert set(result["公司名稱"]) == {
        "Alpha Organic",
        "Beta Natural",
    }


def test_filter_by_classification_and_country_combined():
    dataframe = build_filter_test_dataframe()

    result = app_logic.filter_database_dataframe(
        dataframe,
        selected_classification="品牌官網",
        selected_country="Italy",
    )

    assert len(result) == 1
    assert result.iloc[0]["公司名稱"] == "Alpha Organic"


def test_filter_by_company_name_keyword():
    dataframe = build_filter_test_dataframe()

    result = app_logic.filter_database_dataframe(
        dataframe,
        company_search_text="gamma",
    )

    assert len(result) == 1
    assert result.iloc[0]["公司名稱"] == "Gamma Skincare"


def test_filter_with_no_conditions_returns_everything():
    dataframe = build_filter_test_dataframe()

    result = app_logic.filter_database_dataframe(dataframe)

    assert len(result) == len(dataframe)


# ---------------------------------------------------------------------------
# 開始搜尋按鈕的三種狀態（成本硬性關卡）
#
# 這幾個測試會透過 AppTest 真的跑一次「估算用量」，
# 需要呼叫展覽官方名錄（免費但需要幾秒到十幾秒的網路時間），
# 執行速度比上面幾類測試慢，是預期中的取捨。
# ---------------------------------------------------------------------------

def test_start_button_disabled_before_any_estimate():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()

    start_buttons = [
        button
        for button in at.button
        if button.label == "開始搜尋"
    ]

    assert len(start_buttons) == 1
    assert start_buttons[0].disabled is True


def test_start_button_enabled_after_low_cost_estimate():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()

    at.checkbox(key="test_mode").set_value(True)
    at.number_input(key="target_count").set_value(1)
    at.run()

    estimate_button = [
        button
        for button in at.button
        if "估算" in button.label
    ][0]
    estimate_button.click()
    at.run(timeout=120)

    start_buttons = [
        button
        for button in at.button
        if button.label == "開始搜尋"
    ]

    assert start_buttons[0].disabled is False

    confirm_checkboxes = [
        checkbox
        for checkbox in at.checkbox
        if "我了解" in checkbox.label
    ]
    assert confirm_checkboxes == []


def test_start_button_requires_confirmation_for_high_cost_estimate():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()

    # 預設設定（歐洲、target_count=10、開台灣代理）
    # 實測會估出超過門檻的用量，需要額外勾選確認。
    estimate_button = [
        button
        for button in at.button
        if "估算" in button.label
    ][0]
    estimate_button.click()
    at.run(timeout=120)

    start_buttons = [
        button
        for button in at.button
        if button.label == "開始搜尋"
    ]
    assert start_buttons[0].disabled is True

    confirm_checkboxes = [
        checkbox
        for checkbox in at.checkbox
        if "我了解" in checkbox.label
    ]
    assert len(confirm_checkboxes) == 1

    confirm_checkboxes[0].set_value(True)
    at.run(timeout=60)

    start_buttons = [
        button
        for button in at.button
        if button.label == "開始搜尋"
    ]
    assert start_buttons[0].disabled is False


if __name__ == "__main__":
    test_contains_non_english_keyword_detects_chinese()
    test_contains_non_english_keyword_allows_english()

    test_build_search_profile_parses_keywords_and_regions()
    test_build_search_profile_no_region_label_means_unrestricted()
    test_build_search_profile_included_countries_parsed()
    test_build_search_config_source_toggle_google_only()
    test_build_search_config_source_toggle_exhibition_only()
    test_build_search_config_source_toggle_both()

    test_fingerprint_is_stable_for_identical_settings()
    test_fingerprint_changes_when_target_count_changes()
    test_fingerprint_changes_when_profile_changes()

    test_exhibition_freshness_reports_missing_local_files()
    test_exhibition_freshness_reports_recent_sync()

    test_filter_by_search_name()
    test_filter_by_classification_and_country_combined()
    test_filter_by_company_name_keyword()
    test_filter_with_no_conditions_returns_everything()

    print(
        "Fast logic tests passed. "
        "Running slower AppTest cost-gate tests "
        "(需要呼叫展覽官方名錄，約需數十秒)..."
    )

    test_start_button_disabled_before_any_estimate()
    test_start_button_enabled_after_low_cost_estimate()
    test_start_button_requires_confirmation_for_high_cost_estimate()

    print("All app.py tests passed.")
