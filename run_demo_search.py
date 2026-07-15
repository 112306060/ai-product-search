"""
產生一份用來跟廠商 demo 的 Excel 結果。

用這幾天改善後的完整後端（多語言搜尋、擴大後的 Bologna 資料庫、
同義詞比對、成本預估等）跑一次正式規模的搜尋，
輸出到獨立的 data/output_demo.xlsx，不會動到正式的 data/output.xlsx。
"""

import dataclasses
import time

from config import DEFAULT_CONFIG, DEFAULT_SEARCH_PROFILE
from modules.search_pipeline import run_search_pipeline


DEMO_OUTPUT_PATH = "data/output_demo.xlsx"


def main():
    demo_config = dataclasses.replace(
        DEFAULT_CONFIG,
        test_mode=False,
        target_count=15,
        output_path=DEMO_OUTPUT_PATH,
        show_cost_estimate=True,
        require_run_confirmation=False,
        require_language_switch_confirmation=False,
    )

    print("=" * 70)
    print("[DEMO 搜尋設定]")
    print("=" * 70)
    print("output_path:", demo_config.output_path)
    print("target_count:", demo_config.target_count)
    print()

    start = time.time()

    summary = run_search_pipeline(
        demo_config,
        DEFAULT_SEARCH_PROFILE,
    )

    elapsed = time.time() - start

    print()
    print("=" * 70)
    print("[DEMO 搜尋完成]")
    print("=" * 70)
    print(summary)
    print(f"總耗時：{elapsed:.1f} 秒（{elapsed / 60:.1f} 分鐘）")


if __name__ == "__main__":
    main()
