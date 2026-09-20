"""
一次性工具：產生授權簽章用的 Ed25519 金鑰對。

⚠️ 這支腳本只需要在建立授權系統的當下執行一次。
私鑰（keys/license_signing_key.pem）絕對不能外流、不能進版控、
不能出現在任何交付給客戶的資料夾裡——誰拿到私鑰，誰就能自己
簽出合法的授權檔案，等於整套授權機制形同虛設。

公鑰會印出來，需要手動貼到 modules/license_manager.py 的
PUBLIC_KEY_PEM 常數裡，這個常數是設計成公開的，會跟著
modules/ 一起打包給客戶（客戶端只需要公鑰來「驗證」授權檔案，
不需要、也不能有私鑰）。

如果私鑰不慎遺失或外流，唯一的補救方式是重新執行這支腳本產生
新的金鑰對、更新 modules/license_manager.py 的公鑰、重新打包
交付所有客戶，並且用新私鑰重新簽發每一位客戶的授權檔案
——舊的授權檔案會全部失效。所以正常情況下這支腳本執行一次後，
keys/license_signing_key.pem 要妥善備份，不要再重新執行。
"""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

KEYS_DIR = Path(__file__).parent / "keys"
PRIVATE_KEY_PATH = KEYS_DIR / "license_signing_key.pem"


def main() -> None:
    if PRIVATE_KEY_PATH.exists():
        raise SystemExit(
            f"{PRIVATE_KEY_PATH} 已經存在，為避免不小心覆蓋掉"
            "正在使用中的簽章金鑰（會讓所有已發出的授權檔案失效），"
            "這支腳本拒絕執行。如果真的要重新產生金鑰，"
            "請先手動備份或刪除現有的檔案。"
        )

    KEYS_DIR.mkdir(exist_ok=True)

    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    PRIVATE_KEY_PATH.write_bytes(private_pem)

    print(f"私鑰已寫入：{PRIVATE_KEY_PATH}")
    print("（此檔案已經在 .gitignore 內，請額外自行備份到安全的地方）")
    print()
    print(
        "請把下面這段公鑰貼到 "
        "modules/license_manager.py 的 PUBLIC_KEY_PEM 常數："
    )
    print()
    print(public_pem.decode("utf-8"))


if __name__ == "__main__":
    main()
