from modules.search_engine import search_web

EXHIBITION_QUERIES = [
    '"Cosmoprof" "hair care" "official website"',
    '"Cosmoprof" "shampoo" "brand"',
    '"Cosmoprof Bologna" "professional hair care"',
    '"Cosmoprof Asia" "hair care brand"',
    '"Cosmoprof" "organic cosmetics" "brand"',
    '"Cosmopack" "private label" "hair care"',
    '"Cosmopack" "OEM" "cosmetics manufacturer"',
    '"Beautyworld" "hair care brand"',
    '"Beautyworld" "natural cosmetics" "brand"',
]

def search_exhibition_sources(    exclude_domains,    num_results=5,    test_mode=False,):
    exhibition_block_domains = [
        "cosmoprof.com",
        "cosmoprofnorthamerica.com",
        "cosmoprof-asia.com",
        "cosmoprofindia.com",
        "cosmoprofbeauty.com",
        "beautyworld.",
        "messefrankfurt.com",
        "facebook.com",
        "instagram.com",
        "scribd.com",
        "bizprospex.com",
        "exhibitorsdata.com",
        "expocaptive.com",
        "packaging-labelling.com",
        "glossy.co",
    ]
    queries = EXHIBITION_QUERIES[:2] if test_mode else EXHIBITION_QUERIES
    urls = []

    for query in queries:
        print(f"[EXHIBITION] {query}")

        results = search_web(
            query=query,
            exclude_domains=exclude_domains + exhibition_block_domains,
            num_results=num_results,
        )

        urls.extend(results)

    return list(dict.fromkeys(urls))