"""
Модуль для анализа инвестиционных предложений и выдачи рекомендаций
"""
from openai import OpenAI
from config import config
from loguru import logger
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from parsers import try_structured_parse
import json, datetime, re
import sys

# Добавляем путь для импорта scraper
sys.path.append('.')
from scraper import FinancialScraper


@dataclass
class InvestmentProduct:
    """Структура инвестиционного продукта"""
    name: str
    type: str  # bonds, deposits, mutual_funds, stocks, etc.
    provider: str  # bank/broker name
    yield_rate: Optional[float]
    currency: str
    term: Optional[str]
    risk_level: str  # low, medium, high
    min_investment: Optional[float]
    url: str
    additional_info: Dict


class InvestmentAnalyzer:
    """Анализ инвестиционных предложений"""

    def __init__(self):
        self.scraper = FinancialScraper()
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)

        # Источники инвестиционных предложений
        self.local_sources = {
            'bonds': [
               'https://kase.kz/ru/markets/government-securities',
                'https://kase.kz/ru/markets/corporate-bonds',
                'https://kase.kz/ru/markets/investment-fund-securities'
                'https://aix.kz/ru/debt-market'
            ],
            'deposits': [
                'https://nationalbank.kz/en/news/vklady-v-bankah-v-regionalnom-razreze-',
                'https://kdif.kz/',
                'https://halykbank.kz/deposits-ru'
                'https://www.bcc.kz/personal/deposits/'
                'https://bank.forte.kz/ru/deposits'
                'https://berekebank.kz/ru/personal/deposits'
                'https://jusan.kz/ru/deposits'
                'https://bankrbk.kz/ru/individuals/deposits'
                'https://bankffin.kz/ru/deposits/physical'
            ],
            'mutual_funds': [
                'https://kase.kz/ru/markets/investment-fund-securities',
                'https://halykfinance.kz/ipif/?lang=ru',
                'https://www.bcc-invest.kz/products/open-pi/'
            ],
            'broker_platforms': [
                'https://ffin.kz/ru',
                'https://halykfinance.kz/brokerskoe-obsluzhivanie/?lang=ru',
                'https://www.interactivebrokers.com/ru/home.php',
                'https://www.bcc-invest.kz/products/brokerage/'
            ]
        }

        self.international_sources = [
            'https://www.investing.com/rates-bonds/world-government-bonds',
            'https://finance.yahoo.com/bonds',
            'https://www.bloomberg.com/markets/rates-bonds',
            'https://www.investing.com/commodities/gold',
            'https://www.investing.com/currencies/usd-kzt',
        ]

    def scrape_investment_products(self, category: str = None) -> List[Dict]:
        """Скрапинг инвестиционных продуктов"""
        logger.info(f"Scraping investment products: {category or 'all'}")

        urls = []
        if category and category in self.local_sources:
            urls = self.local_sources[category]
        elif category == 'international':
            urls = self.international_sources
        elif category == 'all':
            for cat_urls in self.local_sources.values():
                urls.extend(cat_urls)
        else:
            # По умолчанию берём местные источники
            for cat_urls in self.local_sources.values():
                urls.extend(cat_urls)

        articles = self.scraper.scrape_many(urls)
        logger.info(f"✅ Scraped {len(articles)} investment sources")
        return articles

    def extract_investment_data(self, text: str, source_type: str) -> list:
        """
        Извлечение строго структурированных данных об инвестиционных продуктах.
        Возвращает Python-список dict'ов (после json.loads).
        """

        # JSON-схема хранится ВНЕ f-string → безопасно
        schema = """
    [
      {
        "name": "string or null",
        "type": "bonds | deposits | mutual_funds | stocks | null",
        "provider": "string or null",
        "yield_rate": "number or null",
        "currency": "string or null",
        "term": "string or null",
        "risk_level": "string or null",
        "min_investment": "number or null",
        "url": "string or null",
        "additional_info": "object or null"
      }
    ]
    """

        # Теперь f-string ЧИСТЫЙ, без {} из схемы
        prompt = f"""
    Ты — финансовый аналитик. Твоя задача — ИЗВЛЕЧЬ ИЗ ТЕКСТА данные об инвестиционных продуктах
    и вернуть ИСКЛЮЧИТЕЛЬНО корректный JSON-массив.

    Требования:

    1) Верни ТОЛЬКО JSON, без текста.
    2) JSON должен быть массивом объектов: [ {{...}}, {{...}} ].
    3) JSON обязан соответствовать схеме ниже.

    СХЕМА JSON:
    {schema}

    4) Если какие-то данные отсутствуют — ставь null.
    5) НЕ добавляй комментарии, текст, markdown.
    6) Числа приводи к числовому типу (без %, ₸, $).

    Категория источника: {source_type}

    ТЕКСТ:
    {text[:4000]}
    """

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты финансовый аналитик. "
                            "Возвращай ТОЛЬКО JSON. "
                            "Если нет данных — верни []"
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
            )

            raw = response.choices[0].message.content.strip()

            # JSON parsing
            try:
                data = json.loads(raw)
                if isinstance(data, list):
                    return data
                else:
                    logger.warning("LLM returned non-list JSON. Wrapping into list.")
                    return [data]

            except json.JSONDecodeError:
                logger.error("JSON decode error. Raw LLM output:")
                logger.error(raw)
                return []

        except Exception as e:
            logger.error(f"Error extracting investment data: {e}")
            return []

    def analyze_market_conditions(self, articles: List[Dict]) -> str:
        """Анализ текущих рыночных условий"""
        combined_text = "\n\n".join([
            f"{art.get('title', '')} — {art.get('url')}\n{art['text'][:2000]}"
            for art in articles[:10]  # Берём первые 10 источников
        ])

        prompt = f"""
На основе собранной информации проанализируй текущие рыночные условия для инвестиций в Казахстане:

1. Уровень инфляции и прогнозы
2. Ставка рефинансирования НБК
3. Курсы основных валют (USD, EUR, RUB)
4. Доходность государственных облигаций
5. Ставки по депозитам в банках
6. Ситуация на фондовом рынке KASE
7. Цены на сырьевые товары (нефть, золото)

Источники:
{combined_text}

Дай краткий аналитический обзор (5-7 пунктов):
"""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Ты финансовый аналитик. Анализируй макроэкономические условия для инвестиций."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error analyzing market conditions: {e}")
            return ""

    def generate_investment_recommendations(
        self,
        products_data: List[str],
        market_conditions: str,
        risk_profile: str = "medium",
        investment_horizon: str = "medium",
        amount: Optional[float] = None
    ) -> str:
        """
        Генерация персонализированных инвестиционных рекомендаций

        Args:
            products_data: Список извлечённых данных о продуктах
            market_conditions: Анализ рыночных условий
            risk_profile: low, medium, high
            investment_horizon: short (до 1 года), medium (1-3 года), long (3+ года)
            amount: Сумма для инвестирования (в тенге)
        """

        risk_descriptions = {
            "low": "консервативный (приоритет — сохранение капитала)",
            "medium": "умеренный (баланс между доходностью и риском)",
            "high": "агрессивный (максимизация доходности)"
        }

        horizon_descriptions = {
            "short": "краткосрочный (до 1 года)",
            "medium": "среднесрочный (1-3 года)",
            "long": "долгосрочный (3+ года)"
        }

        products_summary = "\n\n".join(products_data[:20])  # Топ-20 продуктов

        amount_info = f"Сумма для инвестирования: {amount:,.0f} ₸" if amount else "Сумма не указана"

        prompt = f"""
Ты — профессиональный инвестиционный консультант в Казахстане.

ПРОФИЛЬ КЛИЕНТА:
- Риск-профиль: {risk_descriptions.get(risk_profile, risk_profile)}
- Инвестиционный горизонт: {horizon_descriptions.get(investment_horizon, investment_horizon)}
- {amount_info}

ТЕКУЩИЕ РЫНОЧНЫЕ УСЛОВИЯ:
{market_conditions}

ДОСТУПНЫЕ ИНВЕСТИЦИОННЫЕ ПРОДУКТЫ:
{products_summary}

ЗАДАЧА:
Сформируй персонализированные инвестиционные рекомендации со следующей структурой:

📊 РЕКОМЕНДУЕМЫЙ ПОРТФЕЛЬ
1. Распределение активов (с процентами)
2. Конкретные продукты для каждой категории
3. Ожидаемая доходность портфеля

💡 ТОП-3 ИНВЕСТИЦИОННЫЕ ИДЕИ
Для каждой идеи:
- Продукт и провайдер
- Ожидаемая доходность
- Уровень риска
- Почему сейчас хорошее время

⚠️ РИСКИ И ОГРАНИЧЕНИЯ
- Основные риски текущих условий
- Что может пойти не так
- Как минимизировать риски

📈 АЛЬТЕРНАТИВНЫЕ СЦЕНАРИИ
- Если рынок растёт
- Если рынок падает

🎯 ПРАКТИЧЕСКИЕ ШАГИ
Что делать дальше (конкретные действия)

Рекомендации должны быть:
- Конкретными (с названиями банков/продуктов)
- Реалистичными (доступные в Казахстане продукты)
- Обоснованными (почему именно это)
- С цифрами (проценты, суммы, сроки)
"""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Ты профессиональный инвестиционный консультант в Казахстане. Даёшь конкретные, обоснованные рекомендации."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return "❌ Ошибка при генерации рекомендаций."

    def parse_product_page(self, article: Dict) -> list:
        """
        Попытка структурно распарсить страницу. Если селекторы не работают, используем LLM (JSON).
        Возвращаем список dict'ов (может быть несколько продуктов на странице).
        """
        url = article.get('url')
        html = None
        # Попробуем сделать структурный парсинг (если в article сохранил raw html — иначе, нужно изменить scraper)
        # Здесь предполагаем, что scraper.scrape_url может сохранять response.content -> можно расширить.
        # Fallback: работаем с article['text'] через LLM
        parsed = None
        try:
            # если article содержит raw_html:
            if 'raw_html' in article and article['raw_html']:
                parsed = try_structured_parse(article['raw_html'], url)
        except Exception:
            parsed = None

        if parsed:
            # Привести данные к единому виду (нормализация)
            return [self._normalize_parsed(p) for p in parsed]

        # Fallback LLM extraction — просим вернуть JSON строго в схеме
        prompt = (
            "Верни JSON array с объектами: {name,type,provider,yield_rate,currency,term,risk_level,min_investment,url,additional_info}\n\n"
            f"ТЕКСТ:\n{article.get('text')[:4000]}"
        )
        resp = self.client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "Ты финансовый аналитик. Возвращай корректный JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
        )
        txt = resp.choices[0].message.content.strip()
        # Попытка извлечь JSON из ответа
        try:
            objs = json.loads(txt)
            return [self._normalize_parsed(o) for o in objs]
        except Exception:
            # как последний вариант — вернуть текст для ручной инспекции
            return [{"name": article.get('title'), "type": "unknown", "provider": "unknown",
                     "yield_rate": None, "currency": None, "term": None, "risk_level": "unknown",
                     "min_investment": None, "url": url, "additional_info": {"raw": article.get('text')[:1000]},
                     "confidence": "llm_free"}]

    def _normalize_parsed(self, raw: dict) -> dict:
        # Привести проценты и суммы к числам
        def parse_percent(s):
            if not s: return None
            s = str(s).replace(',', '.')
            m = re.search(r"(\d+(\.\d+)?)", s)
            return float(m.group(1)) if m else None

        def parse_amount(s):
            if not s: return None
            s = re.sub(r"[^\d.,]", "", str(s)).replace(',', '')
            try:
                return float(s)
            except:
                return None

        return {
            "name": raw.get("name") or raw.get("title"),
            "type": raw.get("type"),
            "provider": raw.get("provider"),
            "yield_rate": parse_percent(raw.get("yield_rate") or raw.get("rate")),
            "currency": (raw.get("currency") or "").upper()[:3],
            "term": raw.get("term"),
            "risk_level": raw.get("risk_level") or "unknown",
            "min_investment": parse_amount(raw.get("min_investment")),
            "url": raw.get("url"),
            "additional_info": raw.get("additional_info") or {},
            "scraped_at": datetime.datetime.utcnow().isoformat(),
        }

    def score_product(self, p: dict) -> float:
        """
        Простая функция скоринга: база по доходности vs benchmark.
        Возвращает 0..100
        """
        score = 50.0
        if p.get("yield_rate") is not None:
            # простой подход — чем выше доходность, тем лучше (но penalize high risk)
            score += (p["yield_rate"] - 1.0) * 3.0  # настраиваем правило
        # наказание за неизвестную валюту
        if p.get("currency") not in ("KZT", "USD", "EUR"):
            score -= 5
        if p.get("min_investment") and p["min_investment"] > 1_000_000:
            score -= 5
        # cap
        return max(0, min(100, score))
    def compare_products(self, product_type: str) -> str:
        """Сравнение однотипных продуктов (например, депозитов)"""
        logger.info(f"Comparing products: {product_type}")

        articles = self.scrape_investment_products(category=product_type)
        if not articles:
            return "❌ Не удалось получить данные для сравнения."

        # Извлекаем данные о продуктах
        products_data = []
        for art in articles:
            chunks = self.scraper.chunk_text(art['text'], max_chars=4000)
            for chunk in chunks[:2]:  # Берём первые 2 чанка
                data = self.extract_investment_data(chunk, product_type)
                if data:
                    products_data.append(data)

        if not products_data:
            return "❌ Не удалось извлечь данные о продуктах."

        # Формируем сравнительную таблицу
        combined = "\n\n".join(products_data)

        prompt = f"""
На основе собранных данных создай сравнительную таблицу {product_type} от разных банков/провайдеров.

Структура:
1. Таблица сравнения (название, банк, доходность, срок, мин. сумма)
2. ТОП-3 лучших предложения с обоснованием
3. Для кого подходит каждое предложение
4. Подводные камни и на что обратить внимание

Данные о продуктах:
{combined}

Сравнение:
"""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Ты финансовый аналитик. Создаёшь объективные сравнения инвестиционных продуктов."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error comparing products: {e}")
            return "❌ Ошибка при сравнении продуктов."

    def get_international_outlook(self) -> str:
        """Анализ международных рынков для диверсификации"""
        logger.info("Analyzing international markets")

        articles = self.scraper.scrape_many(self.international_sources)
        if not articles:
            return "❌ Не удалось получить международные данные."

        combined = "\n\n".join([
            f"{art.get('title', '')} — {art.get('url')}\n{art['text'][:2000]}"
            for art in articles[:5]
        ])

        prompt = f"""
На основе международных финансовых источников проанализируй возможности для диверсификации портфеля казахстанского инвестора:

1. US Treasury Bonds (доходности)
2. Еврооблигации (европейский рынок)
3. Золото и драгметаллы
4. Мировые валюты (USD, EUR, CNY)
5. Глобальные фондовые индексы

Для каждого актива:
- Текущая ситуация
- Перспективы
- Как можно инвестировать из Казахстана
- Риски и ограничения

Источники:
{combined}

Аналитика:
"""

        try:
            response = self.client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "Ты международный финансовый аналитик. Помогаешь казахстанским инвесторам с диверсификацией."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error analyzing international markets: {e}")
            return "❌ Ошибка при анализе международных рынков."


def generate_full_investment_report(
    risk_profile: str = "medium",
    investment_horizon: str = "medium",
    amount: Optional[float] = None
) -> str:
    """
    Генерация полного инвестиционного отчёта
    """
    analyzer = InvestmentAnalyzer()

    logger.info("🔍 Starting full investment analysis...")

    # 1. Скрапим местные продукты
    logger.info("Step 1: Scraping local investment products...")
    local_articles = analyzer.scrape_investment_products(category='all')

    # 2. Извлекаем данные о продуктах
    logger.info("Step 2: Extracting product data...")
    products_data = []
    for art in local_articles[:15]:  # Топ-15 источников
        chunks = analyzer.scraper.chunk_text(art['text'], max_chars=4000)
        for chunk in chunks[:2]:
            data = analyzer.extract_investment_data(chunk, 'mixed')
            if data:
                products_data.append(data)
    structured_products = []
    for art in local_articles[:50]:
        parsed = analyzer.parse_product_page(art)
        for p in parsed:
            p['score'] = analyzer.score_product(p)
            structured_products.append(p)

    # Сохраняем топ N в ProductComparison
    top3 = sorted(structured_products, key=lambda x: x['score'], reverse=True)[:3]
    from database import save_investment_report  # или создать save_product_comparison
    save_investment_report(
        user_id=0,
        title=f"Snapshot products {datetime.utcnow().isoformat()}",
        content=str(structured_products)[:10000],
        market_conditions=market_conditions,
        recommendations=str(top3),
        risk_profile=risk_profile,
        investment_horizon=investment_horizon
    )
    top3 = sorted(structured_products, key=lambda x: x['score'], reverse=True)[:3]
    from database import save_investment_report  # или создать save_product_comparison
    save_investment_report(
        user_id=0,
        title=f"Snapshot products {datetime.utcnow().isoformat()}",
        content=str(structured_products)[:10000],
        market_conditions=market_conditions,
        recommendations=str(top3),
        risk_profile=risk_profile,
        investment_horizon=investment_horizon
    )
    # 3. Анализируем рыночные условия
    logger.info("Step 3: Analyzing market conditions...")
    market_conditions = analyzer.analyze_market_conditions(local_articles)

    # 4. Получаем международную перспективу
    logger.info("Step 4: Getting international outlook...")
    international_outlook = analyzer.get_international_outlook()

    # 5. Генерируем рекомендации
    logger.info("Step 5: Generating recommendations...")
    recommendations = analyzer.generate_investment_recommendations(
        products_data=products_data,
        market_conditions=market_conditions,
        risk_profile=risk_profile,
        investment_horizon=investment_horizon,
        amount=amount
    )

    # Формируем итоговый отчёт
    report = f"""
🎯 ИНВЕСТИЦИОННЫЙ АНАЛИЗ И РЕКОМЕНДАЦИИ
Дата: {datetime.now().strftime('%d.%m.%Y')}

{'='*60}

📊 ТЕКУЩИЕ РЫНОЧНЫЕ УСЛОВИЯ

{market_conditions}

{'='*60}

{recommendations}

{'='*60}

🌍 МЕЖДУНАРОДНЫЕ ВОЗМОЖНОСТИ

{international_outlook}

{'='*60}

⚠️ ДИСКЛЕЙМЕР
Данный анализ носит информационный характер и не является индивидуальной инвестиционной рекомендацией. Перед принятием инвестиционных решений проконсультируйтесь с лицензированным финансовым консультантом. Помните: прошлые результаты не гарантируют будущую доходность.

📞 Для получения персональной консультации обратитесь к финансовому советнику.
"""

    logger.info("✅ Investment report generated")
    return report