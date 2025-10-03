# blueprints/registros/__init__.py
from flask import Blueprint

registros_bp = Blueprint("registros", __name__, url_prefix="/registros")

from . import routes  # noqa
