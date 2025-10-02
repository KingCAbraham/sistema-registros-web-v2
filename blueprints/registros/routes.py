from flask import render_template, request, redirect, url_for, flash
from . import registros_bp  # importa el blueprint creado en __init__

@registros_bp.route("/")
def lista():
    return render_template("registros_listado.html")

@registros_bp.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    # tu lógica aquí...
    return render_template("registros_nuevo.html")
