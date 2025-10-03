# services/auth_utils.py
from functools import wraps
from flask import session, redirect, url_for, flash

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Debes iniciar sesión.", "warning")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if role not in roles:
                flash("No tienes permisos para acceder.", "danger")
                return redirect(url_for("home"))
            return view_func(*args, **kwargs)
        return wrapper
    return decorator
