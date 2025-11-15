import requests, time, re
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from loguru import logger
from config import config
from utils import clean_html, truncate_text, validate_url

class FinancialScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; FinBot/1.0; +https://example.com/bot)'
        })
        self.timeout = config.REQUEST_TIMEOUT
        self.max_retries = config.MAX_RETRIES
        self.delay = config.SCRAPE_DELAY

    def _make_request(self, url, retries=0):
        try:
            r = self.session.get(url, timeout=self.timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            if retries < self.max_retries:
                time.sleep(2 ** retries)
                return self._make_request(url, retries+1)
            logger.error(f"Failed {url}: {e}")
            return None

    def extract_text(self, html_content):
        soup = BeautifulSoup(html_content, 'lxml')
        # Удаляем скрипты и стили
        for s in soup(['script','style','noscript']):
            s.decompose()
        # Берём основной текст — heuristics: article > main > div
        candidate = soup.find('article') or soup.find('main') or soup.body
        text = candidate.get_text(separator='\n', strip=True) if candidate else soup.get_text(separator='\n', strip=True)
        text = clean_html(text)
        # Нормализация пробелов
        text = re.sub(r'\n{2,}', '\n\n', text).strip()
        return text

    def scrape_url(self, url: str) -> Optional[Dict]:
        if not validate_url(url):
            url = 'http://' + url  # попытаемся поправить
        response = self._make_request(url)
        if not response:
            return None
        text = self.extract_text(response.content)
        title = ''
        try:
            soup = BeautifulSoup(response.content, 'lxml')
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
        except:
            pass
        # Обрезаем слишком длинный raw (чтобы не сломать LLM)
        if len(text) > 20000:
            text = text[:20000]  # начальный guard, всё равно будем чанкать
        return {
            'url': url,
            'title': title,
            'text': text,
        }

    def scrape_many(self, urls: List[str]) -> List[Dict]:
        out = []
        for u in urls:
            logger.info(f"Scraping {u}")
            item = self.scrape_url(u)
            if item:
                out.append(item)
            time.sleep(self.delay)
        return out

    @staticmethod
    def chunk_text(text: str, max_chars: int = 3000) -> List[str]:
        """Разбивка на чанки без порчи слов"""
        if not text:
            return []
        parts = []
        while len(text) > max_chars:
            cut = text.rfind('\n', 0, max_chars)
            if cut <= 0:
                cut = max_chars
            parts.append(text[:cut].strip())
            text = text[cut:].strip()
        if text:
            parts.append(text)
        return parts