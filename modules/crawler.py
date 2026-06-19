import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 AI product search research tool"
}

def fetch_website_text(url: str, max_chars: int = 12000) -> str:
    """
    讀取網頁文字。
    第一版只讀取該URL頁面；第二版可延伸讀取 About / Product / Contact 頁。
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[crawler failed] {url}: {exc}")
        return ""

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    text = soup.get_text("\n")
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()

    return text[:max_chars]
