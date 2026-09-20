import shutil
import tempfile
from pathlib import Path
from unittest import mock

from config import SearchConfig
from modules.search_profile import SearchProfile
import modules.search_history as search_history
from modules.search_history import (
    load_search_history,
    record_search_run,
)


def build_test_profile(**overrides) -> SearchProfile:
    fields = dict(
        query="歐洲有機天然洗髮精",
        product_keywords=["shampoo"],
        positioning_keywords=["organic"],
        excluded_keywords=[],
        included_regions=["europe"],
        included_countries=[],
        excluded_countries=[],
    )
    fields.update(overrides)
    return SearchProfile(**fields)


def build_test_summary(**overrides) -> dict:
    summary = {
        "本次找到": 5,
        "新增品牌": 3,
        "更新品牌": 2,
        "鎖定跳過": 0,
        "資料庫總數": 42,
    }
    summary.update(overrides)
    return summary


def test_record_and_load_round_trip():
    scratch_dir = Path(tempfile.mkdtemp())

    try:
        with mock.patch.object(
            search_history,
            "HISTORY_PATH",
            scratch_dir / "history.jsonl",
        ):
            record_search_run(
                build_test_profile(),
                SearchConfig(target_count=10),
                build_test_summary(),
            )

            entries = load_search_history()

        assert len(entries) == 1
        entry = entries[0]
        assert entry["搜尋名稱"] == "歐洲有機天然洗髮精"
        assert entry["商品詞"] == ["shampoo"]
        assert entry["目標家數"] == 10
        assert entry["新增品牌"] == 3
        assert entry["中止"] is False

    finally:
        shutil.rmtree(scratch_dir)


def test_multiple_entries_ordered_newest_first():
    scratch_dir = Path(tempfile.mkdtemp())

    try:
        with mock.patch.object(
            search_history,
            "HISTORY_PATH",
            scratch_dir / "history.jsonl",
        ):
            record_search_run(
                build_test_profile(query="第一次搜尋"),
                SearchConfig(),
                build_test_summary(),
            )
            record_search_run(
                build_test_profile(query="第二次搜尋"),
                SearchConfig(),
                build_test_summary(),
            )

            entries = load_search_history()

        assert len(entries) == 2
        assert entries[0]["搜尋名稱"] == "第二次搜尋"
        assert entries[1]["搜尋名稱"] == "第一次搜尋"

    finally:
        shutil.rmtree(scratch_dir)


def test_corrupted_line_is_skipped():
    scratch_dir = Path(tempfile.mkdtemp())

    try:
        history_path = scratch_dir / "history.jsonl"

        with mock.patch.object(
            search_history,
            "HISTORY_PATH",
            history_path,
        ):
            record_search_run(
                build_test_profile(query="正常紀錄"),
                SearchConfig(),
                build_test_summary(),
            )

            with history_path.open(
                "a", encoding="utf-8"
            ) as history_file:
                history_file.write(
                    "this is not valid json\n"
                )

            entries = load_search_history()

        assert len(entries) == 1
        assert entries[0]["搜尋名稱"] == "正常紀錄"

    finally:
        shutil.rmtree(scratch_dir)


def test_missing_file_returns_empty_list():
    scratch_dir = Path(tempfile.mkdtemp())

    try:
        with mock.patch.object(
            search_history,
            "HISTORY_PATH",
            scratch_dir / "does_not_exist.jsonl",
        ):
            entries = load_search_history()

        assert entries == []

    finally:
        shutil.rmtree(scratch_dir)


def test_cancelled_run_is_recorded():
    scratch_dir = Path(tempfile.mkdtemp())

    try:
        with mock.patch.object(
            search_history,
            "HISTORY_PATH",
            scratch_dir / "history.jsonl",
        ):
            record_search_run(
                build_test_profile(),
                SearchConfig(),
                build_test_summary(cancelled=True),
            )

            entries = load_search_history()

        assert entries[0]["中止"] is True

    finally:
        shutil.rmtree(scratch_dir)


if __name__ == "__main__":
    test_record_and_load_round_trip()
    test_multiple_entries_ordered_newest_first()
    test_corrupted_line_is_skipped()
    test_missing_file_returns_empty_list()
    test_cancelled_run_is_recorded()

    print("All search_history tests passed.")
