"""
把系統打包成可以交給父親公司電腦、但看不到後端程式碼的交付版本。

原理：
- app.py 因為 Streamlit 的執行機制（每次互動都重新讀取明文原始碼並
  exec()）一定要維持明文，但它已經被精簡到只剩畫面排版，沒有值得
  保護的商業邏輯。
- modules/（含 modules/exhibitions/）跟 config.py 用 PyArmor 混淆成
  加密過的亂碼，肉眼打開看不到任何邏輯，執行時需要搭配 PyArmor 產生
  的 runtime 套件解密執行。

用法：
    python build_release.py                    # 平常更新程式碼／展覽名錄用
    python build_release.py --include-existing-data   # 只有第一次交付才用

⚠️ 重要：對方拿到系統後會自己持續累積資料，他們的 data/output.xlsx
之後只存在他們的電腦上，跟這台開發機的版本會逐漸分歧。所以預設
（不加任何參數）不會打包資料庫／API 快取，避免你之後重新交付
（更新程式碼或展覽名錄）時，複製過去把對方自己累積的資料覆蓋掉。
只有「這是第一次交付、對方那邊還沒有任何資料」的情況，才加上
--include-existing-data 把現有資料庫一併帶過去。

之後重新交付更新版時，只需要覆蓋對方電腦上的這幾項：
app.py、modules/、config.py、pyarmor_runtime_*/、data/exhibitions/，
絕對不要動到對方的 data/output.xlsx、data/cache/、
data/search_history.jsonl、data/coverage/ 這些他們自己產生的資料。
"""

import argparse
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "dist_release"

# 交付資料夾裡，除了混淆後的 modules/、config.py、PyArmor runtime
# 套件之外，還需要附上這些檔案（都不含商業邏輯，不需要混淆）。
FILES_TO_COPY = [
    "app.py",
    "requirements.txt",
    ".env.example",
    "run_frontend.bat",
]

# 展覽名錄快取檔——讓對方一開始就能用「展覽名錄」這個資料來源，
# 不用自己執行同步腳本（同步腳本沒有一起打包，之後由 David
# 定期在自己電腦重新產生、重新交付更新過的資料）。
EXHIBITION_CACHE_FILES = [
    "data/exhibitions/cosmoprof_bologna_2026.json",
    "data/exhibitions/cosmoprof_north_america_2026.json",
    "data/exhibitions/cosmoprof_north_america_2026_metadata.json",
]

# 現有已累積的品牌研究資料庫，這次交付決定一併帶過去，
# 讓對方接手既有成果，不用從零開始。
DATABASE_FILE = "data/output.xlsx"

# API 回應快取（台灣代理查證／Bologna 官網查詢／近期已分析品牌），
# 帶過去可以讓對方重跑到已經分析過的品牌時不用重新花錢查詢。
CACHE_DIR = "data/cache"


def run_pyarmor_obfuscation() -> None:
    print("[1/3] 用 PyArmor 混淆 modules/ 與 config.py ...")

    result = subprocess.run(
        [
            "pyarmor",
            "gen",
            "-r",
            "-O",
            str(OUTPUT_DIR),
            "modules",
            "config.py",
        ],
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "PyArmor 混淆失敗，請檢查上方錯誤訊息。"
        )


def copy_supporting_files(
    include_existing_data: bool,
) -> None:
    print("[2/3] 複製 app.py 與其他交付檔案 ...")

    for filename in FILES_TO_COPY:
        source_path = PROJECT_ROOT / filename

        if not source_path.exists():
            print(f"  警告：找不到 {filename}，略過")
            continue

        shutil.copy2(
            source_path,
            OUTPUT_DIR / filename,
        )

    data_dir = OUTPUT_DIR / "data"
    (data_dir / "exhibitions").mkdir(
        parents=True, exist_ok=True
    )

    for relative_path in EXHIBITION_CACHE_FILES:
        source_path = PROJECT_ROOT / relative_path

        if not source_path.exists():
            print(
                f"  警告：找不到 {relative_path}，略過"
            )
            continue

        shutil.copy2(
            source_path,
            OUTPUT_DIR / relative_path,
        )

    if not include_existing_data:
        print(
            "  （未加 --include-existing-data，"
            "不打包資料庫／快取，避免覆蓋對方既有資料）"
        )
        return

    database_source = PROJECT_ROOT / DATABASE_FILE

    if database_source.exists():
        shutil.copy2(
            database_source,
            OUTPUT_DIR / DATABASE_FILE,
        )
    else:
        print(
            f"  警告：找不到 {DATABASE_FILE}，略過"
        )

    cache_source = PROJECT_ROOT / CACHE_DIR

    if cache_source.exists():
        shutil.copytree(
            cache_source,
            OUTPUT_DIR / CACHE_DIR,
        )


def print_summary(
    include_existing_data: bool,
) -> None:
    print("[3/3] 打包完成")
    print()
    print(f"交付資料夾：{OUTPUT_DIR}")

    if include_existing_data:
        print(
            "內容包含：app.py（明文）、"
            "modules/（混淆後）、config.py（混淆後）、"
            "pyarmor_runtime_*/（PyArmor runtime）、"
            "requirements.txt、.env.example、run_frontend.bat、"
            "data/output.xlsx（現有資料庫）、"
            "data/exhibitions/（展覽名錄快取）、"
            "data/cache/（API 回應快取）"
        )
        print()
        print(
            "交付前提醒：對方電腦需要先安裝對應版本的 Python，"
            "並在 dist_release/ 資料夾內執行："
        )
        print("  pip install -r requirements.txt")
        print("  cp .env.example .env  （並填入自己的 API 金鑰）")
        print("  streamlit run app.py  （或雙擊 run_frontend.bat）")

    else:
        print(
            "內容包含：app.py（明文）、"
            "modules/（混淆後）、config.py（混淆後）、"
            "pyarmor_runtime_*/（PyArmor runtime）、"
            "requirements.txt、.env.example、run_frontend.bat、"
            "data/exhibitions/（展覽名錄快取）"
        )
        print()
        print(
            "⚠️ 這是更新版打包，不含資料庫／快取。"
            "覆蓋到對方電腦時，只覆蓋以下項目，"
            "不要動到對方的 data/output.xlsx、data/cache/："
        )
        print(
            "  app.py、modules/、config.py、"
            "pyarmor_runtime_*/、data/exhibitions/"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--include-existing-data",
        action="store_true",
        help=(
            "一併打包現有 data/output.xlsx 與 data/cache/，"
            "只有第一次交付（對方那邊還沒有資料）才需要"
        ),
    )
    args = parser.parse_args()

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    run_pyarmor_obfuscation()
    copy_supporting_files(args.include_existing_data)
    print_summary(args.include_existing_data)


if __name__ == "__main__":
    main()
