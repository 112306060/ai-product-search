from pathlib import Path

from datetime import datetime, timedelta
import pandas as pd
from modules.url_utils import get_main_domain

COLUMNS = [
    "記錄日期",
    "編號",
    "公司名稱",
    "網站",
    "國家",
    "資料來源",
    "商品類別",
    "商品內容",
    "AI分類",
    "是否適合代理",
    "代理推薦分數",
    "AI判斷原因",
    "台灣代理狀態",
    "台灣代理商名稱",
    "台灣代理證據",
    "台灣代理來源",
    "台灣檢查信心分數",
    "評論",
    "後續連絡情況",
    "連絡人資料",
    "來源連結",
]

# 這些欄位可能由公司人員人工填寫。
# 程式更新品牌資料時，不應把人工內容覆蓋掉。
MANUAL_COLUMNS = [
    "後續連絡情況",
    "連絡人資料",
]




def normalize_brand_name(name: str) -> str:
    """
    品牌名稱標準化，作為網域缺失時的備用去重方式。
    """
    if not isinstance(name, str):
        return ""

    return "".join(
        character.lower()
        for character in name.strip()
        if character.isalnum()
    )


def make_brand_key(record: dict) -> str:
    """
    優先使用官方網域建立品牌識別鍵。
    沒有網址時才使用公司名稱。
    """
    website = record.get("網站", "")
    source_url = record.get("來源連結", "")

    domain = get_main_domain(website) or get_main_domain(source_url)

    if domain:
        return f"domain:{domain}"

    brand_name = normalize_brand_name(record.get("公司名稱", ""))

    if brand_name:
        return f"name:{brand_name}"

    return ""


def prepare_dataframe(records: list[dict]) -> pd.DataFrame:
    """
    統一 DataFrame 欄位。
    """
    dataframe = pd.DataFrame(records)

    for column in COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""

    return dataframe[COLUMNS]


def load_existing_records(output_path: str) -> list[dict]:
    """
    讀取既有 Excel 品牌資料。

    Excel 不存在、內容為空或讀取失敗時，回傳空清單。
    """
    path = Path(output_path)

    if not path.exists():
        return []

    try:
        dataframe = pd.read_excel(
            path,
            sheet_name="總表",
            dtype=object,
        )

        dataframe = dataframe.fillna("")

        return dataframe.to_dict(orient="records")

    except Exception as exc:
        print(f"[EXCEL READ FAILED] {output_path}: {exc}")
        return []

def parse_record_date(value) -> datetime | None:
    """
    解析 Excel 內的記錄日期。

    支援：
    20260620
    2026-06-20
    Excel datetime
    """
    if value in ("", None):
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()

    # Excel 可能把整數讀成 20260620.0
    if text.endswith(".0"):
        text = text[:-2]

    date_formats = [
        "%Y%m%d",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y-%m-%d %H:%M:%S",
    ]

    for date_format in date_formats:
        try:
            return datetime.strptime(text, date_format)
        except ValueError:
            continue

    return None


def load_recent_existing_domains(
        output_path: str,
        refresh_days: int = 30,
) -> set[str]:
    """
    讀取 Excel 內近期已分析品牌的網域。

    只有在 refresh_days 內的品牌才會被跳過；
    過期品牌仍可重新分析。
    """
    existing_records = load_existing_records(output_path)

    if not existing_records:
        return set()

    cutoff_date = datetime.now() - timedelta(days=refresh_days)
    recent_domains: set[str] = set()

    for record in existing_records:
        website = record.get("網站", "")
        source_url = record.get("來源連結", "")

        domain = (
            get_main_domain(website)
            or get_main_domain(source_url)
        )

        if not domain:
            continue

        record_date = parse_record_date(
            record.get("記錄日期", "")
        )

        # 舊資料若沒有可解析日期，先視為需要重新分析，
        # 避免錯誤地永久跳過。
        if record_date is None:
            continue

        if record_date >= cutoff_date:
            recent_domains.add(domain)

    return recent_domains
def merge_vendor_records(
        existing_records: list[dict],
        new_records: list[dict],
) -> tuple[list[dict], int, int]:
    """
    合併舊資料與新資料。

    回傳：
    - 合併後資料
    - 新增筆數
    - 更新筆數
    """
    merged_by_key: dict[str, dict] = {}
    key_order: list[str] = []

    # 先放入既有資料。
    for index, record in enumerate(existing_records):
        record_copy = dict(record)
        key = make_brand_key(record_copy)

        # 無法建立識別鍵時，仍保留資料。
        if not key:
            key = f"existing_unknown:{index}"

        if key not in merged_by_key:
            key_order.append(key)

        merged_by_key[key] = record_copy

    added_count = 0
    updated_count = 0

    # 再合併本次新結果。
    for index, new_record in enumerate(new_records):
        new_record_copy = dict(new_record)
        key = make_brand_key(new_record_copy)

        if not key:
            key = f"new_unknown:{index}"

        if key in merged_by_key:
            old_record = merged_by_key[key]

            # 先保留人工欄位。
            manual_values = {
                column: old_record.get(column, "")
                for column in MANUAL_COLUMNS
            }

            # 自動分析欄位以新結果為準。
            old_record.update(new_record_copy)

            # 將人工欄位放回去，避免被空白覆蓋。
            for column, old_value in manual_values.items():
                new_value = new_record_copy.get(column, "")

                if old_value not in ("", None):
                    old_record[column] = old_value
                else:
                    old_record[column] = new_value

            merged_by_key[key] = old_record
            updated_count += 1

        else:
            merged_by_key[key] = new_record_copy
            key_order.append(key)
            added_count += 1

    merged_records = [
        merged_by_key[key]
        for key in key_order
    ]

    # 重新排列編號。
    for index, record in enumerate(merged_records, start=1):
        record["編號"] = index

    return merged_records, added_count, updated_count


def export_vendor_records(
    records: list[dict],
    output_path: str,
    incremental: bool = True,
) -> dict:
    """
    匯出品牌資料。

    incremental=True：
    讀取舊 Excel，合併後再輸出。

    incremental=False：
    僅輸出本次搜尋結果。
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    existing_records = (
        load_existing_records(output_path)
        if incremental
        else []
    )

    merged_records, added_count, updated_count = merge_vendor_records(
        existing_records=existing_records,
        new_records=records,
    )

    dataframe = prepare_dataframe(merged_records)

    dataframe.to_excel(
        output_path,
        index=False,
        sheet_name="總表",
    )

    summary = {
        "本次找到": len(records),
        "新增品牌": added_count,
        "更新品牌": updated_count,
        "資料庫總數": len(merged_records),
    }

    print(
        "[INCREMENTAL EXPORT] "
        f"本次找到 {summary['本次找到']} 筆，"
        f"新增 {summary['新增品牌']} 筆，"
        f"更新 {summary['更新品牌']} 筆，"
        f"總數 {summary['資料庫總數']} 筆"
    )

    return summary