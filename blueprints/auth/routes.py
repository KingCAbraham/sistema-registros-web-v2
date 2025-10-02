# blueprints/auth/routes.py
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
import pymysql
import os

from . import auth_bp
from .forms import LoginForm

from dotenv import load_dotenv
load_dotenv()

DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "4000"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME", "sistema_registros")
DB_SSL_CA = os.getenv("DB_SSL_CA")

def get_conn():
    return pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, ssl={"ca": DB_SSL_CA}
    )

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():  # sólo True en POST con CSRF OK y campos válidos
        username = form.username.data.strip()
        password = form.password.data

        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, password_hash, role, activo FROM usuarios WHERE username=%s", (username,))
            row = cur.fetchone()

        if not row:
            flash("Usuario o contraseña inválidos.", "danger")
            return render_template("login.html", form=form)

        user_id, password_hash, role, activo = row
        if not activo:
            flash("Usuario inactivo.", "warning")
            return render_template("login.html", form=form)

        if not check_password_hash(password_hash, password):
            flash("Usuario o contraseña inválidos.", "danger")
            return render_template("login.html", form=form)

        session["user_id"] = user_id
        session["username"] = username
        session["role"] = role
        flash(f"Bienvenido, {username}", "success")
        return redirect(url_for("home"))

    # GET o POST inválido → renderiza con errores
    return render_template("login.html", form=form)

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.", "success")
    return redirect(url_for("home"))
