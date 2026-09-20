"""
授權驗證：確認交付出去的軟體是否還在授權期限內。

設計方式：
- 用 Ed25519 簽章保護授權檔案（license.lic）——這支模組只內嵌
  「公鑰」，只能拿來驗證簽章，沒辦法反推出私鑰、也沒辦法自己
  簽出一份合法的授權檔案。真正能簽發授權的私鑰只存在
  keys/license_signing_key.pem，且已列在 .gitignore、
  build_release.py 也不會把 keys/ 資料夾打包出去。
- 到期日之外，額外做了簡單的「系統時間回撥」偵測：本機會記住
  看過的最新日期，如果目前系統時間明顯比記錄還早，視為異常
  （常見的規避手法是把電腦時間調回授權到期之前）。

防護等級：跟整體 PyArmor 混淆策略一致——擋得住一般客戶手動
修改到期日、竄改授權內容，不是滴水不漏、防駭客等級的 DRM。
"""

import base64
import json
from datetime import date, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization

# 公鑰本身就是設計成公開的，跟著 modules/ 一起打包給客戶也沒關係——
# 沒有私鑰就無法用這把公鑰反推出能通過驗證的簽章。
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAlMdj2yDe2gO9lDhXOMQTGymlBRmFNk+a2AJMOWpiEiU=
-----END PUBLIC KEY-----
"""

LICENSE_FILE_PATH = "license.lic"
LICENSE_STATE_PATH = "data/.license_state.json"

# 剩餘天數低於這個門檻，畫面上會提醒即將到期。
RENEWAL_WARNING_DAYS = 14

# 系統時間比本機記錄還早幾天以上，視為時間被回撥
# （容忍 1 天，避免時區或系統時鐘微幅漂移誤判）。
CLOCK_ROLLBACK_TOLERANCE_DAYS = 1


def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, ensure_ascii=False
    ).encode("utf-8")


def _verify_license_file(path: str) -> dict:
    license_path = Path(path)

    if not license_path.exists():
        return {
            "valid": False,
            "message": (
                f"找不到授權檔案（{path}），"
                "請聯繫供應商取得授權。"
            ),
        }

    try:
        license_data = json.loads(
            license_path.read_text(encoding="utf-8")
        )
        payload = license_data["payload"]
        signature = base64.b64decode(
            license_data["signature"]
        )

    except Exception as error:
        return {
            "valid": False,
            "message": (
                f"授權檔案格式錯誤或已損毀：{error}"
            ),
        }

    public_key = serialization.load_pem_public_key(
        PUBLIC_KEY_PEM
    )

    try:
        public_key.verify(
            signature,
            _canonical_payload_bytes(payload),
        )

    except InvalidSignature:
        return {
            "valid": False,
            "message": (
                "授權檔案驗證失敗，內容可能遭竄改，"
                "請聯繫供應商重新取得授權。"
            ),
        }

    return {
        "valid": True,
        "payload": payload,
    }


def _load_state(path: str) -> dict:
    state_path = Path(path)

    if not state_path.exists():
        return {}

    try:
        return json.loads(
            state_path.read_text(encoding="utf-8")
        )

    except Exception:
        return {}


def _save_state(path: str, state: dict) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(
        parents=True, exist_ok=True
    )

    state_path.write_text(
        json.dumps(state, ensure_ascii=False),
        encoding="utf-8",
    )


def _invalid_result(
    message: str,
    customer: str | None = None,
    expires_at: str | None = None,
) -> dict:
    return {
        "valid": False,
        "message": message,
        "customer": customer,
        "expires_at": expires_at,
        "days_remaining": None,
    }


def check_license(
    license_path: str = LICENSE_FILE_PATH,
    state_path: str = LICENSE_STATE_PATH,
) -> dict:
    """
    驗證授權檔案，回傳：
        valid: bool
        message: str            # 無效時的原因，有效時是空字串
        customer: str | None
        expires_at: str | None  # YYYY-MM-DD
        days_remaining: int | None
    """

    verification = _verify_license_file(license_path)

    if not verification["valid"]:
        return _invalid_result(verification["message"])

    payload = verification["payload"]
    customer = payload.get("customer", "未知客戶")
    expires_at_text = payload.get("expires_at", "")

    try:
        expires_at = date.fromisoformat(expires_at_text)

    except Exception:
        return _invalid_result(
            "授權檔案內容格式錯誤（到期日無法解析）。",
            customer=customer,
        )

    today = datetime.now().date()

    state = _load_state(state_path)
    last_seen = None
    last_seen_text = state.get("last_seen_date")

    if last_seen_text:
        try:
            last_seen = date.fromisoformat(last_seen_text)

        except Exception:
            last_seen = None

    if (
        last_seen
        and (last_seen - today).days
        > CLOCK_ROLLBACK_TOLERANCE_DAYS
    ):
        return _invalid_result(
            "偵測到系統時間異常（比先前執行時的時間還早），"
            "請確認電腦時間設定正確後再試一次。",
            customer=customer,
            expires_at=expires_at_text,
        )

    newest_seen = (
        max(today, last_seen) if last_seen else today
    )

    _save_state(
        state_path,
        {"last_seen_date": newest_seen.isoformat()},
    )

    days_remaining = (expires_at - today).days

    if days_remaining < 0:
        return _invalid_result(
            f"授權已於 {expires_at_text} 到期，"
            "請聯繫供應商續約。",
            customer=customer,
            expires_at=expires_at_text,
        )

    return {
        "valid": True,
        "message": "",
        "customer": customer,
        "expires_at": expires_at_text,
        "days_remaining": days_remaining,
    }
