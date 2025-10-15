# blueprints/admin/routes.py
import io
import csv
import os
import time

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session as _session,
    send_file,
    current_app,
)
from werkzeug.security import generate_password_hash

from sqlalchemy import text

from db import SessionLocal, engine
from models import BaseGeneral, TipoConvenio, BocaCobranza, Usuario, Registro

# Usa el blueprint ya creado en __init__.py
from . import admin_bp


def require_admin():
    if _session.get("role") != "admin":
        flash("Acceso restringido a administradores.", "danger")
        return False
    return True


# --- EXPORTAR REGISTROS POR SEMANA (CSV) ---
@admin_bp.get("/export/semana")
def export_semana():
    if _session.get("role") != "admin":
        flash("Acceso restringido a administradores.", "danger")
        return redirect(url_for("auth.login"))

    semana_str = (request.args.get("semana") or "").strip()
    try:
        semana = int(semana_str)
        if not (1 <= semana <= 53):
            raise ValueError()
    except Exception:
        flash("Parámetro 'semana' inválido.", "warning")
        return redirect(url_for("admin.index"))

    with SessionLocal() as db:
        rows = (
            db.query(
                Registro.id,
                Registro.cliente_unico,
                Registro.nombre_cte_snap,
                Registro.gerencia_snap,
                Registro.producto_snap,
                Registro.fidiapago_snap,
                Registro.gestion_desc_snap,
                Registro.fecha_promesa,
                Registro.telefono,
                Registro.semana,
                Registro.pago_inicial,
                Registro.pago_semanal,
                Registro.duracion_semanas,
                Registro.notas,
                Usuario.username.label("creado_por_username"),
                Registro.creado_en,
                TipoConvenio.nombre.label("tipo_convenio_nombre"),
                BocaCobranza.nombre.label("boca_cobranza_nombre"),
            )
            .outerjoin(Usuario, Usuario.id == Registro.creado_por)
            .outerjoin(TipoConvenio, TipoConvenio.id == Registro.tipo_convenio_id)
            .outerjoin(BocaCobranza, BocaCobranza.id == Registro.boca_cobranza_id)
            .filter(Registro.semana == semana)
            .order_by(Registro.id.asc())
            .all()
        )

    # CSV en memoria (BOM + UTF-8 para Excel)
    sio = io.StringIO(newline="")
    w = csv.writer(sio, lineterminator="\n")
    w.writerow(
        [
            "ID",
            "CLIENTE_UNICO",
            "NOMBRE_SNAP",
            "GERENCIA_SNAP",
            "PRODUCTO_SNAP",
            "FIDIAPAGO_SNAP",
            "GESTION_DESC_SNAP",
            "FECHA_PROMESA",
            "TELEFONO",
            "SEMANA",
            "PAGO_INICIAL",
            "PAGO_SEMANAL",
            "DURACION_SEMANAS",
            "NOTAS",
            "CREADO_POR",
            "CREADO_EN",
            "TIPO_CONVENIO",
            "BOCA_COBRANZA",
        ]
    )
    for r in rows:
        w.writerow(
            [
                r.id or "",
                r.cliente_unico or "",
                r.nombre_cte_snap or "",
                r.gerencia_snap or "",
                r.producto_snap or "",
                r.fidiapago_snap or "",
                (r.gestion_desc_snap or "").replace("\r", " ").replace("\n", " "),
                r.fecha_promesa or "",
                r.telefono or "",
                r.semana or "",
                r.pago_inicial or "",
                r.pago_semanal or "",
                r.duracion_semanas or "",
                (r.notas or "").replace("\r", " ").replace("\n", " "),
                r.creado_por_username or "",
                r.creado_en or "",
                r.tipo_convenio_nombre or "",
                r.boca_cobranza_nombre or "",
            ]
        )

    csv_bytes = ("\ufeff" + sio.getvalue()).encode("utf-8")
    filename = f"registros_semana_{semana}.csv"
    return send_file(
        io.BytesIO(csv_bytes),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


# (opcional) portada del admin
@admin_bp.get("/")
def index():
    if not require_admin():
        return redirect(url_for("auth.login"))
    return render_template("admin_index.html")


# --------- Base General ----------
@admin_bp.get("/base_general")
def base_general():
    if not require_admin():
        return redirect(url_for("auth.login"))
    return render_template("admin_base_general.html")


# --------- Carga CSV → staging → UPSERT a destino (sin CTE ni CTAS, compatible TiDB) ----------
@admin_bp.post("/base_general")
def base_general_upload():
    """
    Carga SOLO CSV. Inserta nuevos y actualiza existentes por UNIQUE(cliente_unico).
    Requisitos previos (una sola vez en la BD):
      - base_general: SOLO un índice UNIQUE(cliente_unico)
      - base_general_tmp: SIN índices UNIQUE
    """
    if not require_admin():
        return redirect(url_for("auth.login"))

    f = request.files.get("archivo")
    mode = (request.form.get("mode") or "upsert").lower()  # "upsert" | "insert"

    if not f or f.filename == "":
        flash("Selecciona un archivo .csv", "warning")
        return redirect(url_for("admin.base_general"))
    if not f.filename.lower().endswith(".csv"):
        flash("Solo se admite CSV (más rápido que XLSX).", "warning")
        return redirect(url_for("admin.base_general"))

    # Guarda temporalmente para usar LOAD DATA LOCAL INFILE
    t0 = time.time()
    tmp_dir = os.path.join(current_app.instance_path, "uploads")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, f"bg_{int(t0)}.csv")
    f.save(tmp_path)

    try:
        with engine.begin() as conn:
            # 1) Limpia staging
            conn.execute(text("TRUNCATE TABLE sistema_registros.base_general_tmp"))

            # 2) Carga rápida a staging
            #    Si tu CSV usa solo '\n', cambia LINES TERMINATED BY '\n'
            conn.exec_driver_sql(
                """
                LOAD DATA LOCAL INFILE %s
                INTO TABLE sistema_registros.base_general_tmp
                CHARACTER SET utf8mb4
                FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
                LINES  TERMINATED BY '\r\n'
                IGNORE 1 LINES
                (@cliente_unico,@nombre_cte,@gerencia,@producto,@fidiapago,@gestion_desc)
                SET
                  cliente_unico = TRIM(@cliente_unico),
                  nombre_cte    = NULLIF(TRIM(@nombre_cte),''),
                  gerencia      = NULLIF(TRIM(@gerencia),''),
                  producto      = NULLIF(TRIM(@producto),''),
                  fidiapago     = NULLIF(TRIM(@fidiapago),''),
                  gestion_desc  = NULLIF(TRIM(@gestion_desc),''),
                  actualizado_en = NOW();
                """,
                (tmp_path,),
            )

            total_tmp = conn.execute(
                text("SELECT COUNT(*) FROM sistema_registros.base_general_tmp")
            ).scalar_one()

            # 3) Subconsulta "dedup": última fila por UPPER(TRIM(cliente_unico))
            dedup_subq = """
              SELECT *
              FROM (
                SELECT s.*,
                       ROW_NUMBER() OVER (
                         PARTITION BY UPPER(TRIM(cliente_unico))
                         ORDER BY id DESC
                       ) AS rn
                FROM sistema_registros.base_general_tmp s
              ) d
              WHERE d.rn = 1
            """

            # Conteo deduplicado
            dedup = conn.execute(
                text(f"SELECT COUNT(*) FROM ({dedup_subq}) AS dd")
            ).scalar_one()

            # Conteo de NUEVOS (dedup LEFT JOIN destino)
            nuevos = conn.execute(
                text(f"""
                  SELECT COUNT(*)
                  FROM ({dedup_subq}) AS d
                  LEFT JOIN sistema_registros.base_general t
                    ON UPPER(TRIM(t.cliente_unico)) = UPPER(TRIM(d.cliente_unico))
                  WHERE t.cliente_unico IS NULL
                """)
            ).scalar_one()

            # 4) Inserta/Actualiza destino (normalizando cliente_unico al entrar)
            if mode == "insert":
                res = conn.execute(
                    text(f"""
                      INSERT INTO sistema_registros.base_general
                        (cliente_unico, nombre_cte, gerencia, producto, fidiapago, gestion_desc)
                      SELECT UPPER(TRIM(d.cliente_unico)) AS cliente_unico,
                             d.nombre_cte, d.gerencia, d.producto, d.fidiapago, d.gestion_desc
                      FROM ({dedup_subq}) AS d
                      LEFT JOIN sistema_registros.base_general t
                        ON UPPER(TRIM(t.cliente_unico)) = UPPER(TRIM(d.cliente_unico))
                      WHERE t.cliente_unico IS NULL
                    """)
                )
                insertados = res.rowcount or int(nuevos)
                actualizados = 0
            else:  # upsert
                res = conn.execute(
                    text(f"""
                      INSERT INTO sistema_registros.base_general
                        (cliente_unico, nombre_cte, gerencia, producto, fidiapago, gestion_desc)
                      SELECT UPPER(TRIM(d.cliente_unico)) AS cliente_unico,
                             d.nombre_cte, d.gerencia, d.producto, d.fidiapago, d.gestion_desc
                      FROM ({dedup_subq}) AS d
                      ON DUPLICATE KEY UPDATE
                        nombre_cte = VALUES(nombre_cte),
                        gerencia   = VALUES(gerencia),
                        producto   = VALUES(producto),
                        fidiapago  = VALUES(fidiapago),
                        gestion_desc = VALUES(gestion_desc),
                        actualizado_en = NOW()
                    """)
                )
                insertados = int(nuevos)
                actualizados = max(0, int(dedup) - insertados)

        dt = time.time() - t0
        flash(
            f"CSV cargado: {total_tmp} filas (dedup únicas: {dedup}). "
            f"Nuevos insertados: {insertados} | Actualizados: {actualizados}. "
            f"Tiempo: {dt:.1f}s",
            "success",
        )
    except Exception as e:
        flash(f"Error al procesar CSV: {e}", "danger")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

    return redirect(url_for("admin.base_general"))


# ---------- Catálogo: TipoConvenio ----------
@admin_bp.get("/catalogo/tipos")
def catalogo_tipos():
    if not require_admin():
        return redirect(url_for("auth.login"))
    with SessionLocal() as db:
        tipos = db.query(TipoConvenio).order_by(TipoConvenio.nombre.asc()).all()
    return render_template("admin_catalogo_tipos.html", tipos=tipos)


@admin_bp.post("/catalogo/tipos")
def catalogo_tipos_save():
    if not require_admin():
        return redirect(url_for("auth.login"))
    nombre = request.form.get("nombre", "").strip()
    activo = 1 if request.form.get("activo") == "on" else 0
    if not nombre:
        flash("Nombre requerido", "warning")
        return redirect(url_for("admin.catalogo_tipos"))

    with SessionLocal() as db:
        item = db.query(TipoConvenio).filter(TipoConvenio.nombre == nombre).first()
        if item:
            item.activo = activo
        else:
            db.add(TipoConvenio(nombre=nombre, activo=activo))
        db.commit()
    flash("Guardado", "success")
    return redirect(url_for("admin.catalogo_tipos"))


# ---------- Catálogo: BocaCobranza ----------
@admin_bp.get("/catalogo/bocas")
def catalogo_bocas():
    if not require_admin():
        return redirect(url_for("auth.login"))
    with SessionLocal() as db:
        bocas = db.query(BocaCobranza).order_by(BocaCobranza.nombre.asc()).all()
    return render_template("admin_catalogo_bocas.html", bocas=bocas)


@admin_bp.post("/catalogo/bocas")
def catalogo_bocas_save():
    if not require_admin():
        return redirect(url_for("auth.login"))
    nombre = request.form.get("nombre", "").strip()
    activo = 1 if request.form.get("activo") == "on" else 0
    if not nombre:
        flash("Nombre requerido", "warning")
        return redirect(url_for("admin.catalogo_bocas"))

    with SessionLocal() as db:
        item = db.query(BocaCobranza).filter(BocaCobranza.nombre == nombre).first()
        if item:
            item.activo = activo
        else:
            db.add(BocaCobranza(nombre=nombre))
        db.commit()
    flash("Guardado", "success")
    return redirect(url_for("admin.catalogo_bocas"))


# ---------- Usuarios ----------
@admin_bp.get("/usuarios")
def usuarios_list():
    if not require_admin():
        return redirect(url_for("auth.login"))
    with SessionLocal() as db:
        users = db.query(Usuario).order_by(Usuario.username.asc()).all()
    return render_template("admin_usuarios.html", usuarios=users)


@admin_bp.post("/usuarios")
def usuarios_create():
    if not require_admin():
        return redirect(url_for("auth.login"))

    username = (request.form.get("username") or "").strip()
    password = (request.form.get("password") or "").strip()
    role = (request.form.get("role") or "agente").strip()
    activo = 1 if request.form.get("activo") == "on" else 0

    if not username or not password:
        flash("Usuario y contraseña son obligatorios.", "warning")
        return redirect(url_for("admin.usuarios_list"))

    with SessionLocal() as db:
        existe = db.query(Usuario).filter(Usuario.username == username).first()
        if existe:
            flash("Ese username ya existe.", "danger")
            return redirect(url_for("admin.usuarios_list"))

        pwd_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=12)
        nuevo = Usuario(username=username, password_hash=pwd_hash, role=role, activo=activo)
        db.add(nuevo)
        db.commit()

    flash("Usuario creado correctamente.", "success")
    return redirect(url_for("admin.usuarios_list"))
