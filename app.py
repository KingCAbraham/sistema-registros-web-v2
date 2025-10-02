import os
from flask import Flask, render_template
from config import Config
from db import engine, Base
from blueprints.auth.routes import auth_bp
from blueprints.registros.routes import registros_bp
from blueprints.admin.routes import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(registros_bp, url_prefix="/registros")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.route("/")
    def home():
        return render_template("dashboard.html")

    # Asegura carpeta uploads
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    return app

app = create_app()

if __name__ == "__main__":
    # Crea tablas si no existen (dev)
    Base.metadata.create_all(bind=engine)
    app.run(host="0.0.0.0", port=5000, debug=True)
