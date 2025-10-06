# blueprints/admin/routes.py
import io
import csv

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session as _session,
    send_file,
)
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from db import SessionLocal
from models import BaseGeneral, TipoConvenio, BocaCobranza, Usuario, Registro
from services.base_general_loader import load_base_general_xlsx

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
    w.writerow([
        "ID", "CLIENTE_UNICO", "NOMBRE_SNAP", "GERENCIA_SNAP", "PRODUCTO_SNAP",
        "FIDIAPAGO_SNAP", "GESTION_DESC_SNAP", "FECHA_PROMESA", "TELEFONO",
        "SEMANA", "PAGO_INICIAL", "PAGO_SEMANAL", "DURACION_SEMANAS", "NOTAS",
        "CREADO_POR", "CREADO_EN",
        "TIPO_CONVENIO", "BOCA_COBRANZA",
    ])
    for r in rows:
        w.writerow([
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
        ])

    csv_bytes = ("\ufeff" + sio.getvalue()).encode("utf-8")
    filename = f"registros_semana_{semana}.csv"
    return send_file(
        io.BytesIO(csv_bytes),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,   # si usas Flask <2.0, cambia a attachment_filename=filename
    )

# (opcional) una portada del admin para el link "Admin"
@admin_bp.get("/")
def index():
    if not require_admin():
        return redirect(url_for("auth.login"))
    return render_template("admin_index.html")  # crea un template simple si quieres

# --------- Base General ----------
@admin_bp.get("/base_general")
def base_general():
    if not require_admin():
        return redirect(url_for("auth.login"))
    return render_template("admin_base_general.html")

@admin_bp.post("/base_general")
def base_general_upload():
    if not require_admin():
        return redirect(url_for("auth.login"))

    file = request.files.get("archivo")
    if not file or file.filename == "":
        flash("Selecciona un archivo .xlsx", "warning")
        return redirect(url_for("admin.base_general"))

    filename = secure_filename(file.filename)
    try:
        data = file.read()
        stats = load_base_general_xlsx(io.BytesIO(data))
        flash(
            f"Base cargada. Insertados: {stats['inserted']} | Actualizados: {stats['updated']} | Omitidos: {stats['skipped']}",
            "success",
        )
    except Exception as e:
        flash(f"Error al procesar: {e}", "danger")

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
            db.add(BocaCobranza(nombre=nombre, activo=activo))
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
