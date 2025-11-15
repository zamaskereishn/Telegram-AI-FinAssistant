# parsers.py
from bs4 import BeautifulSoup
import re
from typing import Optional, Dict

# Примитивные селекторы (улучшаешь по мере нужды)
PROVIDER_SELECTORS = {
    "forte.kz": {
        "product_blocks": ".product, .tariff, .offer",
        "title": "h1, h2, .title",
        "rate": ".rate, .percent, .apy",
        "currency": ".currency, .valuta",
        "term": ".term, .duration",
        "min_amount": ".min-amount, .min-sum"
    },
    # Добавь селекторы для halykbank.kz, bcc.kz и т.д.
}

def domain_from_url(url: str) -> str:
    m = re.search(r"https?://(www\.)?([^/]+)", url)
    return m.group(2) if m else ""

def try_structured_parse(html: bytes, url: str) -> Optional[Dict]:
    soup = BeautifulSoup(html, "lxml")
    dom = domain_from_url(url)
    cfg = PROVIDER_SELECTORS.get(dom)
    results = []
    if cfg:
        blocks = soup.select(cfg.get("product_blocks", "article, .offer, .card"))
        for b in blocks:
            title = (b.select_one(cfg["title"]) or b.select_one("h2,h3")).get_text(strip=True) if blocks else None
            rate_el = b.select_one(cfg["rate"])
            rate = rate_el.get_text(strip=True) if rate_el else None
            currency = (b.select_one(cfg["currency"]).get_text(strip=True) if b.select_one(cfg["currency"]) else None)
            term = (b.select_one(cfg["term"]).get_text(strip=True) if b.select_one(cfg["term"]) else None)
            min_s = (b.select_one(cfg["min_amount"]).get_text(strip=True) if b.select_one(cfg["min_amount"]) else None)
            results.append({
                "title": title,
                "rate": rate,
                "currency": currency,
                "term": term,
                "min_amount": min_s,
                "source": url,
                "parser": "selector"
            })
        return results if results else None
    return None
