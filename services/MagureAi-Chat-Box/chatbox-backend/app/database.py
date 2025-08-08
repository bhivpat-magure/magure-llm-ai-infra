from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

# Create SQLAlchemy engine with connection pooling and other optimizations
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=5,         # Number of connections to keep open
    max_overflow=10,     # Number of connections to allow in overflow
    pool_timeout=30,     # Seconds to wait before giving up on getting a connection
    pool_recycle=1800    # Recycle connections after 30 minutes
)

print(f"Database URL: {settings.DATABASE_URL}")

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False  # This is important for async operations
)


def get_db():
    db = SessionLocal()
    try:
        yield db
        print("Database session yielded")
    finally:
        db.close()

# Base class for all models
Base = declarative_base()
