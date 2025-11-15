#!/usr/bin/env python3
"""
Финансовый Telegram-бот для генерации дайджестов
Автор: Your Name
Версия: 1.0
"""

from loguru import logger
import sys
from pathlib import Path

# Настройка логирования
from config import config

logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO"
)

# Логирование в файл
log_file = config.LOGS_DIR / "bot_{time:YYYY-MM-DD}.log"
logger.add(
    str(log_file),
    rotation="00:00",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    level="DEBUG"
)


def check_config():
    """Проверка конфигурации перед запуском"""
    errors = []

    if not config.TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN не установлен")

    if not config.OPENAI_API_KEY:
        errors.append("OPENAI_API_KEY не установлен")

    if not config.DATABASE_URL:
        errors.append("DATABASE_URL не установлен")

    if errors:
        logger.error("Ошибки конфигурации:")
        for error in errors:
            logger.error(f"  - {error}")
        return False

    return True


def main():
    """Главная функция"""
    logger.info("=" * 70)
    logger.info("🤖 ФИНАНСОВЫЙ ДАЙДЖЕСТ-БОТ")
    logger.info("=" * 70)
    logger.info("")

    # Проверка конфигурации
    logger.info("Проверка конфигурации...")
    if not check_config():
        logger.error("Конфигурация неверна. Проверьте .env файл")
        sys.exit(1)

    logger.success("✓ Конфигурация корректна")
    logger.info("")

    # Вывод параметров
    logger.info("Параметры запуска:")
    logger.info(f"  Timezone: {config.TIMEZONE}")
    logger.info(f"  Время рассылки: {config.DIGEST_HOUR:02d}:{config.DIGEST_MINUTE:02d}")
    logger.info(f"  Источников новостей: {len(config.NEWS_SOURCES)}")
    logger.info(f"  Источников валют: {len(config.EXCHANGE_SOURCES)}")
    logger.info(f"  Админов: {len(config.ADMIN_IDS)}")
    logger.info(f"  База данных: {config.DATABASE_URL.split('@')[1] if '@' in config.DATABASE_URL else 'настроена'}")
    logger.info(f"  OpenAI Model: {config.OPENAI_MODEL}")
    logger.info("")

    # Инициализация базы данных
    logger.info("Инициализация базы данных...")
    try:
        from database import init_db, get_db, User
        init_db()

        # Проверка подключения
        db = get_db()
        try:
            user_count = db.query(User).count()
            logger.success(f"✓ База данных готова (пользователей: {user_count})")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        logger.error("Проверьте DATABASE_URL и доступность PostgreSQL")
        sys.exit(1)

    logger.info("")

    # Проверка OpenAI API
    logger.info("Проверка OpenAI API...")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        # Простой тестовый запрос
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "user", "content": "Привет! Ответь одним словом: работает?"}
            ],
            max_tokens=10
        )
        if response and response.choices[0].message.content:
            logger.success("✓ OpenAI API работает")
        else:
            logger.warning("⚠ OpenAI API отвечает, но пустой ответ")
    except Exception as e:
        logger.error(f"Ошибка OpenAI API: {e}")
        logger.error("Проверьте OPENAI_API_KEY")
        sys.exit(1)

    logger.info("")
    logger.info("=" * 70)
    logger.info("🚀 Запуск Telegram бота...")
    logger.info("=" * 70)
    logger.info("")

    # Запуск бота
    try:
        from bot import run_bot
        run_bot()
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 70)
        logger.info("⏹️  Бот остановлен пользователем")
        logger.info("=" * 70)
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()