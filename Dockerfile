# Базовый образ Python
FROM python:3.11-slim

# Устанавливаем системные зависимости (включая клиент Postgres для ожидания)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаём рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем весь проект в контейнер
COPY . .

# Создаём папки для логов и бэкапов
RUN mkdir -p /app/logs /app/backups && chmod 755 /app/logs /app/backups

# Добавляем пользователя без root-прав
RUN useradd -m -u 1000 botuser && chown -R botuser:botuser /app
USER botuser

# Указываем Python-переменные
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 🕒 Ждём, пока Postgres будет готов, потом запускаем бота
CMD bash -c "until pg_isready -h db -p 5432 -U finbot_user; do echo '⏳ Waiting for PostgreSQL...'; sleep 2; done && python main.py"
