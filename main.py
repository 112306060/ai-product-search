from config import (
    DEFAULT_CONFIG,
    DEFAULT_SEARCH_PROFILE,
)
from modules.search_pipeline import run_search_pipeline


def main():
    run_search_pipeline(
    DEFAULT_CONFIG,
    DEFAULT_SEARCH_PROFILE,
)


if __name__ == "__main__":
    main()