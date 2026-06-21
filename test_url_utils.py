from modules.url_utils import (
    normalize_domain,
    get_main_domain,
    dedupe_urls,
)


def test_normalize_domain():
    assert normalize_domain(
        "https://www.brand.com/products/shampoo"
    ) == "brand.com"

    assert normalize_domain(
        "eu.brand.com"
    ) == "eu.brand.com"


def test_get_main_domain():
    assert get_main_domain(
        "https://eu.brand.com"
    ) == "brand.com"

    assert get_main_domain(
        "https://shop.brand.co.uk/products"
    ) == "brand.co.uk"

    assert get_main_domain(
        "https://www.greenpeople.co.uk"
    ) == "greenpeople.co.uk"


def test_dedupe_urls():
    urls = [
        ("https://brand.com", "Google Search"),
        ("https://www.brand.com/products", "Google Search"),
        ("https://eu.brand.com", "Exhibition"),
        ("https://otherbrand.com", "Google Search"),
    ]

    result = dedupe_urls(urls)

    assert len(result) == 2
    assert result[0][0] == "https://brand.com"
    assert result[1][0] == "https://otherbrand.com"


if __name__ == "__main__":
    test_normalize_domain()
    test_get_main_domain()
    test_dedupe_urls()

    print("PASS | url_utils tests")