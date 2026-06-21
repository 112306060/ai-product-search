from dataclasses import dataclass, field


@dataclass
class SearchConfig:
    product: str = "有機天然洗髮精"
    region: str = "歐盟"
    target_count: int = 10

    # True：少量測試，節省 API 額度
    # False：正式搜尋
    

    
    test_mode: bool = False
    check_taiwan_distributor: bool = True
    force_refresh_taiwan: bool = False
    taiwan_cache_days: int = 7
    # 是否跳過近期已分析的品牌
    skip_existing_brands: bool = True

    # 品牌基礎分析多久重新執行一次
    brand_refresh_days: int = 30

    # 強制重新分析所有搜尋到的品牌
    force_refresh_brands: bool = False
    languages: list[str] = field(
        default_factory=lambda: [
            "English",
            "Italian",
            "French",
            "German",
            "Spanish",
            "Dutch",
            "Polish",
            "Swedish",
        ]
    )

    exclude_domains: list[str] = field(
        default_factory=lambda: [
            "amazon.",
            "alibaba.",
            "temu.",
            "shopee.",
            "momo.",
            "pchome.",
            "ebay.",
        ]
    )

    output_path: str = "data/output.xlsx"


DEFAULT_CONFIG = SearchConfig()