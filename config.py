from dataclasses import dataclass, field

@dataclass
class SearchConfig:
    product: str = "shampoo"
    region: str = "EU"
    target_count: int = 20
    languages: list[str] = field(default_factory=lambda: [
        "English", "Italian", "French", "German", "Spanish", "Dutch", "Polish", "Swedish"
    ])
    exclude_domains: list[str] = field(default_factory=lambda: [
        "amazon.", "alibaba.", "temu.", "shopee.", "momo.", "pchome.", "ebay."
    ])
    output_path: str = "data/output.xlsx"

DEFAULT_CONFIG = SearchConfig()
