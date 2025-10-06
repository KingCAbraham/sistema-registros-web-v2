# db.py
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
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


def ensure_latest_schema() -> None:
    """Aplica ajustes mínimos al esquema si faltan columnas nuevas."""
    try:
        with engine.begin() as conn:
            inspector = inspect(conn)
            if "registros" not in inspector.get_table_names():
                return

            existing = {col["name"] for col in inspector.get_columns("registros")}
            statements: list[str] = []

            if "pago_inicial" not in existing:
                statements.append(
                    "ALTER TABLE registros ADD COLUMN pago_inicial DECIMAL(12,2) NULL"
                )
            if "pago_semanal" not in existing:
                statements.append(
                    "ALTER TABLE registros ADD COLUMN pago_semanal DECIMAL(12,2) NULL"
                )
            if "duracion_semanas" not in existing:
                statements.append(
                    "ALTER TABLE registros ADD COLUMN duracion_semanas INT NULL"
                )

            for statement in statements:
                conn.execute(text(statement))
    except SQLAlchemyError as exc:
        print("[WARN] No se pudo aplicar la migración automática de registros:", exc)
