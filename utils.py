"""
Вспомогательные утилиты для работы бота
"""

from typing import List, Dict
import re
from datetime import datetime, timedelta
from database import get_db, Digest, User
from loguru import logger


def clean_html(text: str) -> str:
    """Очистка HTML тегов из текста"""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)


def truncate_text(text: str, max_length: int = 300) -> str:
    """Обрезка текста с сохранением целостности слов"""
    if len(text) <= max_length:
        return text

    truncated = text[:max_length].rsplit(' ', 1)[0]
    return truncated + '...'


def format_currency(value: str) -> str:
    """Форматирование валютных значений"""
    try:
        # Убираем лишние символы
        clean_value = re.sub(r'[^\d.,]', '', value)
        clean_value = clean_value.replace(',', '.')

        # Преобразуем в число
        num = float(clean_value)
        return f"{num:.2f}"
    except (ValueError, AttributeError):
        return value


def validate_url(url: str) -> bool:
    """Проверка корректности URL"""
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    return url_pattern.match(url) is not None


def get_digest_stats(days: int = 7) -> Dict:
    """Получение статистики по дайджестам"""
    db = get_db()
    try:
        start_date = datetime.now() - timedelta(days=days)

        digests = db.query(Digest).filter(
            Digest.created_at >= start_date
        ).all()

        return {
            'total_digests': len(digests),
            'published': len([d for d in digests if d.status == 'published']),
            'failed': len([d for d in digests if d.status == 'failed']),
            'drafts': len([d for d in digests if d.status == 'draft']),
        }
    finally:
        db.close()


def get_user_stats() -> Dict:
    """Получение статистики по пользователям"""
    db = get_db()
    try:
        users = db.query(User).all()

        return {
            'total_users': len(users),
            'active_users': len([u for u in users if u.is_active]),
            'inactive_users': len([u for u in users if not u.is_active]),
        }
    finally:
        db.close()


def format_digest_for_telegram(digest: str) -> List[str]:
    """
    Разбивка длинного дайджеста на части для Telegram
    (максимум 4096 символов в сообщении)
    """
    max_length = 4000  # Оставляем запас

    if len(digest) <= max_length:
        return [digest]

    # Разбиваем по разделам (они обычно начинаются с эмодзи)
    sections = re.split(r'(\n\n[📊💱🏦📈⚠️])', digest)

    messages = []
    current_message = ""

    for section in sections:
        if len(current_message) + len(section) <= max_length:
            current_message += section
        else:
            if current_message:
                messages.append(current_message.strip())
            current_message = section

    if current_message:
        messages.append(current_message.strip())

    return messages


def escape_markdown(text: str) -> str:
    """Экранирование специальных символов для Markdown"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']

    for char in special_chars:
        text = text.replace(char, f'\\{char}')

    return text


def get_latest_digest() -> Dict:
    """Получение последнего опубликованного дайджеста"""
    db = get_db()
    try:
        digest = db.query(Digest).filter(
            Digest.status == 'published'
        ).order_by(Digest.date.desc()).first()

        if digest:
            return {
                'id': digest.id,
                'date': digest.date,
                'summary': digest.summary,
                'categories': digest.categories,
            }
        return None
    finally:
        db.close()


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """Извлечение ключевых слов из текста"""
    # Простая реализация: извлечение самых частых слов
    # Можно улучшить с помощью NLP библиотек

    # Убираем пунктуацию и приводим к lowercase
    words = re.findall(r'\b\w+\b', text.lower())

    # Фильтруем стоп-слова (базовый список)
    stop_words = {
        'и', 'в', 'на', 'с', 'по', 'для', 'не', 'что', 'это', 'как',
        'из', 'о', 'к', 'до', 'от', 'у', 'за', 'при', 'так', 'но',
        'а', 'или', 'же', 'бы', 'ли', 'же', 'уже', 'даже', 'ни'
    }

    filtered_words = [w for w in words if len(w) > 3 and w not in stop_words]

    # Подсчет частоты
    word_freq = {}
    for word in filtered_words:
        word_freq[word] = word_freq.get(word, 0) + 1

    # Сортировка по частоте
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)

    return [word for word, freq in sorted_words[:top_n]]


def backup_database(backup_dir: str = 'backups'):
    """Создание резервной копии БД"""
    import os
    import subprocess
    from pathlib import Path

    backup_path = Path(backup_dir)
    backup_path.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_path / f'finbot_backup_{timestamp}.sql'

    try:
        # Используем pg_dump для создания бэкапа
        # Требует настройки .pgpass или переменных окружения
        subprocess.run([
            'pg_dump',
            '-h', 'localhost',
            '-U', 'finbot_user',
            '-d', 'finbot_db',
            '-f', str(backup_file)
        ], check=True)

        logger.info(f"Backup created: {backup_file}")
        return str(backup_file)
    except subprocess.CalledProcessError as e:
        logger.error(f"Backup failed: {e}")
        return None


def health_check() -> Dict:
    """Проверка работоспособности всех компонентов"""
    health = {
        'database': False,
        'telegram_api': False,
        'gemini_api': False,
        'scraper': False,
    }

    # Проверка БД
    try:
        db = get_db()
        db.query(User).first()
        db.close()
        health['database'] = True
    except Exception as e:
        logger.error(f"DB health check failed: {e}")

    # Проверка Telegram API
    try:
        from config import config
        if config.TELEGRAM_BOT_TOKEN:
            health['telegram_api'] = True
    except Exception as e:
        logger.error(f"Telegram health check failed: {e}")

    # Проверка Gemini API
    try:
        from config import config
        if config.GEMINI_API_KEY:
            health['gemini_api'] = True
    except Exception as e:
        logger.error(f"Gemini health check failed: {e}")

    # Проверка парсера
    try:
        from scraper import FinancialScraper
        scraper = FinancialScraper()
        health['scraper'] = True
    except Exception as e:
        logger.error(f"Scraper health check failed: {e}")

    return health


def generate_report(days: int = 7) -> str:
    """Генерация отчета о работе бота"""
    digest_stats = get_digest_stats(days)
    user_stats = get_user_stats()
    health = health_check()

    report = f"""
📊 **Отчет о работе бота**

Период: последние {days} дней

**Дайджесты:**
• Всего: {digest_stats['total_digests']}
• Опубликовано: {digest_stats['published']}
• Черновики: {digest_stats['drafts']}
• Ошибки: {digest_stats['failed']}

**Пользователи:**
• Всего: {user_stats['total_users']}
• Активных: {user_stats['active_users']}
• Неактивных: {user_stats['inactive_users']}

**Статус компонентов:**
• База данных: {'✓' if health['database'] else '✗'}
• Telegram API: {'✓' if health['telegram_api'] else '✗'}
• Gemini API: {'✓' if health['gemini_api'] else '✗'}
• Парсер: {'✓' if health['scraper'] else '✗'}

Дата отчета: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    return report


if __name__ == "__main__":
    # Пример использования
    print(generate_report())