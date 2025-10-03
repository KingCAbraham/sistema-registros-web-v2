from datetime import datetime
from sqlalchemy import Integer, String, Date, DateTime, Text, ForeignKey
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

# --- Base General (diaria) ---
class BaseGeneral(Base):
    __tablename__ = "base_general"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_unico: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    nombre_cte: Mapped[str] = mapped_column(String(255))
    gerencia: Mapped[str] = mapped_column(String(255))
    producto: Mapped[str] = mapped_column(String(255))
    fidiapago: Mapped[str] = mapped_column(String(255))
    gestion_desc: Mapped[str] = mapped_column(Text)

# --- Registros (del agente) ---
class Registro(Base):
    __tablename__ = "registros"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cliente_unico: Mapped[str] = mapped_column(String(100), index=True, nullable=False)

    # snapshot
    nombre_cte_snap: Mapped[str] = mapped_column(String(255))
    gerencia_snap: Mapped[str] = mapped_column(String(255))
    producto_snap: Mapped[str] = mapped_column(String(255))
    fidiapago_snap: Mapped[str] = mapped_column(String(255))
    gestion_desc_snap: Mapped[str] = mapped_column(Text)

    tipo_convenio_id: Mapped[int] = mapped_column(Integer, ForeignKey("tipo_convenio.id"), nullable=False)
    boca_cobranza_id: Mapped[int] = mapped_column(Integer, ForeignKey("bocas_cobranza.id"), nullable=False)

    fecha_promesa: Mapped[datetime] = mapped_column(Date)
    telefono: Mapped[str] = mapped_column(String(30))
    semana: Mapped[int] = mapped_column(Integer)
    notas: Mapped[str] = mapped_column(Text)

    archivo_convenio: Mapped[str] = mapped_column(String(255))
    archivo_pago: Mapped[str] = mapped_column(String(255))
    archivo_gestion: Mapped[str] = mapped_column(String(255))

    creado_por: Mapped[int] = mapped_column(Integer, ForeignKey("usuarios.id"), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    tipo_convenio: Mapped["TipoConvenio"] = relationship("TipoConvenio")
    boca_cobranza: Mapped["BocaCobranza"] = relationship("BocaCobranza")
