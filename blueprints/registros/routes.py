# blueprints/registros/routes.py
import os
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.orm import selectinload

from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    session, jsonify, current_app, send_from_directory, abort
)
from werkzeug.utils import secure_filename

from db import SessionLocal
from models import Registro, BaseGeneral, TipoConvenio, BocaCobranza
from . import registros_bp


# ----------------- Helpers de auth -----------------
def require_agent():
    role = session.get("role")
    if role not in ("agente", "admin", "supervisor", "gerente"):
        flash("Inicia sesión.", "warning")
        return False
    return True


# ----------------- Helpers de archivos -----------------
def _allowed(filename: str) -> bool:
    """Verifica extensión permitida contra Config.ALLOWED_EXTENSIONS."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", set())


def _save_upload(file_storage):
    """
    Guarda un FileStorage en UPLOAD_FOLDER con nombre seguro + UUID.
    Devuelve el nombre de archivo guardado (str) o None si no se envió.
    Lanza ValueError si la extensión no es válida.
    """
    if not file_storage or file_storage.filename == "":
        return None

    if not _allowed(file_storage.filename):
        raise ValueError("Extensión no permitida (usa pdf, png, jpg, jpeg).")

    base = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(base, exist_ok=True)

    safe = secure_filename(file_storage.filename)
    unique = f"{uuid.uuid4().hex}_{safe}"
    file_storage.save(os.path.join(base, unique))
    return unique


# ----------------- Listado -----------------
@registros_bp.get("/")
def listado():
    if not require_agent():
        return redirect(url_for("auth.login"))
    user_id = session.get("user_id")
    with SessionLocal() as db:
        q = (
            db.query(Registro)
            .options(
                selectinload(Registro.tipo_convenio),
                selectinload(Registro.boca_cobranza),
            )
        )
        if session.get("role") == "agente":
            q = q.filter(Registro.creado_por == user_id)
        regs = q.order_by(Registro.id.desc()).limit(100).all()
    return render_template("registros_listado.html", registros=regs)
# ----------------- Nuevo registro (form) -----------------
@registros_bp.get("/nuevo")
def nuevo():
    if not require_agent():
        return redirect(url_for("auth.login"))
    with SessionLocal() as db:
        tipos = (
            db.query(TipoConvenio)
            .filter(TipoConvenio.activo == 1)
            .order_by(TipoConvenio.nombre.asc())
            .all()
        )
        bocas = (
            db.query(BocaCobranza)
            .filter(BocaCobranza.activo == 1)
            .order_by(BocaCobranza.nombre.asc())
            .all()
        )
    return render_template("registros_nuevo.html", tipos=tipos, bocas=bocas)


# ----------------- API: Autocomplete por cliente_unico -----------------
@registros_bp.get("/api/search_cliente")
def api_search_cliente():
    """Devuelve sugerencias por cliente_unico prefix (hasta 10)."""
    if not require_agent():
        return jsonify([]), 401

    term = (request.args.get("term") or "").strip()
    if len(term) < 2:
        return jsonify([])

    with SessionLocal() as db:
        rows = (
            db.query(BaseGeneral.cliente_unico, BaseGeneral.nombre_cte)
            .filter(BaseGeneral.cliente_unico.like(f"{term}%"))
            .order_by(BaseGeneral.cliente_unico.asc())
            .limit(10)
            .all()
        )
    return jsonify([{"cliente_unico": r[0], "nombre_cte": r[1] or ""} for r in rows])


# ----------------- API: Datos exactos del cliente -----------------
@registros_bp.get("/api/datos_cliente")
def api_datos_cliente():
    if not require_agent():
        return jsonify({"ok": False, "error": "no-auth"}), 401
    cu = (request.args.get("cu") or "").strip()
    if not cu:
        return jsonify({"ok": False, "error": "cu-vacio"}), 400

    with SessionLocal() as db:
        row = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cu).first()
    if not row:
        return jsonify({"ok": False, "error": "no-encontrado"}), 404

    return jsonify(
        {
            "ok": True,
            "data": {
                "nombre_cte": row.nombre_cte or "",
                "gerencia": row.gerencia or "",
                "producto": row.producto or "",
                "fidiapago": row.fidiapago or "",
                "gestion_desc": row.gestion_desc or "",
            },
        }
    )


# (opcional) versión POST legacy
@registros_bp.post("/buscar_cliente")
def buscar_cliente():
    if not require_agent():
        return redirect(url_for("auth.login"))
    cliente_unico = (request.form.get("cliente_unico") or "").strip()
    if not cliente_unico:
        return {"ok": False, "error": "cliente_unico vacío"}, 400

    with SessionLocal() as db:
        row = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cliente_unico).first()

    if not row:
        return {"ok": False, "error": "Cliente no encontrado en base del día"}, 404

    return {
        "ok": True,
        "data": {
            "nombre_cte": row.nombre_cte or "",
            "gerencia": row.gerencia or "",
            "producto": row.producto or "",
            "fidiapago": row.fidiapago or "",
            "gestion_desc": row.gestion_desc or "",
        },
    }


# ----------------- Crear registro (con archivos) -----------------
@registros_bp.post("/crear")
def crear():
    if not require_agent():
        return redirect(url_for("auth.login"))

    form = request.form
    files = request.files
    user_id = session.get("user_id")

    cliente_unico = (form.get("cliente_unico") or "").strip()
    tipo_convenio_id = form.get("tipo_convenio_id")
    boca_cobranza_id = form.get("boca_cobranza_id")
    fecha_promesa = form.get("fecha_promesa")
    telefono = (form.get("telefono") or "").strip()
    semana = form.get("semana")
    notas = (form.get("notas") or "").strip()
    pago_inicial_raw = (form.get("pago_inicial") or "").strip()
    pago_semanal_raw = (form.get("pago_semanal") or "").strip()
    duracion_raw = (form.get("duracion_semanas") or "").strip()

    def parse_currency(value: str) -> Decimal | None:
        if not value:
            return None
        cleaned = (
            value.replace("MXN", "")
            .replace("$", "")
            .replace("\u00a0", " ")
            .replace(" ", "")
        )
        if "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        cleaned = cleaned.replace(",", "")
        if not cleaned:
            return None
        try:
            return Decimal(cleaned).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            raise ValueError("Formato de moneda inválido")

    try:
        pago_inicial = parse_currency(pago_inicial_raw)
        pago_semanal = parse_currency(pago_semanal_raw)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("registros.nuevo"))

    duracion_semanas = None
    if duracion_raw:
        try:
            duracion_val = int(duracion_raw)
        except ValueError:
            flash("Duración en semanas inválida", "danger")
            return redirect(url_for("registros.nuevo"))
        if duracion_val < 1:
            flash("La duración debe ser al menos de una semana", "danger")
            return redirect(url_for("registros.nuevo"))
        duracion_semanas = duracion_val

    if not cliente_unico:
        flash("Cliente único es obligatorio", "warning")
        return redirect(url_for("registros.nuevo"))

    with SessionLocal() as db:
        base = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cliente_unico).first()
        if not base:
            flash("Cliente no existe en la base del día", "danger")
            return redirect(url_for("registros.nuevo"))

        # --- Guardar archivos (si vienen) ---
        try:
            archivo_convenio = _save_upload(files.get("archivo_convenio"))
            archivo_pago = _save_upload(files.get("archivo_pago"))
            archivo_gestion = _save_upload(files.get("archivo_gestion"))
        except Exception as e:
            flash(f"Error en archivos: {e}", "danger")
            return redirect(url_for("registros.nuevo"))

        reg = Registro(
            cliente_unico=cliente_unico,
            nombre_cte_snap=base.nombre_cte,
            gerencia_snap=base.gerencia,
            producto_snap=base.producto,
            fidiapago_snap=base.fidiapago,
            gestion_desc_snap=base.gestion_desc,
            tipo_convenio_id=int(tipo_convenio_id),
            boca_cobranza_id=int(boca_cobranza_id),
            fecha_promesa=date.fromisoformat(fecha_promesa) if fecha_promesa else date.today(),
            telefono=telefono or None,
            semana=int(semana) if semana else None,
            pago_inicial=pago_inicial,
            pago_semanal=pago_semanal,
            duracion_semanas=duracion_semanas,
            notas=notas or None,
            creado_por=user_id,

            # nuevos campos de evidencia
            archivo_convenio=archivo_convenio,
            archivo_pago=archivo_pago,
            archivo_gestion=archivo_gestion,
        )
        db.add(reg)
        db.commit()

    flash("Registro creado", "success")
    return redirect(url_for("registros.listado"))


# ----------------- Servir archivo (protegido) -----------------
@registros_bp.get("/file/<string:fname>")
def get_file(fname):
    """Sirve un archivo desde UPLOAD_FOLDER; requiere sesión."""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    if "/" in fname or "\\" in fname:
        abort(400)

    base = current_app.config["UPLOAD_FOLDER"]
    full = os.path.join(base, fname)
    if not os.path.isfile(full):
        abort(404)
    return send_from_directory(base, fname, as_attachment=False)

@registros_bp.get("/resumen")
def resumen():
    if not require_agent():
        return redirect(url_for("auth.login"))

    semana = request.args.get("semana", type=int)
    user_id = session.get("user_id")

    with SessionLocal() as db:
        q = db.query(Registro).filter(Registro.creado_por == user_id)
        if semana:
            q = q.filter(Registro.semana == semana)
        registros = q.order_by(Registro.id.desc()).all()

        # Totales simples
        total = len(registros)
        total_pagos_inicial = Decimal("0")
        total_pagos_semanal = Decimal("0")
        # por tipo / boca
        por_tipo = {}
        por_boca = {}
        for r in registros:
            t = r.tipo_convenio.nombre if r.tipo_convenio else "(s/tipo)"
            b = r.boca_cobranza.nombre if r.boca_cobranza else "(s/boca)"
            por_tipo[t] = por_tipo.get(t, 0) + 1
            por_boca[b] = por_boca.get(b, 0) + 1
            if r.pago_inicial:
                total_pagos_inicial += r.pago_inicial
            if r.pago_semanal:
                total_pagos_semanal += r.pago_semanal

    return render_template(
        "registros_resumen.html",
        registros=registros,
        semana=semana,
        total=total,
        por_tipo=por_tipo,
        por_boca=por_boca,
        total_pagos_inicial=total_pagos_inicial,
        total_pagos_semanal=total_pagos_semanal,
    )
