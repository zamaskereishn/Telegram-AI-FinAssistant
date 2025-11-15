from telegram import Update
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram import BotCommand
from telegram.ext import CallbackQueryHandler, MessageHandler
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackContext,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from config import config
from loguru import logger
from llm import summarize_chunk, aggregate_summaries, ask_openai
from scraper import FinancialScraper
from database import get_db, Digest, init_db
from investment_analyzer import InvestmentAnalyzer, generate_full_investment_report
from sqlalchemy.exc import SQLAlchemyError
import asyncio
from datetime import time as dtime, datetime
from zoneinfo import ZoneInfo

scraper = FinancialScraper()
investment_analyzer = InvestmentAnalyzer()


# Middleware для логирования всех обновлений
async def log_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логируем каждое обновление от Telegram"""
    logger.info(f"📨 RECEIVED UPDATE: {update}")
    if update.message:
        logger.info(f"  └─ Message: {update.message.text}")
    if update.callback_query:
        logger.info(f"  └─ Callback: {update.callback_query.data}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("🎬 start command called")
    await update.message.reply_text(
        "Привет! Я бот для финансового анализа и инвестиционных рекомендаций.\n\n"
        "📊 /digest — финансовый дайджест\n"
        "💰 /invest — инвестиционные рекомендации\n"
        "📈 /compare — сравнение продуктов\n"
        "🌍 /global — международные рынки\n"
        "❓ /help — список всех команд"
    )


async def digest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show category selection keyboard."""
    logger.info("📊 digest_command called")
    keyboard = [
        [
            InlineKeyboardButton("💰 Макроэкономика", callback_data="digest_macro"),
            InlineKeyboardButton("💹 Валюты", callback_data="digest_forex"),
        ],
        [
            InlineKeyboardButton("🛢 Нефть и сырьё", callback_data="digest_commodities"),
            InlineKeyboardButton("🏦 Банковский сектор", callback_data="digest_banks"),
        ],
        [InlineKeyboardButton("📊 Все темы", callback_data="digest_all")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await update.message.reply_text("Выберите категорию дайджеста:", reply_markup=reply_markup)
    logger.info(f"✅ Keyboard sent, message_id: {msg.message_id}")


async def invest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show investment options menu"""
    logger.info("💰 invest_command called")
    keyboard = [
        [
            InlineKeyboardButton("🎯 Полный анализ", callback_data="invest_full"),
            InlineKeyboardButton("📊 Сравнить продукты", callback_data="invest_compare"),
        ],
        [
            InlineKeyboardButton("🌍 Международные рынки", callback_data="invest_global"),
            InlineKeyboardButton("⚙️ Настроить профиль", callback_data="invest_profile"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "💼 ИНВЕСТИЦИОННЫЙ АНАЛИЗ\n\n"
        "Выберите опцию:",
        reply_markup=reply_markup
    )


async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show product comparison menu"""
    logger.info("📈 compare_command called")
    keyboard = [
        [
            InlineKeyboardButton("💳 Депозиты", callback_data="compare_deposits"),
            InlineKeyboardButton("📜 Облигации", callback_data="compare_bonds"),
        ],
        [
            InlineKeyboardButton("📊 ПИФы", callback_data="compare_mutual_funds"),
            InlineKeyboardButton("🏢 Брокеры", callback_data="compare_brokers"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "📊 СРАВНЕНИЕ ПРОДУКТОВ\n\n"
        "Выберите тип продукта:",
        reply_markup=reply_markup
    )


async def global_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Analyze international markets"""
    logger.info("🌍 global_command called")
    await update.message.reply_text("⏳ Анализирую международные рынки...")

    try:
        result = investment_analyzer.get_international_outlook()

        # Отправляем результат частями
        for chunk in (result[i:i + 3900] for i in range(0, len(result), 3900)):
            await update.message.reply_text(chunk)
    except Exception as e:
        logger.exception(f"Error in global analysis: {e}")
        await update.message.reply_text("❌ Ошибка при анализе международных рынков.")


async def digest_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора категории из inline-кнопок"""
    logger.info("🎯 digest_category_selected TRIGGERED!")

    query = update.callback_query
    logger.info(f"  └─ Callback data: {query.data}")
    logger.info(f"  └─ User: {query.from_user.id} (@{query.from_user.username})")

    await query.answer()
    logger.info("  └─ Query answered")

    # Извлекаем категорию из callback_data (убираем префикс "digest_")
    category = query.data.replace("digest_", "")
    logger.info(f"  └─ Processing category: {category}")

    # Показываем сообщение о начале генерации
    await query.edit_message_text(f"⏳ Генерирую дайджест по теме: {category}...")
    logger.info("  └─ Status message sent")

    try:
        # Генерируем дайджест
        logger.info(f"  └─ Starting digest generation for: {category}")
        digest_text = await generate_digest(category)
        logger.info(f"  └─ Digest generated, length: {len(digest_text)}")

        # Отправляем результат (разбиваем на части, если длинный)
        chunk_count = 0
        for chunk in (digest_text[i:i + 3900] for i in range(0, len(digest_text), 3900)):
            await query.message.reply_text(chunk)
            chunk_count += 1
        logger.info(f"  └─ Sent {chunk_count} message chunks")
    except Exception as e:
        logger.exception(f"❌ Error generating digest: {e}")
        await query.message.reply_text("❌ Ошибка при генерации дайджеста. Попробуйте позже.")


async def investment_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка callback'ов для инвестиционных команд"""
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.info(f"Investment callback: {data}")

    if data == "invest_full":
        await query.edit_message_text("⏳ Генерирую полный инвестиционный анализ...")
        try:
            # Используем профиль пользователя из контекста, если есть
            user_data = context.user_data
            risk_profile = user_data.get('risk_profile', 'medium')
            horizon = user_data.get('investment_horizon', 'medium')
            amount = user_data.get('investment_amount', None)

            report = await asyncio.to_thread(
                generate_full_investment_report,
                risk_profile=risk_profile,
                investment_horizon=horizon,
                amount=amount
            )

            # Отправляем отчёт частями
            for chunk in (report[i:i + 3900] for i in range(0, len(report), 3900)):
                await query.message.reply_text(chunk)

        except Exception as e:
            logger.exception(f"Error generating investment report: {e}")
            await query.message.reply_text("❌ Ошибка при генерации отчёта.")

    elif data == "invest_compare":
        # Показываем меню сравнения
        keyboard = [
            [
                InlineKeyboardButton("💳 Депозиты", callback_data="compare_deposits"),
                InlineKeyboardButton("📜 Облигации", callback_data="compare_bonds"),
            ],
            [
                InlineKeyboardButton("📊 ПИФы", callback_data="compare_mutual_funds"),
                InlineKeyboardButton("🏢 Брокеры", callback_data="compare_brokers"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите тип продукта для сравнения:", reply_markup=reply_markup)

    elif data == "invest_global":
        await query.edit_message_text("⏳ Анализирую международные рынки...")
        try:
            result = await asyncio.to_thread(investment_analyzer.get_international_outlook)

            for chunk in (result[i:i + 3900] for i in range(0, len(result), 3900)):
                await query.message.reply_text(chunk)
        except Exception as e:
            logger.exception(f"Error in global analysis: {e}")
            await query.message.reply_text("❌ Ошибка при анализе.")

    elif data == "invest_profile":
        # Показываем меню настройки профиля
        keyboard = [
            [
                InlineKeyboardButton("🟢 Низкий риск", callback_data="profile_risk_low"),
                InlineKeyboardButton("🟡 Средний риск", callback_data="profile_risk_medium"),
                InlineKeyboardButton("🔴 Высокий риск", callback_data="profile_risk_high"),
            ],
            [
                InlineKeyboardButton("⏱ Короткий срок", callback_data="profile_horizon_short"),
                InlineKeyboardButton("📅 Средний срок", callback_data="profile_horizon_medium"),
                InlineKeyboardButton("📆 Длинный срок", callback_data="profile_horizon_long"),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "⚙️ НАСТРОЙКА ПРОФИЛЯ\n\n"
            "Выберите ваш риск-профиль и инвестиционный горизонт:",
            reply_markup=reply_markup
        )


async def comparison_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сравнения продуктов"""
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.info(f"Comparison callback: {data}")

    # Определяем тип продукта
    product_type = data.replace("compare_", "")

    product_names = {
        'deposits': 'депозиты',
        'bonds': 'облигации',
        'mutual_funds': 'ПИФы',
        'brokers': 'брокерские платформы'
    }

    product_name = product_names.get(product_type, product_type)

    await query.edit_message_text(f"⏳ Сравниваю {product_name}...")

    try:
        result = await asyncio.to_thread(investment_analyzer.compare_products, product_type)

        for chunk in (result[i:i + 3900] for i in range(0, len(result), 3900)):
            await query.message.reply_text(chunk)
    except Exception as e:
        logger.exception(f"Error comparing products: {e}")
        await query.message.reply_text(f"❌ Ошибка при сравнении {product_name}.")


async def profile_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка настройки профиля пользователя"""
    query = update.callback_query
    await query.answer()

    data = query.data
    logger.info(f"Profile callback: {data}")

    # Сохраняем настройки в user_data
    if data.startswith("profile_risk_"):
        risk = data.replace("profile_risk_", "")
        context.user_data['risk_profile'] = risk
        await query.edit_message_text(
            f"✅ Установлен риск-профиль: {risk.upper()}\n\n"
            f"Теперь используйте /invest для получения персонализированных рекомендаций."
        )

    elif data.startswith("profile_horizon_"):
        horizon = data.replace("profile_horizon_", "")
        context.user_data['investment_horizon'] = horizon
        await query.edit_message_text(
            f"✅ Установлен горизонт: {horizon.upper()}\n\n"
            f"Теперь используйте /invest для получения персонализированных рекомендаций."
        )


async def catch_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ловим ВСЕ callback'и для отладки"""
    query = update.callback_query
    logger.warning(f"⚠️ CATCH-ALL TRIGGERED: {query.data}")
    await query.answer(f"Получен callback: {query.data}")
    await query.message.reply_text(f"Debug: обработан callback '{query.data}'")


async def scheduled_digest_job(context: CallbackContext):
    """Ежедневная задача — генерируем и рассылаем всем активным юзерам (упрощённо)"""
    logger.info("⏰ Scheduled digest job started")
    chat_id = context.job.chat_id if hasattr(context.job, 'chat_id') else None
    digest_text = await generate_digest()
    # Здесь: можно выбрать рассылку всем пользователям из БД; для примера — в админов
    for admin in config.ADMIN_IDS:
        await context.bot.send_message(chat_id=admin, text=digest_text[:3900])
        logger.info(f"  └─ Sent to admin: {admin}")


async def generate_digest(category: str = None) -> str:
    """Генерация дайджеста по категории"""
    logger.info(f"🔧 generate_digest called with category: {category}")

    # Словарь URL'ов по категориям
    category_urls = {
        "macro": [
            "https://uz.kursiv.media/banks/",
            "https://forbes.kz/category/finance",
            "https://lsm.kz/",
            "https://finance.kapital.kz/"
        ],
        "forex": [
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
        ],
        "commodities": [
            'https://www.inform.kz/tag/neft_t7366',
            'https://newsline.kz/ru/section/628/',
            'https://tengrinews.kz/ru/tag/%D0%BD%D0%B5%D1%84%D1%82%D1%8C/',
            'https://www.kt.kz/rus/archive_tags/%D0%9D%D0%B5%D1%84%D1%82%D1%8C'
        ],
        "banks": [
            "https://altynbank.kz/news",
            "https://alataucitybank.kz/ru/articles/news",
            "https://bankffin.kz/ru/articles",
            "https://nurbank.kz/ru/bank/press-center/news/",
            "https://bankrbk.kz/ru/media/novosti#1",
            "https://home.kz/press-center/news",
            "https://eubank.kz/news/",
            "https://www.bcc.kz/about/press-center/news/",
            "https://ir.kaspi.kz/news/",
            "https://forte.kz/ru/news",
            "https://halykbank.kz/about/press_center"
        ]
    }

    # Получаем URL'ы для категории (или все, если category="all" или None)
    if category == "all":
        urls = []
        for cat_urls in category_urls.values():
            urls.extend(cat_urls)
    else:
        urls = category_urls.get(category, config.NEWS_SOURCES)

    logger.info(f"Generating digest for category: {category}, URLs: {len(urls)}")

    # Скрапим статьи
    articles = scraper.scrape_many(urls)
    logger.info(f"✅ Scraped {len(articles)} articles")

    if not articles:
        return "⚠️ Не удалось получить данные для дайджеста. Попробуйте позже."

    # Генерируем саммари для каждой статьи
    summaries = []
    for art in articles:
        chunks = scraper.chunk_text(art['text'], max_chars=3000)
        for c in chunks:
            s = summarize_chunk(c)
            if s:
                summaries.append(f"{art.get('title', '')} — {art.get('url')}\n{s}")

    logger.info(f"✅ Generated {len(summaries)} summaries")

    if not summaries:
        return "⚠️ Не удалось создать саммари статей."

    # Агрегируем в единый дайджест
    digest = aggregate_summaries(summaries, category)
    logger.info("✅ aggregate done")

    # Сохраняем в БД
    try:
        db = get_db()
        d = Digest(
            title=f"Дайджест {datetime.utcnow().date()} - {category}",
            content=digest,
            source_metadata=str(urls),
            query="auto",
            model=config.OPENAI_MODEL
        )
        db.add(d)
        db.commit()
        db.close()
    except SQLAlchemyError as e:
        logger.exception("DB save error")

    return digest or "❌ Не получилось сгенерировать дайджест."


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка текстовых сообщений (Q&A с OpenAI)"""
    logger.info(f"💬 chat handler called: {update.message.text[:50]}")
    user_message = update.message.text

    answer = ask_openai(user_message)
    await update.message.reply_text(answer)


async def set_bot_commands(app):
    """Set the persistent menu commands."""
    logger.info("Setting bot commands...")
    commands = [
        BotCommand("start", "Запустить бота"),
        BotCommand("digest", "Финансовый дайджест"),
        BotCommand("invest", "Инвестиционные рекомендации"),
        BotCommand("compare", "Сравнение продуктов"),
        BotCommand("global", "Международные рынки"),
        BotCommand("help", "Помощь"),
        BotCommand("about", "О проекте"),
    ]
    await app.bot.set_my_commands(commands)
    logger.info("✅ Bot commands set")


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("ℹ️ about command called")
    await update.message.reply_text(
        "🤖 Финансовый Дайджест-Бот\n"
        "Создан для генерации ежедневных финансовых сводок "
        "и персонализированных инвестиционных рекомендаций.\n\n"
        "Функции:\n"
        "📊 Финансовые дайджесты по категориям\n"
        "💰 Инвестиционный анализ и рекомендации\n"
        "📈 Сравнение банковских продуктов\n"
        "🌍 Анализ международных рынков\n"
        "🤖 Q&A ассистент по финансам"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("❓ help command called")
    await update.message.reply_text(
        "💡 ДОСТУПНЫЕ КОМАНДЫ:\n\n"
        "📊 /digest — финансовый дайджест по категориям\n"
        "  • Макроэкономика\n"
        "  • Валюты\n"
        "  • Нефть и сырьё\n"
        "  • Банковский сектор\n\n"
        "💰 /invest — инвестиционные рекомендации\n"
        "  • Полный анализ рынка\n"
        "  • Персональные рекомендации\n"
        "  • Настройка риск-профиля\n\n"
        "📈 /compare — сравнение продуктов\n"
        "  • Депозиты\n"
        "  • Облигации\n"
        "  • ПИФы\n"
        "  • Брокерские платформы\n\n"
        "🌍 /global — международные рынки\n"
        "  • US Treasury Bonds\n"
        "  • Еврооблигации\n"
        "  • Золото и драгметаллы\n\n"
        "❓ /help — помощь\n"
        "ℹ️ /about — информация о проекте\n\n"
        "Также вы можете просто написать свой вопрос о финансах, "
        "и я постараюсь помочь! 💬"
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех ошибок"""
    logger.error(f"❌ Exception while handling update {update}:")
    logger.exception(context.error)


def run_bot():
    """Запуск бота"""
    logger.info("=" * 70)
    logger.info("🤖 STARTING FINANCIAL DIGEST BOT")
    logger.info("=" * 70)

    logger.info("Step 1: Initializing database...")
    init_db()
    logger.info("✅ Database initialized")

    logger.info("Step 2: Building application...")
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    logger.info("✅ Application built")

    # Error handler (должен быть первым!)
    logger.info("Step 3: Registering error handler...")
    app.add_error_handler(error_handler)

    # Middleware для логирования
    logger.info("Step 4: Adding update logger...")
    app.add_handler(MessageHandler(filters.ALL, log_update), group=-1)
    app.add_handler(CallbackQueryHandler(log_update), group=-1)

    # Command Handlers
    logger.info("Step 5: Registering command handlers...")
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("digest", digest_command))
    app.add_handler(CommandHandler("invest", invest_command))
    app.add_handler(CommandHandler("compare", compare_command))
    app.add_handler(CommandHandler("global", global_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    logger.info("  ✅ Registered 7 command handlers")

    # Callback Handlers
    logger.info("Step 6: Registering callback handlers...")
    app.add_handler(CallbackQueryHandler(digest_category_selected, pattern=r"^digest_"))
    app.add_handler(CallbackQueryHandler(investment_callback_handler, pattern=r"^invest_"))
    app.add_handler(CallbackQueryHandler(comparison_callback_handler, pattern=r"^compare_"))
    app.add_handler(CallbackQueryHandler(profile_callback_handler, pattern=r"^profile_"))
    logger.info("  ✅ Registered specialized callback handlers")

    # Catch-all для отладки (должен быть последним!)
    app.add_handler(CallbackQueryHandler(catch_all_callback))
    logger.info("  ✅ Registered catch-all callback handler")

    # Chat handler (OpenAI Q&A)
    logger.info("Step 7: Registering message handler...")
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    logger.info("  ✅ Registered chat handler")

    # JobQueue (daily digest)
    logger.info("Step 8: Setting up job queue...")
    j = app.job_queue
    j.run_daily(
        lambda ctx: asyncio.create_task(scheduled_digest_job(ctx)),
        time=dtime(config.DIGEST_HOUR, config.DIGEST_MINUTE, tzinfo=ZoneInfo(config.TIMEZONE))
    )
    logger.info(f"  ✅ Job scheduled for {config.DIGEST_HOUR:02d}:{config.DIGEST_MINUTE:02d} {config.TIMEZONE}")

    # Persistent command menu
    logger.info("Step 9: Setting bot commands...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(set_bot_commands(app))

    logger.info("=" * 70)
    logger.info("🚀 Bot started (polling)...")
    logger.info("Waiting for updates from Telegram...")
    logger.info("=" * 70)

    app.run_polling(allowed_updates=Update.ALL_TYPES)