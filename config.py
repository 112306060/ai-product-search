from dataclasses import dataclass, field


@dataclass
class SearchConfig:
    product: str = "shampoo"
    region: str = "EU"
    target_count: int = 20

    # True：少量測試，節省 API 額度
    # False：正式搜尋
    

    
    test_mode: bool = True
    check_taiwan_distributor: bool = True
    force_refresh_taiwan: bool = False
    taiwan_cache_days: int = 7
    
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