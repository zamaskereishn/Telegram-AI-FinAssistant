"""
Database models and session management
"""
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from datetime import datetime
from config import config
from loguru import logger

Base = declarative_base()


class User(Base):
    """Модель пользователя"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    first_name = Column(String(255))
    last_name = Column(String(255))

    # Инвестиционный профиль
    risk_profile = Column(String(50), default='medium')  # low, medium, high
    investment_horizon = Column(String(50), default='medium')  # short, medium, long
    investment_amount = Column(Float, nullable=True)
    preferred_currency = Column(String(10), default='KZT')

    # Предпочтения
    preferred_categories = Column(Text)  # JSON список категорий
    notification_enabled = Column(Boolean, default=True)
    notification_time = Column(String(10), default='09:00')

    # Метаданные
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.username})>"


class Digest(Base):
    """Модель сгенерированного дайджеста"""
    __tablename__ = 'digests'

    id = Column(Integer, primary_key=True)
    title = Column(String(500))
    content = Column(Text)
    category = Column(String(100))  # macro, forex, commodities, banks, all

    # Метаданные генерации
    source_metadata = Column(Text)  # JSON с источниками
    query = Column(String(500))
    model = Column(String(100))

    # Статистика
    generation_time = Column(Float)  # секунды
    tokens_used = Column(Integer)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    scheduled_for = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Digest(id={self.id}, category={self.category}, created={self.created_at})>"


class InvestmentReport(Base):
    """Модель инвестиционного отчёта"""
    __tablename__ = 'investment_reports'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)  # telegram_id пользователя

    # Параметры запроса
    risk_profile = Column(String(50))
    investment_horizon = Column(String(50))
    investment_amount = Column(Float, nullable=True)

    # Контент
    title = Column(String(500))
    content = Column(Text)
    market_conditions = Column(Text)
    recommendations = Column(Text)

    # Метаданные
    source_metadata = Column(Text)  # JSON с источниками
    model = Column(String(100))
    generation_time = Column(Float)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<InvestmentReport(id={self.id}, user={self.user_id}, created={self.created_at})>"


class ProductComparison(Base):
    """Модель сравнения продуктов"""
    __tablename__ = 'product_comparisons'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)

    # Тип продукта
    product_type = Column(String(100))  # deposits, bonds, mutual_funds, brokers

    # Контент
    title = Column(String(500))
    content = Column(Text)
    top_products = Column(Text)  # JSON с ТОП-3

    # Метаданные
    source_metadata = Column(Text)
    products_analyzed = Column(Integer)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ProductComparison(id={self.id}, type={self.product_type})>"


class Query(Base):
    """Модель пользовательского запроса (для Q&A)"""
    __tablename__ = 'queries'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer)

    # Запрос и ответ
    question = Column(Text)
    answer = Column(Text)

    # Метаданные
    model = Column(String(100))
    tokens_used = Column(Integer)
    response_time = Column(Float)

    # Оценка пользователя
    rating = Column(Integer, nullable=True)  # 1-5
    feedback = Column(Text, nullable=True)

    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Query(id={self.id}, user={self.user_id}, created={self.created_at})>"


class ScrapingLog(Base):
    """Логи скрапинга для мониторинга"""
    __tablename__ = 'scraping_logs'

    id = Column(Integer, primary_key=True)
    url = Column(String(1000))
    category = Column(String(100))

    # Результат
    success = Column(Boolean)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    # Метрики
    response_time = Column(Float)
    content_length = Column(Integer, nullable=True)
    articles_extracted = Column(Integer, default=0)

    # Временные метки
    scraped_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ScrapingLog(url={self.url}, success={self.success})>"


# Database engine and session
engine = None
SessionLocal = None


def init_db():
    """Инициализация базы данных"""
    global engine, SessionLocal

    try:
        logger.info(f"Connecting to database: {config.DATABASE_URL.split('@')[1] if '@' in config.DATABASE_URL else 'configured'}")

        engine = create_engine(
            config.DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )

        # Создаём таблицы
        Base.metadata.create_all(engine)
        logger.success("✅ Database tables created/verified")

        # Создаём session factory
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        # Проверяем подключение

        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
            logger.success("✅ Database connection verified")
        finally:
            session.close()


    except Exception as e:
        logger.error(f"❌ Database initialization error: {e}")
        raise


def get_db():
    """Получить сессию базы данных"""
    if SessionLocal is None:
        init_db()
    return SessionLocal()


def get_or_create_user(telegram_id: int, username: str = None,
                       first_name: str = None, last_name: str = None) -> User:
    """Получить или создать пользователя"""
    db = get_db()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()

        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new user: {telegram_id} (@{username})")
        else:
            # Обновляем last_active
            user.last_active = datetime.utcnow()
            if username:
                user.username = username
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            db.commit()

        return user
    finally:
        db.close()


def update_user_profile(telegram_id: int, **kwargs) -> bool:
    """Обновить профиль пользователя"""
    db = get_db()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            return False

        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)

        db.commit()
        logger.info(f"Updated profile for user {telegram_id}: {kwargs}")
        return True
    except Exception as e:
        logger.error(f"Error updating user profile: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def save_digest(title: str, content: str, category: str,
                source_metadata: str, query: str, model: str,
                generation_time: float = None, tokens_used: int = None) -> Digest:
    """Сохранить дайджест"""
    db = get_db()
    try:
        digest = Digest(
            title=title,
            content=content,
            category=category,
            source_metadata=source_metadata,
            query=query,
            model=model,
            generation_time=generation_time,
            tokens_used=tokens_used
        )
        db.add(digest)
        db.commit()
        db.refresh(digest)
        logger.info(f"Saved digest: {digest.id} ({category})")
        return digest
    finally:
        db.close()


def save_investment_report(user_id: int, title: str, content: str,
                           market_conditions: str, recommendations: str,
                           risk_profile: str, investment_horizon: str,
                           investment_amount: float = None,
                           source_metadata: str = None, model: str = None,
                           generation_time: float = None) -> InvestmentReport:
    """Сохранить инвестиционный отчёт"""
    db = get_db()
    try:
        report = InvestmentReport(
            user_id=user_id,
            title=title,
            content=content,
            market_conditions=market_conditions,
            recommendations=recommendations,
            risk_profile=risk_profile,
            investment_horizon=investment_horizon,
            investment_amount=investment_amount,
            source_metadata=source_metadata,
            model=model,
            generation_time=generation_time
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        logger.info(f"Saved investment report: {report.id} for user {user_id}")
        return report
    finally:
        db.close()


def get_user_stats(telegram_id: int) -> dict:
    """Получить статистику пользователя"""
    db = get_db()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            return {}

        queries_count = db.query(Query).filter(Query.user_id == telegram_id).count()
        reports_count = db.query(InvestmentReport).filter(InvestmentReport.user_id == telegram_id).count()

        return {
            'joined': user.created_at,
            'last_active': user.last_active,
            'queries': queries_count,
            'reports': reports_count,
            'risk_profile': user.risk_profile,
            'investment_horizon': user.investment_horizon
        }
    finally:
        db.close()


def cleanup_old_data(days: int = 90):
    """Очистка старых данных (для maintenance)"""
    db = get_db()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Удаляем старые логи скрапинга
        deleted = db.query(ScrapingLog).filter(ScrapingLog.scraped_at < cutoff_date).delete()
        logger.info(f"Deleted {deleted} old scraping logs")

        # Можно добавить очистку других таблиц

        db.commit()
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")
        db.rollback()
    finally:
        db.close()


# Export для импорта
__all__ = [
    'Base',
    'User',
    'Digest',
    'InvestmentReport',
    'ProductComparison',
    'Query',
    'ScrapingLog',
    'init_db',
    'get_db',
    'get_or_create_user',
    'update_user_profile',
    'save_digest',
    'save_investment_report',
    'get_user_stats',
    'cleanup_old_data',
]