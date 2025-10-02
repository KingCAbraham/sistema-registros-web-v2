import os
from flask import Flask, render_template
from config import Config
from db import engine, Base

# importa los blueprints del paquete (que ya auto-importa sus routes)
from blueprints.auth import auth_bp
from blueprints.registros import registros_bp
from blueprints.admin import admin_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.register_blueprint(auth_bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(admin_bp)

    @app.route("/")
    def home():
        return render_template("dashboard.html")

    # asegurar carpeta uploads
    upload_dir = app.config.get("UPLOAD_FOLDER")
    if not upload_dir:
        upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
        app.config["UPLOAD_FOLDER"] = upload_dir
    os.makedirs(upload_dir, exist_ok=True)

    return app

app = create_app()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    app.run(host="0.0.0.0", port=5000, debug=True)
