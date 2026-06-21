from dataclasses import dataclass, field


# 地區與國家的對照屬於系統基礎資料，
# 不是固定搜尋條件。
#
# 使用者選擇 Europe 時，系統才會展開這些國家；
# 若使用者沒有選擇地區，就不會套用。
REGION_COUNTRIES: dict[str, set[str]] = {
    "europe": {
        "albania",
        "andorra",
        "austria",
        "belarus",
        "belgium",
        "bosnia and herzegovina",
        "bulgaria",
        "croatia",
        "cyprus",
        "czechia",
        "czech republic",
        "denmark",
        "estonia",
        "finland",
        "france",
        "germany",
        "greece",
        "hungary",
        "iceland",
        "ireland",
        "italy",
        "kosovo",
        "latvia",
        "liechtenstein",
        "lithuania",
        "luxembourg",
        "malta",
        "moldova",
        "monaco",
        "montenegro",
        "netherlands",
        "north macedonia",
        "norway",
        "poland",
        "portugal",
        "romania",
        "san marino",
        "serbia",
        "slovakia",
        "slovenia",
        "spain",
        "sweden",
        "switzerland",
        "ukraine",
        "united kingdom",
        "uk",
        "vatican city",
    },
    "european union": {
        "austria",
        "belgium",
        "bulgaria",
        "croatia",
        "cyprus",
        "czechia",
        "czech republic",
        "denmark",
        "estonia",
        "finland",
        "france",
        "germany",
        "greece",
        "hungary",
        "ireland",
        "italy",
        "latvia",
        "lithuania",
        "luxembourg",
        "malta",
        "netherlands",
        "poland",
        "portugal",
        "romania",
        "slovakia",
        "slovenia",
        "spain",
        "sweden",
    },
    "eu": {
        "austria",
        "belgium",
        "bulgaria",
        "croatia",
        "cyprus",
        "czechia",
        "czech republic",
        "denmark",
        "estonia",
        "finland",
        "france",
        "germany",
        "greece",
        "hungary",
        "ireland",
        "italy",
        "latvia",
        "lithuania",
        "luxembourg",
        "malta",
        "netherlands",
        "poland",
        "portugal",
        "romania",
        "slovakia",
        "slovenia",
        "spain",
        "sweden",
    },
    "asia": {
        "china",
        "hong kong",
        "hong kong,s.a.r.,china",
        "india",
        "indonesia",
        "japan",
        "korea",
        "south korea",
        "malaysia",
        "philippines",
        "singapore",
        "taiwan",
        "taiwan,china",
        "thailand",
        "vietnam",
    },
    "north america": {
        "canada",
        "mexico",
        "united states",
        "usa",
    },
}


@dataclass
class SearchProfile:
    """
    代表一次搜尋任務的動態條件。

    現在可以由 config.py 或測試程式建立；
    未來可以由 Streamlit 使用者介面產生。
    """

    # 使用者原始輸入，例如「歐洲有機天然洗髮精」
    query: str

    # 商品相關關鍵字，例如 shampoo、conditioner
    product_keywords: list[str] = field(
        default_factory=list
    )

    # 品牌定位關鍵字，例如 organic、natural
    positioning_keywords: list[str] = field(
        default_factory=list
    )

    # 使用者指定排除的內容，例如 equipment、packaging
    excluded_keywords: list[str] = field(
        default_factory=list
    )

    # 使用者指定只包含的國家。
    # 空清單代表不限制特定國家。
    included_countries: list[str] = field(
        default_factory=list
    )

    # 使用者指定排除的國家。
    excluded_countries: list[str] = field(
        default_factory=list
    )

    # 使用者指定的地區，例如 Europe、EU。
    # 系統會透過 REGION_COUNTRIES 展開。
    included_regions: list[str] = field(
        default_factory=list
    )

    # 是否要求候選公司必須有官方網站
    require_official_url: bool = True

    # 是否必須符合至少一個商品關鍵字
    require_product_match: bool = True

    # 是否必須符合至少一個定位關鍵字
    require_positioning_match: bool = True

    # 國家資料為空時是否允許保留
    allow_unknown_country: bool = True

    def normalized_product_keywords(self) -> list[str]:
        return normalize_values(
            self.product_keywords
        )

    def normalized_positioning_keywords(
        self,
    ) -> list[str]:
        return normalize_values(
            self.positioning_keywords
        )

    def normalized_excluded_keywords(
        self,
    ) -> list[str]:
        return normalize_values(
            self.excluded_keywords
        )

    def normalized_included_countries(
        self,
    ) -> list[str]:
        return normalize_values(
            self.included_countries
        )

    def normalized_excluded_countries(
        self,
    ) -> list[str]:
        return normalize_values(
            self.excluded_countries
        )

    def normalized_included_regions(
        self,
    ) -> list[str]:
        return normalize_values(
            self.included_regions
        )

    def resolved_included_countries(self) -> set[str]:
        """
        合併使用者直接指定的國家，以及地區展開後的國家。

        例如：
        included_countries=["Italy"]
        included_regions=["Europe"]

        最後會得到 Europe 國家集合加上 Italy。
        """

        countries = set(
            self.normalized_included_countries()
        )

        for region in self.normalized_included_regions():
            region_countries = REGION_COUNTRIES.get(
                region,
                set(),
            )

            countries.update(region_countries)

        return countries


def normalize_values(
    values: list[str],
) -> list[str]:
    """
    將設定值轉為適合比對的格式。

    - 去除前後空白
    - 轉為小寫
    - 排除空字串
    - 去除重複值
    """

    normalized = []

    for value in values:
        cleaned = str(value).strip().lower()

        if not cleaned:
            continue

        if cleaned not in normalized:
            normalized.append(cleaned)

    return normalized