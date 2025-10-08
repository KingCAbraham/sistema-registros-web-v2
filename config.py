import os
from sqlalchemy import create_engine

def _build_mysql_uri():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "4000")
    user = os.getenv("DB_USER")
    pwd  = os.getenv("DB_PASSWORD")
    db   = os.getenv("DB_NAME", "sistema_registros")

    if not (host and user and pwd):
        return None

    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"

def _db_url():
    # Permite usar DATABASE_URL si lo expone la plataforma (p. ej., Postgres en Render)
    return os.getenv("SQLALCHEMY_DATABASE_URI") or os.getenv("DATABASE_URL") or _build_mysql_uri()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = _db_url()

# --- crear engine con SSL en Linux (Render) ---
DB_URL = Config.SQLALCHEMY_DATABASE_URI
if not DB_URL:
    raise RuntimeError(
        "Faltan variables para construir la URL de la base de datos "
        "(define DB_HOST, DB_USER, DB_PASSWORD, etc. en el entorno)."
    )

# Usa el CA del sistema en Render/Linux
CA_PATH = os.getenv("DB_SSL_CA", "/etc/ssl/certs/ca-certificates.crt")

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    connect_args={"ssl": {"ca": CA_PATH}},
)