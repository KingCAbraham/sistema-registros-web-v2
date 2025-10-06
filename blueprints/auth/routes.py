from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from db import SessionLocal
from models import Usuario
from . import auth_bp  # IMPORTA el blueprint ya creado en __init__.py

@auth_bp.get("/login")
def login():
    return render_template("login.html")

@auth_bp.post("/login")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        flash("Usuario y contraseña son obligatorios", "warning")
        return redirect(url_for("auth.login"))

    with SessionLocal() as db:
        user = db.query(Usuario).filter(Usuario.username == username, Usuario.activo == 1).first()

    if not user or not check_password_hash(user.password_hash, password):
        flash("Credenciales inválidas", "danger")
        return redirect(url_for("auth.login"))

    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role

    flash(f"Bienvenido, {user.username}", "success")

    if user.role == "admin":
        destino = "admin.index"
    else:
        destino = "registros.listado"

    return redirect(url_for(destino))

@auth_bp.get("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada", "success")
    return redirect(url_for("auth.login"))
