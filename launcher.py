"""
啟動前的環境檢查，避免非技術背景的使用者卡在看不懂的英文錯誤訊息。

執行順序：Python 版本檢查 → 套件安裝 → .env 金鑰檢查 →
license.lic 存在檢查 → 啟動 Streamlit。任何一關沒過，
都會印出中文說明並停在原地，不會往下跑到令人困惑的錯誤畫面。

這支檔案刻意保持單純、不放任何商業邏輯，所以不需要跟著
modules/ 一起用 PyArmor 混淆，明文交付即可。
"""

import subprocess
import sys
from pathlib import Path

REQUIRED_PYTHON = (3, 13)

PROJECT_ROOT = Path(__file__).parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
LICENSE_PATH = PROJECT_ROOT / "license.lic"
REQUIREMENTS_PATH = PROJECT_ROOT / "requirements.txt"

REQUIRED_ENV_KEYS = ("OPENAI_API_KEY", "SEARCH_API_KEY")


def check_python_version() -> None:
    current = sys.version_info[:2]

    if current != REQUIRED_PYTHON:
        print(
            f"[提醒] 目前偵測到的 Python 版本是 "
            f"{current[0]}.{current[1]}，"
            f"本軟體是針對 Python "
            f"{REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]} 打包的。"
        )
        print(
            "版本不同不一定會出問題，但如果接下來出現難以理解的"
            "錯誤訊息，請先安裝對應版本的 Python 再試一次。"
        )
        print()


def install_requirements() -> bool:
    if not REQUIREMENTS_PATH.exists():
        return True

    print("[檢查 1/3] 確認相依套件已安裝 ...")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-r",
            str(REQUIREMENTS_PATH),
            "--quiet",
            "--disable-pip-version-check",
        ]
    )

    if result.returncode != 0:
        print()
        print(
            "[錯誤] 套件安裝失敗，請確認這台電腦有連接網路，"
            "或聯繫供應商協助處理。"
        )
        return False

    print("[檢查 1/3] 套件安裝完成。")
    print()
    return True


def check_env_file() -> bool:
    print("[檢查 2/3] 確認 API 金鑰設定 ...")

    if not ENV_PATH.exists():
        print()
        print("[錯誤] 找不到 .env 設定檔。")

        if ENV_EXAMPLE_PATH.exists():
            ENV_PATH.write_text(
                ENV_EXAMPLE_PATH.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            print(
                "已經幫你複製一份範本到 .env，"
                "請參考「API 金鑰申請教學」文件，"
                "打開 .env 填入你的 API 金鑰後，"
                "重新執行本程式。"
            )
        else:
            print("請聯繫供應商取得 .env 設定檔範本。")

        return False

    # 延後到這裡才 import，避免第一次執行、套件還沒裝好時
    # 這支檔案本身就因為 import 失敗而整個打不開。
    from dotenv import dotenv_values

    values = dotenv_values(ENV_PATH)

    missing = [
        key
        for key in REQUIRED_ENV_KEYS
        if not values.get(key)
        or str(values.get(key)).startswith("請填入")
    ]

    if missing:
        print()
        print(
            "[錯誤] .env 設定檔裡，以下欄位還沒有填入金鑰："
            f"{', '.join(missing)}"
        )
        print(
            "請參考「API 金鑰申請教學」文件申請帳號並填入金鑰，"
            "填好後重新執行本程式。"
        )
        return False

    print("[檢查 2/3] API 金鑰設定正常。")
    print()
    return True


def check_license_file() -> bool:
    print("[檢查 3/3] 確認授權檔案 ...")

    if not LICENSE_PATH.exists():
        print()
        print(
            "[錯誤] 找不到授權檔案 license.lic，"
            "請聯繫供應商取得授權後再試一次。"
        )
        return False

    print("[檢查 3/3] 授權檔案存在，實際是否有效由系統啟動後確認。")
    print()
    return True


def launch_app() -> None:
    print("[啟動] 所有檢查通過，正在啟動系統，請稍候 ...")
    print()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
        ]
    )


def main() -> None:
    print("=" * 50)
    print("  AI 海外品牌搜尋系統 - 啟動檢查")
    print("=" * 50)
    print()

    check_python_version()

    if not install_requirements():
        return

    if not check_env_file():
        return

    if not check_license_file():
        return

    launch_app()


if __name__ == "__main__":
    main()
