# app.py
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Flask, session, redirect, url_for, flash
from config import Config
from db import ensure_latest_schema

# Blueprints
from blueprints.auth import auth_bp
from blueprints.registros import registros_bp
from blueprints.admin import admin_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # --- Asegurar carpeta de uploads con fallback robusto ---
    default_upload = os.path.join(os.path.dirname(__file__), "static", "uploads")
    upload_dir = app.config.get("UPLOAD_FOLDER") or os.getenv("UPLOAD_FOLDER") or default_upload
    os.makedirs(upload_dir, exist_ok=True)
    app.config["UPLOAD_FOLDER"] = upload_dir  # fijamos el valor final

    # --- Migraciones mínimas / esquema ---
    ensure_latest_schema()

    # --- Blueprints ---
    app.register_blueprint(auth_bp)       # /auth
    app.register_blueprint(registros_bp)  # /registros
    app.register_blueprint(admin_bp)      # /admin

    # --- Contexto global para templates ---
    @app.context_processor
    def inject_current_user():
        return {
            "current_username": session.get("username"),
            "current_role": session.get("role"),
        }

    # --- Filtro de moneda MX ---
    @app.template_filter("currency_mx")
    def currency_mx(value):
        if value in (None, ""):
            return "—"
        try:
            amount = Decimal(value)
        except (InvalidOperation, TypeError, ValueError):
            return str(value)
        quantized = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        formatted = f"{quantized:,.2f}"
        return f"$ {formatted}"

    # --- Rutas base / utilidades ---
    @app.route("/")
    def home():
        """Si no hay sesión => login. Si hay sesión => dashboard de registros."""
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return redirect(url_for("registros.listado"))

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    # --- Manejo de errores ---
    @app.errorhandler(413)
    def too_large(e):
        mb = app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024)
        if mb:
            flash(f"El archivo excede el límite de {mb} MB.", "danger")
        else:
            flash("El archivo es demasiado grande.", "danger")
        return redirect(url_for("admin.base_general"))

    return app


# Para gunicorn "app:app"
app = create_app()

if __name__ == "__main__":
    # Asegúrate de tener SECRET_KEY en el entorno para sesión en producción.
    app.run(host="0.0.0.0", port=5000, debug=True)
