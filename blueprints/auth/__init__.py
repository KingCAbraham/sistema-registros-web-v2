# blueprints/auth/__init__.py
from flask import Blueprint

# un solo blueprint, sin template_folder raro
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# importa las rutas para que se adjunten a ESTE blueprint
from . import routes  # noqa: E402,F401
