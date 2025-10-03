# blueprints/registros/routes.py
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy import func
from db import SessionLocal
from models import Registro, BaseGeneral, TipoConvenio, BocaCobranza

from . import registros_bp


def require_agent():
    role = session.get("role")
    if role not in ("agente", "admin", "supervisor", "gerente"):
        flash("Inicia sesión.", "warning")
        return False
    return True


@registros_bp.get("/")
def listado():
    if not require_agent():
        return redirect(url_for("auth.login"))
    user_id = session.get("user_id")
    with SessionLocal() as db:
        q = db.query(Registro)
        if session.get("role") == "agente":
            q = q.filter(Registro.creado_por == user_id)
        regs = q.order_by(Registro.id.desc()).limit(100).all()
    return render_template("registros_listado.html", registros=regs)


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


# ==== NUEVO: API para AUTOCOMPLETE (sugerencias) ====
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
    # [{cliente_unico:..., nombre_cte:...}, ...]
    return jsonify([{"cliente_unico": r[0], "nombre_cte": r[1] or ""} for r in rows])


# ==== NUEVO: API para AUTOLLENAR por cliente_unico exacto ====
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


# (opcional: dejamos la versión POST también por compatibilidad)
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


@registros_bp.post("/crear")
def crear():
    if not require_agent():
        return redirect(url_for("auth.login"))

    form = request.form
    user_id = session.get("user_id")

    cliente_unico = (form.get("cliente_unico") or "").strip()
    tipo_convenio_id = form.get("tipo_convenio_id")
    boca_cobranza_id = form.get("boca_cobranza_id")
    fecha_promesa = form.get("fecha_promesa")
    telefono = (form.get("telefono") or "").strip()
    semana = form.get("semana")
    notas = (form.get("notas") or "").strip()

    if not cliente_unico:
        flash("Cliente único es obligatorio", "warning")
        return redirect(url_for("registros.nuevo"))

    with SessionLocal() as db:
        base = db.query(BaseGeneral).filter(BaseGeneral.cliente_unico == cliente_unico).first()
        if not base:
            flash("Cliente no existe en la base del día", "danger")
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
            notas=notas or None,
            creado_por=user_id,
        )
        db.add(reg)
        db.commit()

    flash("Registro creado", "success")
    return redirect(url_for("registros.listado"))
