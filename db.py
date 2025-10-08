# db.py
import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker
from config import Config

# ----- TLS / CA -----
# En Render (Linux) existe el bundle del sistema:
DEFAULT_CA = "/etc/ssl/certs/ca-certificates.crt"
CA_PATH = os.getenv("DB_SSL_CA", DEFAULT_CA)

# ----- Engine (MySQL/TiDB) -----
# Nota: TiDB Serverless requiere TLS. Por eso pasamos connect_args["ssl"].
# Ajusta el pool si necesitas menos conexiones simultáneas.
engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,          # verifica conexiones antes de usarlas
    pool_recycle=280,            # recicla antes de que el server cierre por inactividad
    pool_size=3,                 # pools pequeños para serverless
    max_overflow=2,              # picos controlados
    future=True,                 # estilo 2.0
    connect_args={
        # TLS obligatorio para TiDB Serverless:
        "ssl": {"ca": CA_PATH},
        # (Opcional) timeouts de PyMySQL:
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
        # Deja el warning pero ahora irá por TLS y no debería fallar por transporte inseguro
        print("[WARN] No se pudo aplicar la migración automática de registros:", exc)
