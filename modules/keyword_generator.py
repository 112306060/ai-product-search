def generate_keywords(product: str, region: str, languages: list[str]) -> list[str]:
    """
    MVP先用固定規則產生關鍵字。
    之後可改成呼叫AI自動生成。
    """
    keywords = [
        "organic shampoo Europe",
        "natural shampoo Europe",
        "professional salon shampoo Europe",
        "organic hair care brand Europe",
        "natural hair care brand Europe",
        "PIF cosmetic shampoo Europe",
        "EU cosmetic regulation shampoo brand",
        "organic shampoo manufacturer Europe",
        "private label organic shampoo Europe",

        # Italian
        "shampoo biologico professionale Italia",
        "shampoo naturale professionale Italia",

        # French
        "shampooing bio professionnel France",
        "shampooing naturel salon France",

        # German
        "Bio Shampoo Hersteller Deutschland",
        "Natur Shampoo professionell Deutschland",

        # Spanish
        "champú orgánico profesional España",
        "champú natural profesional España",

        # Dutch
        "biologische shampoo professioneel Nederland",
        "natuurlijke shampoo merk Nederland",
    ]
    return keywords
