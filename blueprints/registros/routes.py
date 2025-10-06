# blueprints/registros/routes.py
"""Rutas del blueprint de registros."""
from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from markupsafe import Markup, escape
from sqlalchemy.orm import selectinload
from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
    current_app,
    send_from_directory,
    abort,
)
from werkzeug.utils import secure_filename

from db import SessionLocal
from models import Registro, BaseGeneral, TipoConvenio, BocaCobranza
from . import registros_bp


# ---------------------------------------------------------------------------
# Helpers de autenticación
# ---------------------------------------------------------------------------
def require_agent() -> bool:
    role = session.get("role")
    if role not in {"agente", "admin", "supervisor", "gerente"}:
        flash("Inicia sesión.", "warning")
        return False
    return True


# ---------------------------------------------------------------------------
# Helpers de archivos / parsing / formato
# ---------------------------------------------------------------------------
def _allowed(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", set())


def _save_upload(file_storage):
    """Guarda archivo en UPLOAD_FOLDER con nombre seguro+UUID. Devuelve nombre o None."""
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


def _delete_file(fname: str | None) -> None:
    if not fname:
        return
    base = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(base, fname)
    try:
        os.remove(path)
    except OSError:
        pass


def _parse_currency(raw: str | None) -> Decimal | None:
    if not raw:
        return None
    cleaned = (
        raw.replace("MXN", "")
        .replace("$", "")
        .replace("\u00a0", " ")
        .replace(" ", "")
    )
    # si viene con separador europeo "1.234,56"
    if "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    cleaned = cleaned.replace(",", "")
    if not cleaned:
        return None
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Formato de moneda inválido") from exc
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_duration(raw: str | None) -> int | None:
    if not raw:
        return None
    try:
        weeks = int(raw)
    except ValueError as exc:
        raise ValueError("Duración en semanas inválida") from exc
    if weeks < 1:
        raise ValueError("La duración debe ser al menos de una semana")
    return weeks


def _parse_fecha(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("Fecha promesa inválida") from exc


def _format_currency(value) -> str:
    if value is None:
        return ""
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    return f"${number:,.2f}"


def _build_select_options(items, selected_id, placeholder="Selecciona una opción") -> Markup:
    placeholder_selected = selected_id in (None, "")
    options: list[str] = [
        f'<option value="" disabled{" selected" if placeholder_selected else ""}>{escape(placeholder)}</option>'
    ]
    for item in items:
        value = escape(str(getattr(item, "id", "")))
        label = escape(getattr(item, "nombre", ""))
        selected = " selected" if selected_id == getattr(item, "id", None) else ""
        options.append(f'<option value="{value}"{selected}>{label}</option>')
    return Markup("\n".join(options))


def _load_catalogos(db):
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
    return tipos, bocas


def _aplicar_snapshot(registro: Registro, base: BaseGeneral) -> None:
    registro.nombre_cte_snap = base.nombre_cte
    registro.gerencia_snap = base.gerencia
    registro.producto_snap = base.producto
    registro.fidiapago_snap = base.fidiapago
    registro.gestion_desc_snap = base.gestion_desc


# ---------------------------------------------------------------------------
# Vistas
# ---------------------------------------------------------------------------
@registros_bp.get("/")
def listado():
    if not require_agent():
        return redirect(url_for("auth.login"))

    user_id = session.get("user_id")
    role = session.get("role")

    with SessionLocal() as db:
        q = (
            db.query(Registro)
            .options(
                selectinload(Registro.tipo_convenio),
                selectinload(Registro.boca_cobranza),
            )
        )
        if role == "agente":
            q = q.filter(Registro.creado_por == user_id)
        regs = q.order_by(Registro.id.desc()).limit(100).all()

    return render_template(
        "registros_listado.html",
        registros=regs,
        role=role,
        user_id=user_id,
    )


@registros_bp.get("/nuevo")
def nuevo():
    if not require_agent():
        return redirect(url_for("auth.login"))

    with SessionLocal() as db:
        tipos, bocas = _load_catalogos(db)

    # Tu template original itera sobre `tipos` y `bocas`
    return render_template(
        "registros_nuevo.html",
        tipos=tipos,
        bocas=bocas,
        registro=None,
        is_edit=False,
        format_currency=_format_currency,
    )


@registros_bp.get("/<int:registro_id>/editar")
def editar(registro_id: int):
    if not require_agent():
        return redirect(url_for("auth.login"))

    user_id = session.get("user_id")
    role = session.get("role")

    with SessionLocal() as db:
        registro = (
            db.query(Registro)
            .options(
                selectinload(Registro.tipo_convenio),
                selectinload(Registro.boca_cobranza),
            )
            .filter(Registro.id == registro_id)
            .first()
        )
        if not registro:
            abort(404)
        if role == "agente" and registro.creado_por != user_id:
            abort(403)

        tipos, bocas = _load_catalogos(db)

    return render_template(
        "registros_nuevo.html",
        tipos=tipos,
        bocas=bocas,
        registro=registro,
        is_edit=True,
        format_currency=_format_currency,
    )


# ----------------- APIs de ayuda (autocomplete / autollenado) -----------------
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
    return jsonify([{"cliente_unico": cu, "nombre_cte": nombre or ""} for cu, nombre in rows])


@registros_bp.get("/api/datos_cliente")
def api_datos_cliente():
    if not require_agent():
        return jsonify({"ok": False, "error": "no-auth"}), 401

    cliente_unico = (request.args.get("cu") or "").strip()
    if not cliente_unico:
        return jsonify({"ok": False, "error": "cu-vacio"}), 400

    with SessionLocal() as db:
        base = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cliente_unico).first()

    if not base:
        return jsonify({"ok": False, "error": "no-encontrado"}), 404

    return jsonify(
        {
            "ok": True,
            "data": {
                "nombre_cte": base.nombre_cte or "",
                "gerencia": base.gerencia or "",
                "producto": base.producto or "",
                "fidiapago": base.fidiapago or "",
                "gestion_desc": base.gestion_desc or "",
            },
        }
    )


@registros_bp.post("/buscar_cliente")
def buscar_cliente():
    """Compatibilidad con la búsqueda legacy via POST."""
    if not require_agent():
        return redirect(url_for("auth.login"))

    cliente_unico = (request.form.get("cliente_unico") or "").strip()
    if not cliente_unico:
        return {"ok": False, "error": "cliente_unico vacío"}, 400

    with SessionLocal() as db:
        base = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cliente_unico).first()

    if not base:
        return {"ok": False, "error": "Cliente no encontrado en base del día"}, 404

    return {
        "ok": True,
        "data": {
            "nombre_cte": base.nombre_cte or "",
            "gerencia": base.gerencia or "",
            "producto": base.producto or "",
            "fidiapago": base.fidiapago or "",
            "gestion_desc": base.gestion_desc or "",
        },
    }


# ----------------- Crear / Actualizar -----------------
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
    fecha_promesa_raw = form.get("fecha_promesa")
    telefono = (form.get("telefono") or "").strip()
    semana_raw = form.get("semana")
    notas = (form.get("notas") or "").strip()
    pago_inicial_raw = (form.get("pago_inicial") or "").strip()
    pago_semanal_raw = (form.get("pago_semanal") or "").strip()
    duracion_raw = (form.get("duracion_semanas") or "").strip()

    try:
        pago_inicial = _parse_currency(pago_inicial_raw)
        pago_semanal = _parse_currency(pago_semanal_raw)
        duracion_semanas = _parse_duration(duracion_raw)
        fecha_promesa = _parse_fecha(fecha_promesa_raw)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("registros.nuevo"))

    if not cliente_unico:
        flash("Cliente único es obligatorio", "warning")
        return redirect(url_for("registros.nuevo"))

    try:
        tipo_convenio_id_int = int(tipo_convenio_id)
        boca_cobranza_id_int = int(boca_cobranza_id)
    except (TypeError, ValueError):
        flash("Selecciona un tipo de convenio y una boca de cobranza válidos.", "danger")
        return redirect(url_for("registros.nuevo"))

    with SessionLocal() as db:
        base = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cliente_unico).first()
        if not base:
            flash("Cliente no existe en la base del día", "danger")
            return redirect(url_for("registros.nuevo"))

        # archivos
        try:
            archivo_convenio = _save_upload(files.get("archivo_convenio"))
            archivo_pago = _save_upload(files.get("archivo_pago"))
            archivo_gestion = _save_upload(files.get("archivo_gestion"))
        except Exception as exc:
            flash(f"Error en archivos: {exc}", "danger")
            return redirect(url_for("registros.nuevo"))

        registro = Registro(
            cliente_unico=cliente_unico,
            tipo_convenio_id=tipo_convenio_id_int,
            boca_cobranza_id=boca_cobranza_id_int,
            fecha_promesa=fecha_promesa or date.today(),
            telefono=telefono or None,
            semana=int(semana_raw) if semana_raw else None,
            pago_inicial=pago_inicial,
            pago_semanal=pago_semanal,
            duracion_semanas=duracion_semanas,
            notas=notas or None,
            creado_por=user_id,
            archivo_convenio=archivo_convenio,
            archivo_pago=archivo_pago,
            archivo_gestion=archivo_gestion,
        )
        _aplicar_snapshot(registro, base)

        db.add(registro)
        db.commit()

    flash("Registro creado", "success")
    return redirect(url_for("registros.listado"))


@registros_bp.post("/<int:registro_id>/actualizar")
def actualizar(registro_id: int):
    if not require_agent():
        return redirect(url_for("auth.login"))

    user_id = session.get("user_id")
    role = session.get("role")

    form = request.form
    files = request.files

    cliente_unico = (form.get("cliente_unico") or "").strip()
    tipo_convenio_id = form.get("tipo_convenio_id")
    boca_cobranza_id = form.get("boca_cobranza_id")
    fecha_promesa_raw = form.get("fecha_promesa")
    telefono = (form.get("telefono") or "").strip()
    semana_raw = form.get("semana")
    notas = (form.get("notas") or "").strip()
    pago_inicial_raw = (form.get("pago_inicial") or "").strip()
    pago_semanal_raw = (form.get("pago_semanal") or "").strip()
    duracion_raw = (form.get("duracion_semanas") or "").strip()

    try:
        pago_inicial = _parse_currency(pago_inicial_raw)
        pago_semanal = _parse_currency(pago_semanal_raw)
        duracion_semanas = _parse_duration(duracion_raw)
        fecha_promesa = _parse_fecha(fecha_promesa_raw)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("registros.editar", registro_id=registro_id))

    if not cliente_unico:
        flash("Cliente único es obligatorio", "warning")
        return redirect(url_for("registros.editar", registro_id=registro_id))

    try:
        tipo_convenio_id_int = int(tipo_convenio_id)
        boca_cobranza_id_int = int(boca_cobranza_id)
    except (TypeError, ValueError):
        flash("Selecciona un tipo de convenio y una boca de cobranza válidos.", "danger")
        return redirect(url_for("registros.editar", registro_id=registro_id))

    with SessionLocal() as db:
        registro = db.query(Registro).filter(Registro.id == registro_id).first()
        if not registro:
            abort(404)
        if role == "agente" and registro.creado_por != user_id:
            abort(403)

        base = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cliente_unico).first()
        if not base:
            flash("Cliente no existe en la base del día", "danger")
            return redirect(url_for("registros.editar", registro_id=registro_id))

        # archivos nuevos
        try:
            nuevo_convenio = _save_upload(files.get("archivo_convenio"))
            nuevo_pago = _save_upload(files.get("archivo_pago"))
            nueva_gestion = _save_upload(files.get("archivo_gestion"))
        except Exception as exc:
            flash(f"Error en archivos: {exc}", "danger")
            return redirect(url_for("registros.editar", registro_id=registro_id))

        # flags de borrado
        if form.get("eliminar_archivo_convenio") == "1":
            _delete_file(registro.archivo_convenio)
            registro.archivo_convenio = None
        if form.get("eliminar_archivo_pago") == "1":
            _delete_file(registro.archivo_pago)
            registro.archivo_pago = None
        if form.get("eliminar_archivo_gestion") == "1":
            _delete_file(registro.archivo_gestion)
            registro.archivo_gestion = None

        # aplicar nuevos archivos
        if nuevo_convenio:
            _delete_file(registro.archivo_convenio)
            registro.archivo_convenio = nuevo_convenio
        if nuevo_pago:
            _delete_file(registro.archivo_pago)
            registro.archivo_pago = nuevo_pago
        if nueva_gestion:
            _delete_file(registro.archivo_gestion)
            registro.archivo_gestion = nueva_gestion

        # campos
        registro.cliente_unico = cliente_unico
        registro.tipo_convenio_id = tipo_convenio_id_int
        registro.boca_cobranza_id = boca_cobranza_id_int
        registro.fecha_promesa = fecha_promesa or registro.fecha_promesa
        registro.telefono = telefono or None
        registro.semana = int(semana_raw) if semana_raw else None
        registro.pago_inicial = pago_inicial
        registro.pago_semanal = pago_semanal
        registro.duracion_semanas = duracion_semanas
        registro.notas = notas or None
        _aplicar_snapshot(registro, base)

        db.commit()

    flash("Registro actualizado", "success")
    return redirect(url_for("registros.listado"))


# ----------------- Servir archivo (protegido) -----------------
@registros_bp.get("/file/<string:fname>")
def get_file(fname: str):
    """Sirve un archivo desde UPLOAD_FOLDER; requiere sesión activa."""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    if "/" in fname or "\\" in fname:
        abort(400)

    base = current_app.config["UPLOAD_FOLDER"]
    full = os.path.join(base, fname)
    if not os.path.isfile(full):
        abort(404)
    return send_from_directory(base, fname, as_attachment=False)


# ----------------- Resumen por semana (agente) -----------------
@registros_bp.get("/resumen")
def resumen():
    if not require_agent():
        return redirect(url_for("auth.login"))

    semana = request.args.get("semana", type=int)
    user_id = session.get("user_id")

    with SessionLocal() as db:
        q = (
            db.query(Registro)
            .options(
                selectinload(Registro.tipo_convenio),
                selectinload(Registro.boca_cobranza),
            )
            .filter(Registro.creado_por == user_id)
        )
        if semana:
            q = q.filter(Registro.semana == semana)
        registros = q.order_by(Registro.id.desc()).all()

    total = len(registros)
    total_pagos_inicial = Decimal("0")
    total_pagos_semanal = Decimal("0")
    por_tipo: dict[str, int] = {}
    por_boca: dict[str, int] = {}

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
        role=session.get("role"),
        user_id=user_id,
    )
