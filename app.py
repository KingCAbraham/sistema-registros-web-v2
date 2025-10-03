# app.py
from flask import Flask, render_template, session, redirect, url_for, flash  # <-- faltaban estos
from config import Config
from blueprints.auth import auth_bp
from blueprints.registros import registros_bp
from blueprints.admin import admin_bp

app = Flask(__name__)
app.config.from_object(Config)

# Registra blueprints: ya traen su propio url_prefix en cada __init__.py
app.register_blueprint(auth_bp)        # /auth
app.register_blueprint(registros_bp)   # /registros
app.register_blueprint(admin_bp)       # /admin

# Para que layout.html sepa quién está logueado
@app.context_processor
def inject_current_user():
    return {
        "current_username": session.get("username"),
        "current_role": session.get("role"),
    }

# Raíz: sin sesión -> login; con sesión -> dashboard
@app.route("/")
def home():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    return render_template("dashboard.html")

# 413 amigable (archivo grande)
@app.errorhandler(413)
def too_large(e):
    flash("El archivo es demasiado grande. Sube un .xlsx más pequeño o pide aumentar el límite.", "danger")
    return redirect(url_for("admin.base_general"))

if __name__ == "__main__":
    # Asegúrate de tener SECRET_KEY en .env / Config para que funcione la sesión
    app.run(host="0.0.0.0", port=5000, debug=True)
