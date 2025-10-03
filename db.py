# db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import Config

engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_recycle=280,
    pool_size=5,
    max_overflow=10,
    future=True,
    connect_args={
        "connect_timeout": 15,
        "read_timeout": 60,
        "write_timeout": 60,
    },
)

# Fábrica de sesiones para usar con "with SessionLocal() as db:"
SessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
    future=True,
)

# Base declarativa para tus modelos
Base = declarative_base()
