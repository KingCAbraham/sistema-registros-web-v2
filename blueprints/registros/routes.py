"""Rutas del blueprint de registros."""

from __future__ import annotations

import os
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from markupsafe import Markup, escape
from sqlalchemy.orm import selectinload

from markupsafe import Markup, escape

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
# Helpers de autenticación y autorización
# ---------------------------------------------------------------------------

def require_agent() -> bool:
    """Valida que el usuario tenga un rol con acceso al módulo."""
    role = session.get("role")
    if role not in {"agente", "admin", "supervisor", "gerente"}:
        flash("Inicia sesión.", "warning")
        return False
    return True


# ---------------------------------------------------------------------------
# Helpers de archivos y parsing
# ---------------------------------------------------------------------------

def _allowed(filename: str) -> bool:
    """Verifica extensión permitida contra Config.ALLOWED_EXTENSIONS."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config.get("ALLOWED_EXTENSIONS", set())


def _save_upload(file_storage):
    """Guarda el archivo con nombre seguro y devuelve el nombre generado."""
    if not file_storage or file_storage.filename == "":
        return None

    if not _allowed(file_storage.filename):
        raise ValueError("Extensión no permitida (usa pdf, png, jpg, jpeg).")

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)

    safe_name = secure_filename(file_storage.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_storage.save(os.path.join(upload_folder, unique_name))
    return unique_name


def _delete_file(filename: str | None) -> None:
    if not filename:
        return
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(upload_folder, filename)
    try:
        os.remove(path)
    except OSError:
        pass


def _parse_currency(raw: str) -> Decimal | None:
    if not raw:
        return None

    cleaned = (
        raw.replace("MXN", "")
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
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Formato de moneda inválido") from exc

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _parse_duration(raw: str) -> int | None:
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

def _delete_file(fname: str | None):
    if not fname:
        return
    base = current_app.config["UPLOAD_FOLDER"]
    path = os.path.join(base, fname)
    try:
        os.remove(path)
    except OSError:
        pass


def _parse_currency(value: str) -> Decimal | None:
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


def _parse_duration(raw: str) -> int | None:
    if not raw:
        return None
    try:
        duracion_val = int(raw)
    except ValueError as exc:
        raise ValueError("Duración en semanas inválida") from exc
    if duracion_val < 1:
        raise ValueError("La duración debe ser al menos de una semana")
    return duracion_val


def _format_currency(value):
    if value is None:
        return ""
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return ""
    return f"${number:,.2f}"


def _build_select_options(items, selected_id, placeholder="Selecciona una opción"):
    placeholder_selected = selected_id in (None, "")
    selected = " selected" if placeholder_selected else ""
    options = [
        f'<option value="" disabled{selected}>{escape(placeholder)}</option>'
    ]
    for item in items:
        opt_selected = " selected" if selected_id == getattr(item, "id", None) else ""
        label = escape(getattr(item, "nombre", ""))
        value = escape(str(getattr(item, "id", "")))
        options.append(f'<option value="{value}"{opt_selected}>{label}</option>')
    return Markup("\n".join(options))


# ----------------- Listado -----------------
@registros_bp.get("/")
def listado():
    if not require_agent():
        return redirect(url_for("auth.login"))

    user_id = session.get("user_id")
    role = session.get("role")

    with SessionLocal() as db:
        query = (
            db.query(Registro)
            .options(
                selectinload(Registro.tipo_convenio),
                selectinload(Registro.boca_cobranza),
            )
        )
        if role == "agente":
            query = query.filter(Registro.creado_por == user_id)
        registros = query.order_by(Registro.id.desc()).limit(100).all()

    return render_template(
        "registros_listado.html",
        registros=registros,
        role=role,
        user_id=user_id,
    )


        if session.get("role") == "agente":
            q = q.filter(Registro.creado_por == user_id)
        regs = q.order_by(Registro.id.desc()).limit(100).all()
    return render_template(
        "registros_listado.html",
        registros=regs,
        role=role,
        user_id=user_id,
    )
# ----------------- Nuevo registro (form) -----------------
@registros_bp.get("/nuevo")
def nuevo():
    if not require_agent():
        return redirect(url_for("auth.login"))

    with SessionLocal() as db:
        tipos, bocas = _load_catalogos(db)

    return render_template(
        "registros_nuevo.html",
        tipo_options=_build_select_options(tipos, None),
        boca_options=_build_select_options(bocas, None),
        registro=None,
        is_edit=False,
        format_currency=_format_currency,
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
    tipo_options = _build_select_options(tipos, None)
    boca_options = _build_select_options(bocas, None)
    return render_template(
        "registros_nuevo.html",
        tipo_options=tipo_options,
        boca_options=boca_options,
        registro=None,
        is_edit=False,
        format_currency=_format_currency,
    return render_template(
        "registros_nuevo.html",
        tipos=tipos,
        bocas=bocas,
        registro=None,
        is_edit=False,
    )


@registros_bp.get("/<int:registro_id>/editar")
def editar(registro_id: int):
    if not require_agent():
        return redirect(url_for("auth.login"))

    user_id = session.get("user_id")
    role = session.get("role")

    with SessionLocal() as db:
        registro = db.query(Registro).filter(Registro.id == registro_id).first()
        if not registro:
            abort(404)
        if role == "agente" and registro.creado_por != user_id:
            abort(403)

        tipos, bocas = _load_catalogos(db)
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

    return render_template(
        "registros_nuevo.html",
        tipo_options=_build_select_options(tipos, registro.tipo_convenio_id),
        boca_options=_build_select_options(bocas, registro.boca_cobranza_id),
        registro=registro,
        is_edit=True,
        format_currency=_format_currency,
        tipos=tipos,
        bocas=bocas,
        registro=registro,
        is_edit=True,
    )


@registros_bp.get("/api/search_cliente")
def api_search_cliente():
    """Autocomplete basado en prefijo de cliente único."""
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
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("registros.nuevo"))
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

    if not tipo_convenio_id or not boca_cobranza_id:
        flash("Selecciona un tipo de convenio y una boca de cobranza.", "danger")
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

        try:
            archivo_convenio = _save_upload(files.get("archivo_convenio"))
            archivo_pago = _save_upload(files.get("archivo_pago"))
            archivo_gestion = _save_upload(files.get("archivo_gestion"))
        except Exception as exc:  # noqa: BLE001 - mostramos mensaje amigable
            flash(f"Error en archivos: {exc}", "danger")
            return redirect(url_for("registros.nuevo"))

        registro = Registro(
            cliente_unico=cliente_unico,
            tipo_convenio_id=tipo_convenio_id_int,
            boca_cobranza_id=boca_cobranza_id_int,
            fecha_promesa=fecha_promesa or date.today(),
            telefono=telefono or None,
            semana=int(semana_raw) if semana_raw else None,
            nombre_cte_snap=base.nombre_cte,
            gerencia_snap=base.gerencia,
            producto_snap=base.producto,
            fidiapago_snap=base.fidiapago,
            gestion_desc_snap=base.gestion_desc,
            tipo_convenio_id=tipo_convenio_id_int,
            boca_cobranza_id=boca_cobranza_id_int,
            fecha_promesa=date.fromisoformat(fecha_promesa) if fecha_promesa else date.today(),
            telefono=telefono or None,
            semana=int(semana) if semana else None,
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
    fecha_promesa = form.get("fecha_promesa")
    telefono = (form.get("telefono") or "").strip()
    semana = form.get("semana")
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

    if not tipo_convenio_id or not boca_cobranza_id:
        flash("Selecciona un tipo de convenio y una boca de cobranza.", "danger")
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

        try:
            nuevo_convenio = _save_upload(files.get("archivo_convenio"))
            nuevo_pago = _save_upload(files.get("archivo_pago"))
            nueva_gestion = _save_upload(files.get("archivo_gestion"))
        except Exception as exc:  # noqa: BLE001
            flash(f"Error en archivos: {exc}", "danger")
        except Exception as e:
            flash(f"Error en archivos: {e}", "danger")
            return redirect(url_for("registros.editar", registro_id=registro_id))

        if form.get("eliminar_archivo_convenio") == "1":
            _delete_file(registro.archivo_convenio)
            registro.archivo_convenio = None
        if form.get("eliminar_archivo_pago") == "1":
            _delete_file(registro.archivo_pago)
            registro.archivo_pago = None
        if form.get("eliminar_archivo_gestion") == "1":
            _delete_file(registro.archivo_gestion)
            registro.archivo_gestion = None

        if nuevo_convenio:
            _delete_file(registro.archivo_convenio)
            registro.archivo_convenio = nuevo_convenio
        if nuevo_pago:
            _delete_file(registro.archivo_pago)
            registro.archivo_pago = nuevo_pago
        if nueva_gestion:
            _delete_file(registro.archivo_gestion)
            registro.archivo_gestion = nueva_gestion

        registro.cliente_unico = cliente_unico
        registro.tipo_convenio_id = tipo_convenio_id_int
        registro.boca_cobranza_id = boca_cobranza_id_int
        registro.fecha_promesa = fecha_promesa or registro.fecha_promesa
        registro.telefono = telefono or None
        registro.semana = int(semana_raw) if semana_raw else None
        try:
            tipo_convenio_id_int = int(tipo_convenio_id)
            boca_cobranza_id_int = int(boca_cobranza_id)
        except (TypeError, ValueError):
            flash("Selecciona un tipo de convenio y una boca de cobranza válidos.", "danger")
            return redirect(url_for("registros.editar", registro_id=registro_id))

        registro.cliente_unico = cliente_unico
        registro.nombre_cte_snap = base.nombre_cte
        registro.gerencia_snap = base.gerencia
        registro.producto_snap = base.producto
        registro.fidiapago_snap = base.fidiapago
        registro.gestion_desc_snap = base.gestion_desc
        registro.tipo_convenio_id = tipo_convenio_id_int
        registro.boca_cobranza_id = boca_cobranza_id_int
        registro.fecha_promesa = (
            date.fromisoformat(fecha_promesa)
            if fecha_promesa
            else registro.fecha_promesa
        )
        registro.telefono = telefono or None
        registro.semana = int(semana) if semana else None
        registro.pago_inicial = pago_inicial
        registro.pago_semanal = pago_semanal
        registro.duracion_semanas = duracion_semanas
        registro.notas = notas or None
        _aplicar_snapshot(registro, base)

        db.commit()

    flash("Registro actualizado", "success")
    return redirect(url_for("registros.listado"))


@registros_bp.get("/file/<string:filename>")
def get_file(filename: str):
    """Sirve un archivo desde UPLOAD_FOLDER; requiere sesión activa."""
# ----------------- Servir archivo (protegido) -----------------
@registros_bp.get("/file/<string:fname>")
def get_file(fname):
    """Sirve un archivo desde UPLOAD_FOLDER; requiere sesión."""
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    if "/" in filename or "\\" in filename:
        abort(400)

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    full_path = os.path.join(upload_folder, filename)
    if not os.path.isfile(full_path):
        abort(404)
    return send_from_directory(upload_folder, filename, as_attachment=False)


@registros_bp.get("/resumen")
def resumen():
    if not require_agent():
        return redirect(url_for("auth.login"))

    semana = request.args.get("semana", type=int)
    user_id = session.get("user_id")

    with SessionLocal() as db:
        query = db.query(Registro).filter(Registro.creado_por == user_id)
        if semana:
            query = query.filter(Registro.semana == semana)
        registros = query.order_by(Registro.id.desc()).all()

    total = len(registros)
    total_pagos_inicial = Decimal("0")
    total_pagos_semanal = Decimal("0")
    por_tipo: dict[str, int] = {}
    por_boca: dict[str, int] = {}

    for registro in registros:
        tipo = registro.tipo_convenio.nombre if registro.tipo_convenio else "(s/tipo)"
        boca = registro.boca_cobranza.nombre if registro.boca_cobranza else "(s/boca)"
        por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
        por_boca[boca] = por_boca.get(boca, 0) + 1
        if registro.pago_inicial:
            total_pagos_inicial += registro.pago_inicial
        if registro.pago_semanal:
            total_pagos_semanal += registro.pago_semanal
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
        role=session.get("role"),
        user_id=user_id,
    )
