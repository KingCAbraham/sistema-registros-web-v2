# utils/authz.py
from functools import wraps
from flask import session, abort

def role_required(*allowed_roles):
    """
    Permite entrar sólo si session['role'] está en allowed_roles.
    Ejemplo: @role_required('agente')  o  @role_required('admin','gerente')
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if role not in allowed_roles:
                # 403 Forbidden si el rol no está permitido
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator
