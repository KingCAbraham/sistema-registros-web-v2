from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import Integer, String, Date, DateTime, Text, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base

# --- Usuarios ---
class Usuario(Base):
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="agente")
    activo: Mapped[int] = mapped_column(Integer, default=1)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# --- Catálogos ---
class TipoConvenio(Base):
    __tablename__ = "tipo_convenio"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    activo: Mapped[int] = mapped_column(Integer, default=1)

class BocaCobranza(Base):
    __tablename__ = "bocas_cobranza"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    activo: Mapped[int] = mapped_column(Integer, default=1)

# --- Base General ---
class BaseGeneral(Base):
    __tablename__ = "base_general"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_unico: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    nombre_cte: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gerencia: Mapped[str | None] = mapped_column(String(255), nullable=True)
    producto: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fidiapago: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gestion_desc: Mapped[str | None] = mapped_column(Text, nullable=True)

# --- Registros ---
class Registro(Base):
    __tablename__ = "registros"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_unico: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # snapshot (opcionales)
    nombre_cte_snap: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gerencia_snap: Mapped[str | None]   = mapped_column(String(255), nullable=True)
    producto_snap: Mapped[str | None]   = mapped_column(String(255), nullable=True)
    fidiapago_snap: Mapped[str | None]  = mapped_column(String(255), nullable=True)
    gestion_desc_snap: Mapped[str | None] = mapped_column(Text, nullable=True)

    tipo_convenio_id: Mapped[int] = mapped_column(Integer, ForeignKey("tipo_convenio.id"), nullable=False)
    boca_cobranza_id: Mapped[int] = mapped_column(Integer, ForeignKey("bocas_cobranza.id"), nullable=False)

    # OJO: es date, no datetime
    fecha_promesa: Mapped[date] = mapped_column(Date, nullable=False)

    telefono: Mapped[str | None] = mapped_column(String(30), nullable=True)
    semana:   Mapped[int | None] = mapped_column(Integer, nullable=True)
    pago_inicial: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    pago_semanal: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    duracion_semanas: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notas:    Mapped[str | None] = mapped_column(Text, nullable=True)

    # evidencias (opcionales)
    archivo_convenio: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archivo_pago:     Mapped[str | None] = mapped_column(String(255), nullable=True)
    archivo_gestion:  Mapped[str | None] = mapped_column(String(255), nullable=True)

    creado_por: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    creado_en:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # relaciones con eager loading por defecto
    tipo_convenio: Mapped["TipoConvenio"] = relationship("TipoConvenio", lazy="selectin")
    boca_cobranza: Mapped["BocaCobranza"] = relationship("BocaCobranza", lazy="selectin")

    # opcional: saber quién creó
    creador: Mapped["Usuario"] = relationship("Usuario", lazy="selectin")
