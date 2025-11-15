📊 Financial Digest & Investment Assistant Bot
Automated Financial Digest Generation • Investment Analytics • Product Comparison • Market Intelligence

This project is a powerful Telegram bot designed for banks, financial analysts, and investment departments.
It automatically scrapes financial news, summarizes them using LLM models, and produces a structured, professional daily digest.
It also performs investment analysis, product comparisons, market outlooks, and finance-only Q&A.

🚀 Features Overview
1️⃣ Financial Digest Generation (MAIN FEATURE)

The bot’s primary capability is generating a complete financial digest from dozens of news sources.

✔ Digest Pipeline:

Web scraping using:

requests + BeautifulSoup4 + lxml

selenium + webdriver-manager for dynamic pages

feedparser for RSS feeds

Content extraction:

text cleaning

title extraction

auto-chunking for LLM

Summaries with GPT (LLM)

each article chunk is summarized

numeric values, dates, events preserved

Digest aggregation

LLM produces a structured digest:

Macroeconomics

FX & currencies

Commodities

Banking news

Full multi-category digest

Saving to PostgreSQL

category

model

JSON source metadata

timestamps

Automatic daily sending
via Telegram JobQueue at a scheduled time.

📌 Digest generation is the foundation of the entire project and the first feature to understand.

2️⃣ Investment Analysis Module

Includes:

scraping local & international investment data

extracting structured investment products (strict JSON via LLM)

analyzing market conditions

personalized recommendations:

risk profile

horizon

investment amount

Produces full investment reports with:

recommended asset allocation

yield expectations

risk scenarios

top investment ideas

3️⃣ Product Comparison

Supports comparison of:

deposits

bonds

mutual funds

broker platforms

Each comparison includes:

tabular comparison

scoring model

top product picks

suitability for different investor types

warnings / pitfalls

4️⃣ International Market Outlook

Analyzes:

US Treasuries

Eurobonds

Gold and commodities

FX (USD/EUR/CNY)

Global indices

Produced via LLM based on scraped data.

5️⃣ Q&A Financial Assistant

Finance-only assistant that:

answers questions related to finance, banking, macroeconomics

rejects non-financial questions

logs all queries in PostgreSQL

🧩 Project Structure
├── bot.py                     # Telegram bot commands & handlers
├── scraper.py                 # Web-scraper system
├── llm.py                     # Summaries, aggregation, Q&A, extraction
├── investment_analyzer.py     # Investment logic & recommendations
├── database.py                # ORM models & database management
├── config.py                  # .env configuration loader
├── main.py                    # Application entry point
├── docker/                    # Docker-related files (optional)
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements.txt  
└── .env.example               # Example environment variables

🐳 Docker Support

The project can run fully inside Docker containers — including scraping, Selenium, PostgreSQL, and the bot worker.

1. Build the Docker image
docker build -t financial-digest-bot .

2. Run the container
docker run --env-file .env financial-digest-bot

🐳 docker-compose (Recommended)

A typical stack includes:

the bot container

PostgreSQL

optional pgAdmin

optional Selenium Chrome driver (if needed)

Example docker-compose.yml:

version: "3.9"

services:
  bot:
    build: .
    container_name: financial_bot
    restart: always
    env_file: .env
    depends_on:
      - db

  db:
    image: postgres:15
    container_name: digest_db
    restart: always
    environment:
      POSTGRES_DB: digest
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

volumes:
  pgdata:

Start everything
docker compose up -d

⚙️ Manual Installation (non-Docker)
1. Install dependencies
pip install -r requirements.txt

2. Set environment variables

Create .env:

TELEGRAM_BOT_TOKEN=
OPENAI_API_KEY=
DATABASE_URL=postgresql+psycopg2://user:password@host/db
TIMEZONE=Asia/Almaty
DIGEST_HOUR=9
DIGEST_MINUTE=0

3. Run
python main.py

🗄 Database Overview

Tables include:

Table	Purpose
users	User profiles, risk profiles
digests	Generated financial digests
investment_reports	Full investment analysis reports
product_comparisons	Product comparison results
queries	Q&A history
scraping_logs	Raw scraping metrics and errors
🧠 Technologies Used
Web Scraping

requests, BeautifulSoup4, lxml, selenium, feedparser

LLM

OpenAI GPT-4o for summaries, aggregation, structured JSON parsing, Q&A

Backend

Python 3.10+
PostgreSQL
SQLAlchemy ORM
Loguru
dotenv

Telegram

python-telegram-bot v20+
JobQueue for scheduled tasks

Docker

Dockerfile + docker-compose support
