import os
from flask import Flask, render_template
from config import Config
from db import engine, Base
from blueprints.auth import auth_bp
from blueprints.registros import registros_bp
from blueprints.admin import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Asegura carpeta uploads (fallback si no viene en Config)
    app.config.setdefault("UPLOAD_FOLDER", os.path.join(os.path.dirname(__file__), "uploads"))
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Blueprints (los url_prefix ya están definidos en cada __init__.py)
    app.register_blueprint(auth_bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def home():
        return render_template("dashboard.html")

    return app

app = create_app()

if __name__ == "__main__":
    # Crear tablas en dev
    Base.metadata.create_all(bind=engine)
    app.run(host="0.0.0.0", port=5000, debug=True)
