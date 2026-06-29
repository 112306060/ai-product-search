import json
from pathlib import Path


CACHE_PATH = Path(
    "data/exhibitions/"
    "cosmoprof_north_america_2026.json"
)


COUNTRY_UPDATES = {
    30035: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "CPNA exhibitor description"
        ),
        "country_evidence": (
            "headquartered in South Korea"
        ),
        "country_confidence": 98,
    },
    31619: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "CPNA exhibitor description"
        ),
        "country_evidence": (
            "K-beauty brand inspired by Seoul"
        ),
        "country_confidence": 90,
    },
    31786: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "CPNA exhibitor description"
        ),
        "country_evidence": (
            "Korean cosmetic OEM/ODM manufacturer"
        ),
        "country_confidence": 98,
    },
    32780: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "CPNA exhibitor description"
        ),
        "country_evidence": (
            "professional Korean K-Beauty company"
        ),
        "country_confidence": 98,
    },
    32975: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "company and brand context"
        ),
        "country_evidence": (
            "W.SKIN LABORATORY / J&J COMPANY"
        ),
        "country_confidence": 75,
    },
    33016: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "CPNA exhibitor description"
        ),
        "country_evidence": (
            "Korean OEM/ODM cosmetics manufacturer"
        ),
        "country_confidence": 98,
    },
    34391: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "CPNA exhibitor description"
        ),
        "country_evidence": (
            "K-beauty manufacturing company "
            "working with Korean OEM/ODM factories"
        ),
        "country_confidence": 95,
    },
    34424: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "CPNA exhibitor description"
        ),
        "country_evidence": (
            "professional lash brand from Korea"
        ),
        "country_confidence": 98,
    },
    34886: {
        "country": "South Korea",
        "country_id": 410,
        "country_source": (
            "company and brand context"
        ),
        "country_evidence": (
            "NIBEC Co., Ltd. / The Klara"
        ),
        "country_confidence": 75,
    },
}


def normalize_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def main():
    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            f"找不到快取：{CACHE_PATH}"
        )

    exhibitors = json.loads(
        CACHE_PATH.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(exhibitors, list):
        raise ValueError(
            "北美快取格式不是 list"
        )

    updated = []
    not_found = set(
        COUNTRY_UPDATES.keys()
    )

    for exhibitor in exhibitors:
        exhibitor_id = normalize_id(
            exhibitor.get("exhibitor_id")
        )

        if exhibitor_id not in COUNTRY_UPDATES:
            continue

        update = COUNTRY_UPDATES[
            exhibitor_id
        ]

        exhibitor.update(update)

        updated.append(
            {
                "id": exhibitor_id,
                "company_name": exhibitor.get(
                    "company_name",
                    "",
                ),
                "country": update["country"],
                "confidence": update[
                    "country_confidence"
                ],
            }
        )

        not_found.discard(
            exhibitor_id
        )

    CACHE_PATH.write_text(
        json.dumps(
            exhibitors,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("=" * 70)
    print("[CPNA 國家補全完成]")
    print("=" * 70)

    for item in updated:
        print(
            f"{item['id']} | "
            f"{item['company_name']} | "
            f"{item['country']} | "
            f"信心 {item['confidence']}"
        )

    print()
    print("成功更新：", len(updated))
    print("找不到 ID：", len(not_found))

    if not_found:
        print()
        print("[找不到的 ID]")

        for exhibitor_id in sorted(
            not_found
        ):
            print("-", exhibitor_id)


if __name__ == "__main__":
    main()