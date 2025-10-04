import os
from dotenv import load_dotenv
load_dotenv()

def _build_uri():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "4000")
    user = os.getenv("DB_USER")
    pwd  = os.getenv("DB_PASSWORD")
    db   = os.getenv("DB_NAME", "sistema_registros")
    ca   = os.getenv("DB_SSL_CA", "")

    if not (host and user and pwd):
        return None

    ca_param = ""
    if ca:
        # escapar backslashes en Windows para URL
        ca_norm = ca.replace("\\", "\\\\")
        ca_param = (
            f"&ssl_ca={ca_norm}"
            f"&ssl_verify_cert=true&ssl_verify_identity=true"
        )

    return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{db}?charset=utf8mb4{ca_param}"

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = _build_uri()

    # --- uploads ---
    # 25 MB reales (y el comentario coincide)
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024
    # Guardar dentro de static/uploads para servir con url_for('static', filename=...)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
