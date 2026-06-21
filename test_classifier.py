from modules.search_profile import SearchProfile
from modules.website_classifier import (
    classify_website,
)


profile = SearchProfile(
    query="歐洲有機天然洗髮精",
    product_keywords=[
        "shampoo",
        "conditioner",
        "hair care",
    ],
    positioning_keywords=[
        "organic",
        "natural",
    ],
    included_regions=[
        "Europe",
    ],
)

sample_text = """
Green People is a British natural and organic beauty brand.
We produce organic shampoo and natural hair care products.
"""

result = classify_website(
    url="https://greenpeople.eu",
    page_text=sample_text,
    search_profile=profile,
)

print(result)