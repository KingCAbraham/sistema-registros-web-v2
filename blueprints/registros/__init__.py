from flask import Blueprint

# crea el blueprint aquí
registros_bp = Blueprint("registros", __name__, url_prefix="/registros")

# importa las rutas para registrarlas en el blueprint
from . import routes  # noqa: E402,F401
