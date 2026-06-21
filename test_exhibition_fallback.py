import modules.search_pipeline as search_pipeline
from modules.search_profile import SearchProfile


def test_exhibition_fallback():
    profile = SearchProfile(
        query="歐洲有機天然洗髮精",
        product_keywords=[
            "shampoo",
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

    source_metadata = {
        "展覽名稱": "Cosmoprof Asia",
        "展覽年份": 2025,
        "展覽攤位": "TEST-A1",
        "展覽公司名稱": "Fallback Test Brand",
        "展覽商品分類": (
            "Hair Care Products & Treatment,"
            "Natural Cosmetics"
        ),
        "展覽參展類型": (
            "Perfumery, cosmetics and toiletries"
        ),
        "展覽來源頁面": (
            "https://example.com/exhibition"
        ),
        "展覽國家": "FRANCE",
    }

    original_fetch = (
        search_pipeline.fetch_website_text
    )

    try:
        # 強制模擬官網讀取失敗。
        search_pipeline.fetch_website_text = (
            lambda url: ""
        )

        records = search_pipeline.build_records(
            urls_with_source=[
                (
                    "https://fallback-test.example",
                    "Cosmoprof Asia 2025",
                    source_metadata,
                )
            ],
            start_index=1,
            max_count=1,
            search_profile=profile,
            check_taiwan=False,
            existing_domains=set(),
            skip_existing_brands=False,
        )

    finally:
        search_pipeline.fetch_website_text = (
            original_fetch
        )

    assert len(records) == 1

    record = records[0]

    assert (
        record["公司名稱"]
        == "Fallback Test Brand"
    )

    assert record["國家"] == "FRANCE"

    assert (
        record["展覽名稱"]
        == "Cosmoprof Asia"
    )

    assert (
        record["AI分類"]
        == "待人工確認"
    )

    assert (
        record["是否適合代理"]
        == "待確認"
    )

    assert (
        record["台灣代理狀態"]
        == "未執行"
    )

    print(
        "All exhibition fallback tests passed."
    )


if __name__ == "__main__":
    test_exhibition_fallback()

