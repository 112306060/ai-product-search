from pathlib import Path
import pandas as pd

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
    "",
    "後續連絡情況",
    "連絡人資料",
    "來源連結",
]

def export_vendor_records(records: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(records)

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS]
    df.to_excel(output_path, index=False, sheet_name="總表")
