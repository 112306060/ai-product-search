"""
簽發客戶授權檔案（license.lic）。

只能在保有 keys/license_signing_key.pem 私鑰的這台開發機上執行。
產生的 license.lic 要交付給客戶，放在他們那份 dist_release/
資料夾內、跟 app.py 同一層目錄。每位客戶、每次續約都要重新執行
一次這支腳本，產生一份新的 license.lic 給對方，不需要重新打包
或重新交付其他程式碼。

用法：
    python generate_license.py --customer "○○貿易股份有限公司" --days 365
    python generate_license.py --customer "David 內部測試" --days 36500
"""

import argparse
import base64
import json
from datetime import date, timedelta
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

PRIVATE_KEY_PATH = (
    Path(__file__).parent / "keys" / "license_signing_key.pem"
)


def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--customer",
        required=True,
        help="客戶名稱，會顯示在軟體畫面上",
    )
    parser.add_argument(
        "--days",
        type=int,
        required=True,
        help="授權天數，從今天起算",
    )
    parser.add_argument(
        "--output",
        default="license.lic",
        help="輸出檔名，預設 license.lic",
    )
    args = parser.parse_args()

    if not PRIVATE_KEY_PATH.exists():
        raise SystemExit(
            f"找不到簽章私鑰：{PRIVATE_KEY_PATH}\n"
            "這支腳本只能在保有私鑰的這台開發機上執行，"
            "如果私鑰不見了，請看 generate_keys.py 的說明。"
        )

    private_key = serialization.load_pem_private_key(
        PRIVATE_KEY_PATH.read_bytes(),
        password=None,
    )

    if not isinstance(private_key, Ed25519PrivateKey):
        raise SystemExit(
            "私鑰格式不是 Ed25519，"
            "請確認 keys/ 資料夾內容正確。"
        )

    today = date.today()
    expires_at = today + timedelta(days=args.days)

    payload = {
        "customer": args.customer,
        "product": "ai-brand-search",
        "issued_at": today.isoformat(),
        "expires_at": expires_at.isoformat(),
    }

    signature = private_key.sign(
        _canonical_payload_bytes(payload)
    )

    license_data = {
        "payload": payload,
        "signature": base64.b64encode(signature).decode(
            "ascii"
        ),
    }

    output_path = Path(args.output)
    output_path.write_text(
        json.dumps(
            license_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"已產生授權檔案：{output_path}")
    print(f"客戶：{args.customer}")
    print(
        f"到期日：{expires_at.isoformat()}"
        f"（共 {args.days} 天）"
    )
    print()
    print(
        "請把這個檔案放到客戶交付資料夾內，"
        "跟 app.py 同一層目錄。"
    )


if __name__ == "__main__":
    main()
