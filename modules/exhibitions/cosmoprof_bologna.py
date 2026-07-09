import json
from pathlib import Path


EVENT_NAME = "Cosmoprof Worldwide Bologna"
EVENT_YEAR = 2026

CATALOG_PATH = Path(
    "data/exhibitions/cosmoprof_bologna_2026.json"
)


def load_bologna_catalog() -> dict:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"找不到 Bologna 官方資料：{CATALOG_PATH}\n"
            "請先執行：\n"
            "python sync_bologna_catalog.py\n"
            "python update_bologna_details.py"
        )

    return json.loads(
        CATALOG_PATH.read_text(
            encoding="utf-8"
        )
    )


def join_values(values) -> str:
    if isinstance(values, list):
        return " / ".join(
            str(value).strip()
            for value in values
            if str(value).strip()
        )

    return str(values or "").strip()


def normalize_exhibitor(raw: dict) -> dict:
    company_name = str(
        raw.get("company_name", "")
    ).strip()

    country = str(
        raw.get("country", "")
    ).strip()

    detail_url = str(
        raw.get("detail_url", "")
    ).strip()

    category_names = raw.get(
        "category_names",
        [],
    )

    product_category = join_values(
        category_names
    )

    hall = str(
        raw.get("hall", "")
    ).strip()

    stand = str(
        raw.get("stand", "")
    ).strip()

    booth_parts = []

    if hall:
        booth_parts.append(
            f"Hall {hall}"
        )

    if stand:
        booth_parts.append(
            f"Stand {stand}"
        )

    booth = " / ".join(
        booth_parts
    )

    sector = str(
        raw.get("detail_sector")
        or raw.get("sector")
        or ""
    ).strip()

    activity_sector = str(
        raw.get("activity_sector", "")
    ).strip()

    exhibiting_area = str(
        raw.get("exhibiting_area", "")
    ).strip()

    opening_dates = str(
        raw.get("opening_dates", "")
    ).strip()

    description_parts = []

    # 分類清單本身已經另外放在 product_category
    # 欄位（給商品/定位比對用），這裡刻意不重複塞入
    # description，避免一家公司只要「同時掛在」某個
    # 排除分類底下（例如兼做包材/指甲），就讓 description
    # 也帶有那個詞，導致排除詞判斷誤判整家排除。
    #
    # exhibiting_area 同樣刻意不放進 description：
    # 這是展區/場館名稱（例如「COSMO HAIR & NAIL &
    # BEAUTY SALON」把美髮、美甲、美容沙龍歸在同一展區），
    # 不是這家公司自己的產品描述，同一展區裡的公司可能
    # 產品完全不同，放進 description 只會誤導排除詞判斷。
    if sector:
        description_parts.append(
            "Sector: "
            + sector
        )

    if activity_sector:
        description_parts.append(
            "Activity sector: "
            + activity_sector
        )

    if opening_dates:
        description_parts.append(
            "Opening dates: "
            + opening_dates
        )

    description = "\n".join(
        description_parts
    )

    return {
        "company_name": company_name,
        "country": country,

        # Bologna 公開頁目前沒有公司官網，
        # 先使用官方 detail page 進入主流程。
        # 若官網爬不到內容，search_pipeline 會使用展覽描述 fallback。
        "official_url": detail_url,

        "product_category": product_category,
        "exhibitor_type": sector,
        "description": description,
        "booth": booth,
        "exhibitor_id": detail_url,
        "exhibition": EVENT_NAME,
        "exhibition_year": EVENT_YEAR,
        "source": f"{EVENT_NAME} {EVENT_YEAR}",
        "source_url": detail_url,

        "bologna_category_codes": raw.get(
            "category_codes",
            [],
        ),
        "bologna_category_names": raw.get(
            "category_names",
            [],
        ),
        "bologna_hall": hall,
        "bologna_stand": stand,
        "bologna_detail_url": detail_url,
        "bologna_exhibiting_area": exhibiting_area,
        "bologna_opening_dates": opening_dates,
    }


def get_all_exhibitors() -> list[dict]:
    catalog = load_bologna_catalog()

    raw_exhibitors = catalog.get(
        "exhibitors",
        [],
    )

    exhibitors = [
        normalize_exhibitor(raw)
        for raw in raw_exhibitors
    ]

    print(
        "[COSMOPROF BOLOGNA] "
        f"讀取 {len(exhibitors)} 家官方展商"
    )

    return exhibitors


if __name__ == "__main__":
    exhibitors = get_all_exhibitors()

    print()
    print("[FIRST 5 BOLOGNA EXHIBITORS]")

    for item in exhibitors[:5]:
        print("-" * 80)
        print("公司：", item["company_name"])
        print("國家：", item["country"])
        print("分類：", item["product_category"])
        print("攤位：", item["booth"])
        print("來源：", item["official_url"])