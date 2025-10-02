from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Date, ForeignKey, Numeric
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import relationship
from db import Base

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="agente")  # admin, gerente, supervisor, agente
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, server_default=func.now())

class BaseGeneral(Base):
    __tablename__ = "base_general"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    cliente_unico = Column(String(100), index=True, nullable=False)
    nombre_cte = Column(String(255))
    gerencia = Column(String(255))
    producto = Column(String(255))
    fidiapago = Column(String(255))
    gestion_desc = Column(Text)
    cargado_en = Column(DateTime, server_default=func.now())
    # … (puedes ampliar con todas las columnas que nos pasaste)

class TipoConvenio(Base):
    __tablename__ = "tipo_convenio"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), unique=True, nullable=False)
    activo = Column(Boolean, default=True)

class BocaCobranza(Base):
    __tablename__ = "bocas_cobranza"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), unique=True, nullable=False)
    activo = Column(Boolean, default=True)

class Registro(Base):
    __tablename__ = "registros"
    id = Column(BIGINT(unsigned=True), primary_key=True, autoincrement=True)
    cliente_unico = Column(String(100), index=True, nullable=False)
    nombre_cte_snap = Column(String(255))
    gerencia_snap = Column(String(255))
    producto_snap = Column(String(255))
    fidiapago_snap = Column(String(255))
    gestion_desc_snap = Column(Text)

    tipo_convenio_id = Column(Integer, ForeignKey("tipo_convenio.id"), nullable=False)
    boca_cobranza_id = Column(Integer, ForeignKey("bocas_cobranza.id"), nullable=False)

    fecha_promesa = Column(Date, nullable=False)
    telefono = Column(String(30))
    semana = Column(Integer)  # 1-53
    notas = Column(Text)

    archivo_convenio = Column(String(255))
    archivo_pago = Column(String(255))
    archivo_gestion = Column(String(255))

    creado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    creado_en = Column(DateTime, server_default=func.now())

    tipo_convenio = relationship("TipoConvenio")
    boca_cobranza = relationship("BocaCobranza")
