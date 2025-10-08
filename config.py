import os

BASE_DIR = os.path.dirname(__file__)

def _build_mysql_uri():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "4000")
    user = os.getenv("DB_USER")
    pwd  = os.getenv("DB_PASSWORD")
    db   = os.getenv("DB_NAME", "sistema_registros")

    if not (host and user and pwd):
        return None

    # PyMySQL + utf8mb4
    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4"

def _db_url():
    """
    Prioridad:
    1) SQLALCHEMY_DATABASE_URI (si la defines directa)
    2) DATABASE_URL (p. ej. Postgres de Render)
    3) Construida desde DB_HOST/DB_USER/DB_PASSWORD/...
    """
    return (
        os.getenv("SQLALCHEMY_DATABASE_URI")
        or os.getenv("DATABASE_URL")
        or _build_mysql_uri()
    )

class Config:
    # --- Flask ---
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")

    # --- SQLAlchemy ---
    SQLALCHEMY_DATABASE_URI = _db_url()

    # --- Uploads ---
    # Si existe UPLOAD_FOLDER en el entorno (p. ej. /var/tmp/uploads en Render), se usa.
    # Si no, cae a static/uploads dentro del proyecto.
    UPLOAD_FOLDER = os.getenv(
        "UPLOAD_FOLDER",
        os.path.join(BASE_DIR, "static", "uploads"),
    )

    # 25 MB
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024

    # Extensiones permitidas (ajústalas si necesitas otras)
    ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
