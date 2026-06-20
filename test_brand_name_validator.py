from modules.brand_name_validator import validate_brand_name


test_cases = [
    ("Eu", "https://eu.oserth.com", "Oserth"),
    ("Greenpeople", "https://www.greenpeople.co.uk", "Green People"),
    ("Muehle Shaving", "https://muehle-shaving.com", "MÜHLE"),
    ("100percentpure", "https://www.100percentpure.com", "100% PURE"),
    ("Paulmitchell", "https://www.paulmitchell.com", "Paul Mitchell"),
]


for proposed_name, url, expected in test_cases:
    result = validate_brand_name(
        proposed_name=proposed_name,
        url=url,
    )

    status = "PASS" if result == expected else "FAIL"

    print(
        f"{status} | "
        f"{url} | "
        f"{proposed_name} -> {result} | "
        f"expected: {expected}"
    )