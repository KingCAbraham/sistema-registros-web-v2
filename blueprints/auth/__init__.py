# blueprints/auth/__init__.py
from flask import Blueprint

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# IMPORTANTE: importar routes para que se registren las rutas
from . import routes  # noqa: E402,F401
