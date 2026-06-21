from config import DEFAULT_CONFIG
from modules.search_pipeline import run_search_pipeline


def main():
    run_search_pipeline(DEFAULT_CONFIG)


if __name__ == "__main__":
    main()