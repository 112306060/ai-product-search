import json
import re
import unicodedata
from pathlib import Path


DEFAULT_METADATA_PATH = Path(
    "data/exhibitions/"
    "cosmoprof_north_america_2026_metadata.json"
)


QUERY_ALIASES = {
    "洗髮精": [
        "shampoo",
        "shampoos",
        "conditioner",
        "conditioners",
        "hair care",
    ],
    "洗髮": [
        "shampoo",
        "shampoos",
        "hair care",
    ],
    "護髮": [
        "conditioner",
        "conditioners",
        "hair care",
        "hair treatment",
    ],
    "髮品": [
        "hair care",
        "haircare",
        "hair products",
    ],
    "頭髮": [
        "hair care",
        "haircare",
    ],
    "沐浴精": [
        "body wash",
        "body cleanser",
        "cleansing",
        "bath",
        "body care",
    ],
    "沐浴乳": [
        "body wash",
        "body cleanser",
        "bath",
        "body care",
    ],
    "身體清潔": [
        "body wash",
        "body cleanser",
        "cleansing",
        "body care",
    ],
    "身體保養": [
        "body care",
        "body treatment",
        "skin care",
    ],
    "護膚": [
        "skin care",
        "skincare",
        "facial care",
    ],
    "保養品": [
        "skin care",
        "skincare",
        "beauty products",
    ],
    "臉部": [
        "face care",
        "facial care",
        "skin care",
    ],
    "彩妝": [
        "makeup",
        "make-up",
        "color cosmetics",
    ],
    "香水": [
        "fragrance",
        "perfume",
        "perfumery",
    ],
    "指甲": [
        "nail",
        "nails",
        "nail care",
    ],
    "美甲": [
        "nail",
        "nails",
        "nail care",
    ],
    "精油": [
        "essential oils",
        "plant extracts",
        "aromatherapy",
    ],
    "天然": [
        "natural",
        "bio",
    ],
    "有機": [
        "organic",
        "bio",
    ],
    "純素": [
        "vegan",
    ],
    "無動物實驗": [
        "cruelty-free",
        "cruelty free",
    ],
    "清真": [
        "halal",
    ],
    "代工": [
        "contract manufacturing",
        "private label",
        "manufacturer",
        "manufacturing",
        "oem",
        "odm",
    ],
    "oem": [
        "oem",
        "contract manufacturing",
        "private label",
        "manufacturer",
    ],
    "odm": [
        "odm",
        "contract manufacturing",
        "private label",
        "manufacturer",
    ],
    "自有品牌": [
        "private label",
        "brand",
    ],
    "包材": [
        "packaging",
        "packaging materials",
        "containers",
    ],
    "原料": [
        "ingredients",
        "raw materials",
        "plant extracts",
    ],
}


GENERIC_WORDS = {
    "and",
    "or",
    "the",
    "of",
    "for",
    "in",
    "products",
    "product",
    "services",
    "service",
    "beauty",
    "cosmetic",
    "cosmetics",
}


WEAK_SHARED_TOKENS = {
    "care",
    "treatment",
}


POSITIONING_CATEGORY_KEYWORDS = {
    "natural",
    "vegan",
    "bio",
    "halal",
    "cruelty free",
    "cruelty-free",
    "organic",
}


MANUFACTURING_CATEGORY_KEYWORDS = {
    "contract",
    "private label",
    "manufacturer",
    "manufacturing",
    "oem",
    "odm",
}


RAW_MATERIAL_CATEGORY_KEYWORDS = {
    "ingredients",
    "raw materials",
    "essential oils",
    "plant extracts",
    "packaging",
}


def normalize_text(value) -> str:
    text = unicodedata.normalize(
        "NFKC",
        str(value or ""),
    )

    text = text.casefold()

    text = re.sub(
        r"[^a-z0-9\u4e00-\u9fff]+",
        " ",
        text,
    )

    return " ".join(
        text.split()
    )


def tokenize(value) -> set[str]:
    return {
        word
        for word in normalize_text(
            value
        ).split()
        if word
        and word not in GENERIC_WORDS
    }


def load_metadata(
    metadata_path: str | Path = (
        DEFAULT_METADATA_PATH
    ),
) -> dict:
    path = Path(metadata_path)

    if not path.exists():
        raise FileNotFoundError(
            "找不到 CPNA metadata："
            f"{path}\n"
            "請先執行 python sync_cpna_catalog.py"
        )

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as error:
        raise RuntimeError(
            "CPNA metadata 不是有效 JSON"
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError(
            "CPNA metadata 最外層必須是 dict"
        )

    return payload


def get_business_areas(
    metadata: dict,
) -> list[dict]:
    raw_areas = (
        metadata.get("business_areas")
        or []
    )

    output = []

    for item in raw_areas:
        if not isinstance(item, dict):
            continue

        category_id = item.get("id")
        category_name = str(
            item.get("name")
            or ""
        ).strip()

        if (
            category_id is None
            or not category_name
        ):
            continue

        output.append(
            {
                "id": category_id,
                "name": category_name,
                "parent_id": item.get(
                    "parent_id"
                ),
            }
        )

    return output


def expand_query_terms(
    query: str,
) -> list[str]:
    normalized_query = normalize_text(
        query
    )

    terms = {
        normalized_query,
    }

    for alias, expansions in (
        QUERY_ALIASES.items()
    ):
        normalized_alias = normalize_text(
            alias
        )

        if (
            normalized_alias
            and normalized_alias
            in normalized_query
        ):
            terms.update(
                normalize_text(term)
                for term in expansions
            )

    terms.update(
        tokenize(normalized_query)
    )

    return sorted(
        term
        for term in terms
        if term
    )


def classify_category_role(
    category_name: str,
) -> str:
    normalized_name = normalize_text(
        category_name
    )

    if any(
        keyword in normalized_name
        for keyword
        in POSITIONING_CATEGORY_KEYWORDS
    ):
        return "positioning"

    if any(
        keyword in normalized_name
        for keyword
        in MANUFACTURING_CATEGORY_KEYWORDS
    ):
        return "manufacturing"

    if any(
        keyword in normalized_name
        for keyword
        in RAW_MATERIAL_CATEGORY_KEYWORDS
    ):
        return "supply_chain"

    return "product"


def score_category(
    category_name: str,
    query_terms: list[str],
) -> tuple[int, list[str]]:
    normalized_category = normalize_text(
        category_name
    )

    category_tokens = tokenize(
        category_name
    )

    score = 0
    reasons = []

    for term in query_terms:
        normalized_term = normalize_text(
            term
        )

        if not normalized_term:
            continue

        term_tokens = tokenize(
            normalized_term
        )

        if normalized_term == (
            normalized_category
        ):
            score += 100
            reasons.append(
                f"exact:{term}"
            )
            continue

        if normalized_term in (
            normalized_category
        ):
            phrase_length = len(
                normalized_term.split()
            )

            score += (
                45
                if phrase_length >= 2
                else 25
            )

            reasons.append(
                f"phrase:{term}"
            )

        # 官方分類名稱有時候會把片語黏在一起寫
        # （例如 "Haircare" vs 我們展開的 "hair care"），
        # 純粹只是有沒有空格的差異，語意上完全相同，
        # 這裡另外做去除空格後的比對，避免漏掉這種分類。
        elif normalized_term.replace(
            " ", ""
        ) == normalized_category.replace(
            " ", ""
        ):
            score += 45

            reasons.append(
                f"phrase_no_space:{term}"
            )

        shared_tokens = (
            term_tokens
            & category_tokens
        )

        meaningful_shared_tokens = (
            shared_tokens
            - WEAK_SHARED_TOKENS
        )

        if meaningful_shared_tokens:
            token_score = (
                len(
                    meaningful_shared_tokens
                )
                * 12
            )

            score += token_score

            reasons.append(
                "tokens:"
                + ",".join(
                    sorted(
                        meaningful_shared_tokens
                    )
                )
            )

        if (
            term_tokens
            and term_tokens.issubset(
                category_tokens
            )
            and not term_tokens.issubset(
                WEAK_SHARED_TOKENS
            )
        ):
            score += 20
            reasons.append(
                f"all_tokens:{term}"
            )

    return score, reasons


def match_business_areas(
    query: str,
    metadata_path: str | Path = (
        DEFAULT_METADATA_PATH
    ),
    *,
    min_score: int = 20,
    max_results: int = 10,
) -> list[dict]:
    metadata = load_metadata(
        metadata_path
    )

    business_areas = get_business_areas(
        metadata
    )

    query_terms = expand_query_terms(
        query
    )

    matches = []

    for category in business_areas:
        score, reasons = score_category(
            category_name=(
                category["name"]
            ),
            query_terms=query_terms,
        )

        if score < min_score:
            continue

        matches.append(
            {
                **category,
                "score": score,
                "reasons": reasons,
                "role": (
                    classify_category_role(
                        category["name"]
                    )
                ),
            }
        )

    matches.sort(
        key=lambda item: (
            -item["score"],
            normalize_text(
                item["name"]
            ),
        )
    )

    return matches[:max_results]


def get_matched_business_area_ids(
    query: str,
    metadata_path: str | Path = (
        DEFAULT_METADATA_PATH
    ),
    *,
    min_score: int = 20,
    max_results: int = 10,
) -> list[int]:
    matches = match_business_areas(
        query=query,
        metadata_path=metadata_path,
        min_score=min_score,
        max_results=max_results,
    )

    output = []

    for match in matches:
        category_id = match.get("id")

        try:
            normalized_id = int(
                category_id
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if normalized_id not in output:
            output.append(
                normalized_id
            )

    return output


def get_api_business_area_matches(
    query: str,
    metadata_path: str | Path = (
        DEFAULT_METADATA_PATH
    ),
    *,
    min_score: int = 35,
    max_results: int = 5,
) -> list[dict]:
    """
    取得適合直接傳給 CPNA API 的主要分類。

    規則：
    1. positioning 不直接傳入 API。
    2. OEM、ODM、代工需求才允許 manufacturing。
    3. Men's 分類只有明確要求男士產品時才加入。
    4. Other 分類只有沒有更明確分類時才作為備用。
    5. 父分類與明確子分類可同時保留。
    """
    matches = match_business_areas(
        query=query,
        metadata_path=metadata_path,
        min_score=min_score,
        max_results=30,
    )

    normalized_query = normalize_text(
        query
    )

    wants_manufacturer = any(
        keyword in normalized_query
        for keyword in [
            "oem",
            "odm",
            "代工",
            "private label",
            "manufacturer",
            "manufacturing",
        ]
    )

    wants_mens = any(
        keyword in normalized_query
        for keyword in [
            "男士",
            "男性",
            "男用",
            "men",
            "mens",
            "men s",
            "male",
        ]
    )

    allowed_roles = {
        "product",
    }

    if wants_manufacturer:
        allowed_roles.add(
            "manufacturing"
        )

    regular_matches = []
    other_matches = []

    for match in matches:
        role = match.get("role")

        if role not in allowed_roles:
            continue

        normalized_name = normalize_text(
            match.get("name", "")
        )

        # 沒有明確要求男士產品時，
        # 不加入 Men's Hair Care、Men's Skin Care。
        if (
            normalized_name.startswith(
                "men s "
            )
            or normalized_name.startswith(
                "mens "
            )
        ):
            if not wants_mens:
                continue

        # Other Hair Care、Other Skin Care
        # 只當作沒有明確分類時的備用選項。
        if normalized_name.startswith(
            "other "
        ):
            other_matches.append(
                match
            )
            continue

        regular_matches.append(
            match
        )

    selected = (
        regular_matches
        if regular_matches
        else other_matches
    )

    return selected[:max_results]

def get_api_business_area_ids(
    query: str,
    metadata_path: str | Path = (
        DEFAULT_METADATA_PATH
    ),
    *,
    min_score: int = 35,
    max_results: int = 5,
) -> list[int]:
    """
    回傳適合直接傳入 CPNA business_area 的 ID。
    """
    matches = get_api_business_area_matches(
        query=query,
        metadata_path=metadata_path,
        min_score=min_score,
        max_results=max_results,
    )

    selected = []

    for match in matches:
        category_id = match.get("id")

        try:
            normalized_id = int(
                category_id
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        if normalized_id not in selected:
            selected.append(
                normalized_id
            )

    return selected


def get_positioning_matches(
    query: str,
    metadata_path: str | Path = (
        DEFAULT_METADATA_PATH
    ),
    *,
    min_score: int = 20,
    max_results: int = 10,
) -> list[dict]:
    """
    取得天然、有機、純素、Halal 等定位分類。

    這些分類主要供後續 OpenAI 分析與文字篩選參考，
    不直接跟產品分類一起傳入官方 API。
    """
    matches = match_business_areas(
        query=query,
        metadata_path=metadata_path,
        min_score=min_score,
        max_results=30,
    )

    output = [
        match
        for match in matches
        if match.get("role")
        == "positioning"
    ]

    return output[:max_results]


def get_supply_chain_matches(
    query: str,
    metadata_path: str | Path = (
        DEFAULT_METADATA_PATH
    ),
    *,
    min_score: int = 20,
    max_results: int = 10,
) -> list[dict]:
    """
    取得原料、包材、精油、植物萃取等供應鏈分類。
    """
    matches = match_business_areas(
        query=query,
        metadata_path=metadata_path,
        min_score=min_score,
        max_results=30,
    )

    output = [
        match
        for match in matches
        if match.get("role")
        == "supply_chain"
    ]

    return output[:max_results]


def print_matches(
    query: str,
    matches: list[dict],
) -> None:
    print()
    print("=" * 72)
    print(
        f"[CPNA CATEGORY MATCH] {query}"
    )
    print("=" * 72)

    if not matches:
        print("找不到符合的官方分類")
        return

    for index, match in enumerate(
        matches,
        start=1,
    ):
        print(
            f"{index}. "
            f"{match['name']} "
            f"(ID={match['id']}, "
            f"score={match['score']}, "
            f"role={match['role']})"
        )

        if match["reasons"]:
            print(
                "   ",
                "；".join(
                    match["reasons"]
                ),
            )


def print_api_selection(
    query: str,
) -> None:
    api_matches = (
        get_api_business_area_matches(
            query=query,
            min_score=35,
            max_results=5,
        )
    )

    positioning_matches = (
        get_positioning_matches(
            query=query,
            min_score=20,
            max_results=5,
        )
    )

    supply_chain_matches = (
        get_supply_chain_matches(
            query=query,
            min_score=20,
            max_results=5,
        )
    )

    print()
    print(
        "[傳給 CPNA 官方 API]"
    )

    if api_matches:
        for match in api_matches:
            print(
                f"- {match['name']} "
                f"(ID={match['id']})"
            )
    else:
        print("- 無")

    print()
    print(
        "[保留給後續定位分析]"
    )

    if positioning_matches:
        for match in positioning_matches:
            print(
                f"- {match['name']} "
                f"(ID={match['id']})"
            )
    else:
        print("- 無")

    print()
    print(
        "[供應鏈相關分類]"
    )

    if supply_chain_matches:
        for match in supply_chain_matches:
            print(
                f"- {match['name']} "
                f"(ID={match['id']})"
            )
    else:
        print("- 無")


if __name__ == "__main__":
    test_queries = [
        "有機天然洗髮精",
        "沐浴精",
        "護膚品",
        "純素保養品",
        "OEM ODM 代工",
        "精油與植物萃取",
        "美甲產品",
    ]

    for test_query in test_queries:
        results = match_business_areas(
            query=test_query,
            min_score=20,
            max_results=8,
        )

        print_matches(
            query=test_query,
            matches=results,
        )

        print_api_selection(
            query=test_query,
        )