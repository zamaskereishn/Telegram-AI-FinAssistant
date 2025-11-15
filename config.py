from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()


class Config:
    # --- Основное ---
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

    # Gemini setup
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

    # База данных
    DATABASE_URL = os.getenv("DATABASE_URL")

    # Админы
    ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

    # Пути
    BASE_DIR = Path(__file__).resolve().parent
    LOGS_DIR = BASE_DIR / "logs"
    BACKUPS_DIR = BASE_DIR / "backups"

    LOGS_DIR.mkdir(exist_ok=True)
    BACKUPS_DIR.mkdir(exist_ok=True)

    # --- Настройки времени и расписания ---
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Almaty")
    DIGEST_HOUR = int(os.getenv("DIGEST_HOUR", 9))
    DIGEST_MINUTE = int(os.getenv("DIGEST_MINUTE", 0))

    # --- Тайминги и лимиты ---
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 2))
    SCRAPE_DELAY = float(os.getenv("SCRAPE_DELAY", 1))
    MAX_NEWS_ARTICLES = int(os.getenv("MAX_NEWS_ARTICLES", 50))

    # --- Списки источников ---
    NEWS_SOURCES = [
        "https://uz.kursiv.media/banks/",
        "https://forbes.kz/category/finance",
        "https://lsm.kz/",
        "https://finance.kapital.kz/"
    ]

    EXCHANGE_SOURCES = [
         "https://ifin.kz/exchange/astana",
        "https://altynbank.kz/ru/personal/exchange",
        "https://alataucitybank.kz/exchange-rates",
        "https://bankffin.kz/ru/exchange-rates",
        "https://nurbank.kz/ru/bank/currencies/",
        "https://bankrbk.kz/ru/exchange",
        "https://home.kz/currency/kurs-segodnya-astana",
        "https://eubank.kz/exchange-rates/",
        "https://prodengi.kz/astana/kurs-valyut",
        "https://nationalbank.kz/ru/exchangerates/ezhednevnye-oficialnye-rynochnye-kursy-valyut",
        "https://www.exchange-rates.org/ru/",
        "https://kurs.kz/site/index?city=astana",
        "https://www.bcc.kz/personal/currency-rates/",
        "https://guide.kaspi.kz/client/ru/transfers/services/own_accounts/q1954",
        "https://bank.forte.kz/ru/forex",
        "https://halykbank.kz/exchange-rates"
    ]


# Экземпляр для импорта
config = Config()