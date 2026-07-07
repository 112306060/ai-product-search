"""
依照使用者本次搜尋的國家／地區條件，
動態決定要用哪些語言搜尋、以及嘗試的先後順序。

不再使用 config.py 裡固定的語言清單——
搜尋日本就該用日文，搜尋義大利就不用浪費關鍵字名額在瑞典文。
"""

from modules.search_profile import SearchProfile


# 每個國家對應的主要商用語言。
# 為了讓翻譯與快取邏輯單純，這裡刻意每個國家只挑一個
# 最實用的主要語言（小國/多語言國家取最普遍用於
# 商業內容的語言，而不是列出所有官方語言）。
COUNTRY_LANGUAGES: dict[str, str] = {
    # Europe
    "albania": "albanian",
    "andorra": "spanish",
    "austria": "german",
    "belarus": "russian",
    "belgium": "dutch",
    "bosnia and herzegovina": "bosnian",
    "bulgaria": "bulgarian",
    "croatia": "croatian",
    "cyprus": "greek",
    "czechia": "czech",
    "czech republic": "czech",
    "denmark": "danish",
    "estonia": "estonian",
    "finland": "finnish",
    "france": "french",
    "germany": "german",
    "greece": "greek",
    "hungary": "hungarian",
    "iceland": "icelandic",
    "ireland": "english",
    "italy": "italian",
    "kosovo": "albanian",
    "latvia": "latvian",
    "liechtenstein": "german",
    "lithuania": "lithuanian",
    "luxembourg": "french",
    "malta": "english",
    "moldova": "romanian",
    "monaco": "french",
    "montenegro": "serbian",
    "netherlands": "dutch",
    "north macedonia": "macedonian",
    "norway": "norwegian",
    "poland": "polish",
    "portugal": "portuguese",
    "romania": "romanian",
    "san marino": "italian",
    "serbia": "serbian",
    "slovakia": "slovak",
    "slovenia": "slovenian",
    "spain": "spanish",
    "sweden": "swedish",
    "switzerland": "german",
    "ukraine": "ukrainian",
    "united kingdom": "english",
    "uk": "english",
    "vatican city": "italian",
    # Asia
    "china": "chinese",
    "hong kong": "chinese",
    "hong kong,s.a.r.,china": "chinese",
    "india": "english",
    "indonesia": "indonesian",
    "japan": "japanese",
    "korea": "korean",
    "south korea": "korean",
    "malaysia": "english",
    "philippines": "english",
    "singapore": "english",
    "taiwan": "chinese",
    "taiwan,china": "chinese",
    "thailand": "thai",
    "vietnam": "vietnamese",
    # North America
    "canada": "english",
    "mexico": "spanish",
    "united states": "english",
    "usa": "english",
}


# 沒有指定國家/地區、或無法辨識國家時的預設語言，
# 至少能搜到國際通用內容。
DEFAULT_LANGUAGE = "english"


def resolve_search_languages(
    profile: SearchProfile,
) -> list[str]:
    """
    依照本次搜尋條件解析出的國家清單，
    回傳依「涵蓋國家數」排序的語言優先清單。

    語言涵蓋的國家數越多（例如同地區內好幾個國家
    都說同一種語言），排序越前面；English 永遠排第一，
    因為是國際商用共通語言，不論搜哪裡都有意義。
    """

    countries = (
        profile.resolved_included_countries()
    )

    if not countries:
        return [DEFAULT_LANGUAGE]

    language_country_counts: dict[
        str, int
    ] = {}

    for country in countries:
        language = COUNTRY_LANGUAGES.get(
            country
        )

        if not language:
            continue

        language_country_counts[
            language
        ] = (
            language_country_counts.get(
                language,
                0,
            )
            + 1
        )

    ranked_languages = sorted(
        language_country_counts.keys(),
        key=lambda language: (
            -language_country_counts[
                language
            ],
            language,
        ),
    )

    languages = [DEFAULT_LANGUAGE]

    for language in ranked_languages:
        if language not in languages:
            languages.append(language)

    return languages
