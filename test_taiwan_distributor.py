from modules.taiwan_distributor_checker import check_taiwan_distributor


def main():
    result = check_taiwan_distributor(
        brand_name="Green People",
        official_url="https://www.greenpeople.co.uk",
    )

    print("\n===== Taiwan Distributor Checker Result =====")

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()