# app.py
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Flask, session, redirect, url_for, flash
from config import Config
from db import ensure_latest_schema

# Blueprints (cada uno define su propio url_prefix en su __init__.py)
from blueprints.auth import auth_bp
from blueprints.registros import registros_bp
from blueprints.admin import admin_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    # Asegura la carpeta de uploads (coincide con Config.UPLOAD_FOLDER)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # ---- Migraciones mínimas ----
    ensure_latest_schema()

    # ---- Blueprints ----
    app.register_blueprint(auth_bp)       # /auth
    app.register_blueprint(registros_bp)  # /registros
    app.register_blueprint(admin_bp)      # /admin

    # ---- Contexto para templates (layout.html) ----
    @app.context_processor
    def inject_current_user():
        return {
            "current_username": session.get("username"),
            "current_role": session.get("role"),
        }

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

    # ---- Rutas raíz / utilidades ----
    @app.route("/")
    def home():
        """Si no hay sesión => login. Si hay sesión => dashboard."""
        if not session.get("user_id"):
            return redirect(url_for("auth.login"))
        return redirect(url_for("registros.listado"))

    # Opcional: pequeña ruta de salud para pruebas de despliegue
    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    # ---- Manejo de errores ----
    @app.errorhandler(413)
    def too_large(e):
        mb = app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024)
        if mb:
            flash(f"El archivo excede el límite de {mb} MB.", "danger")
        else:
            flash("El archivo es demasiado grande.", "danger")
        return redirect(url_for("admin.base_general"))

    return app


app = create_app()

if __name__ == "__main__":
    # Asegúrate de tener SECRET_KEY en tu .env o en Config para manejar sesión
    app.run(host="0.0.0.0", port=5000, debug=True)
