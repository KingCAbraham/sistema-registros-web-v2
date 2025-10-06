-- =====================================================================
-- Esquema limpio y consistente para sistema_registros (TiDB/MySQL)
-- Tipos unificados: TODAS las PK/FK son BIGINT
-- Collation/charset: utf8mb4_bin para comparaciones exactas
-- =====================================================================

-- (Opcional) Si tu usuario no entra ya a la BD por defecto:
-- CREATE DATABASE IF NOT EXISTS sistema_registros
--   DEFAULT CHARACTER SET utf8mb4
--   COLLATE utf8mb4_bin;
-- USE sistema_registros;

-- ---------------------------------------------------------------------
-- Limpieza (en orden de dependencias)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS bitacora_registro;
DROP TABLE IF EXISTS registros;
DROP TABLE IF EXISTS base_general;
DROP TABLE IF EXISTS bocas_cobranza;
DROP TABLE IF EXISTS tipo_convenio;
DROP TABLE IF EXISTS usuarios;

-- ---------------------------------------------------------------------
-- Usuarios
-- ---------------------------------------------------------------------
CREATE TABLE usuarios (
  id            BIGINT NOT NULL AUTO_INCREMENT,
  username      VARCHAR(100) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role          VARCHAR(20)  NOT NULL DEFAULT 'agente',
  activo        TINYINT(1)   DEFAULT '1',
  creado_en     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id) /*T![clustered_index] CLUSTERED*/,
  UNIQUE KEY uq_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- ---------------------------------------------------------------------
-- Catálogo: tipo_convenio
-- ---------------------------------------------------------------------
CREATE TABLE tipo_convenio (
  id        BIGINT NOT NULL AUTO_INCREMENT,
  nombre    VARCHAR(100) NOT NULL,
  activo    TINYINT(1) DEFAULT '1',
  creado_en DATETIME   DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id) /*T![clustered_index] CLUSTERED*/,
  UNIQUE KEY uq_tipo_convenio_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- ---------------------------------------------------------------------
-- Catálogo: bocas_cobranza
-- ---------------------------------------------------------------------
CREATE TABLE bocas_cobranza (
  id        BIGINT NOT NULL AUTO_INCREMENT,
  nombre    VARCHAR(100) NOT NULL,
  activo    TINYINT(1) DEFAULT '1',
  creado_en DATETIME   DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id) /*T![clustered_index] CLUSTERED*/,
  UNIQUE KEY uq_boca_nombre (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- ---------------------------------------------------------------------
-- Base diaria de referencia (para búsqueda/autocomplete y snapshots)
-- ---------------------------------------------------------------------
CREATE TABLE base_general (
  id             BIGINT NOT NULL AUTO_INCREMENT,
  cliente_unico  VARCHAR(100) NOT NULL,
  nombre_cte     VARCHAR(255),
  gerencia       VARCHAR(255),
  producto       VARCHAR(255),
  fidiapago      VARCHAR(255),
  gestion_desc   TEXT,
  actualizado_en DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id) /*T![clustered_index] CLUSTERED*/,
  UNIQUE KEY uq_bg_cliente_unico (cliente_unico),
  KEY idx_bg_nombre (nombre_cte),
  KEY idx_bg_gerencia (gerencia),
  KEY idx_bg_producto (producto)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- ---------------------------------------------------------------------
-- Registros operativos (con snapshot de campos críticos)
-- ---------------------------------------------------------------------
CREATE TABLE registros (
  id                 BIGINT NOT NULL AUTO_INCREMENT,
  cliente_unico      VARCHAR(100) NOT NULL,

  -- Snapshots (para que el registro no cambie si la base diaria cambia)
  nombre_cte_snap    VARCHAR(255) DEFAULT NULL,
  gerencia_snap      VARCHAR(255) DEFAULT NULL,
  producto_snap      VARCHAR(255) DEFAULT NULL,
  fidiapago_snap     VARCHAR(255) DEFAULT NULL,
  gestion_desc_snap  TEXT DEFAULT NULL,

  -- FK a catálogos (BIGINT para compatibilidad)
  tipo_convenio_id   BIGINT NOT NULL,
  boca_cobranza_id   BIGINT NOT NULL,

  -- Datos del registro
  fecha_promesa      DATE NOT NULL,
  telefono           VARCHAR(30) DEFAULT NULL,
  semana             INT DEFAULT NULL,       -- semana 1..52
  anio               SMALLINT DEFAULT NULL,  -- si decides usar año+semana
  pago_inicial       DECIMAL(12,2) DEFAULT NULL,
  pago_semanal       DECIMAL(12,2) DEFAULT NULL,
  duracion_semanas   INT DEFAULT NULL,
  notas              TEXT DEFAULT NULL,

  -- Archivos (rutas relativas guardadas en disco)
  archivo_convenio   VARCHAR(255) DEFAULT NULL,
  archivo_pago       VARCHAR(255) DEFAULT NULL,
  archivo_gestion    VARCHAR(255) DEFAULT NULL,

  -- Auditoría mínima
  creado_por         BIGINT NOT NULL,
  creado_en          DATETIME DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (id) /*T![clustered_index] CLUSTERED*/,

  KEY idx_reg_cu (cliente_unico),
  KEY fk_tc (tipo_convenio_id),
  KEY fk_bc (boca_cobranza_id),
  KEY fk_user (creado_por),
  KEY idx_reg_semana_anio (anio, semana),

  CONSTRAINT fk_tc
    FOREIGN KEY (tipo_convenio_id) REFERENCES tipo_convenio (id),
  CONSTRAINT fk_bc
    FOREIGN KEY (boca_cobranza_id) REFERENCES bocas_cobranza (id),
  CONSTRAINT fk_user
    FOREIGN KEY (creado_por) REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- ---------------------------------------------------------------------
-- Bitácora (opcional, simple): guarda JSON de cambios por registro
-- ---------------------------------------------------------------------
CREATE TABLE bitacora_registro (
  id           BIGINT NOT NULL AUTO_INCREMENT,
  registro_id  BIGINT NOT NULL,
  accion       VARCHAR(50) NOT NULL,    -- 'CREAR','EDITAR','ELIMINAR'
  cambios_json JSON DEFAULT NULL,       -- resumen de difs
  hecho_por    BIGINT DEFAULT NULL,     -- usuario
  hecho_en     DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id) /*T![clustered_index] CLUSTERED*/,
  KEY idx_bit_reg (registro_id),
  CONSTRAINT fk_bit_reg
    FOREIGN KEY (registro_id) REFERENCES registros (id),
  CONSTRAINT fk_bit_user
    FOREIGN KEY (hecho_por)  REFERENCES usuarios (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin;

-- ---------------------------------------------------------------------
-- Seeds mínimos (catálogos y un admin por defecto)
-- ---------------------------------------------------------------------

INSERT INTO usuarios (username, password_hash, role, activo)
VALUES
  ('admin', '$2b$12$REEMPLAZA_POR_UN_HASH_REAL_BCRYPT', 'admin', 1)
ON DUPLICATE KEY UPDATE username = VALUES(username);

INSERT INTO tipo_convenio (nombre, activo) VALUES
  ('INTENCIÓN', 1),
  ('LIQUIDACIÓN', 1),
  ('RECURRENTE', 1),
  ('RMD', 1),
  ('A PLAZO (SERPIENTES)', 1),
  ('A PALABRA', 1),
  ('A PLAZO', 1)
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);

INSERT INTO bocas_cobranza (nombre, activo) VALUES
  ('PREDICTIVO', 1),
  ('CARTEO', 1),
  ('LLAM PERDIDAS', 1),
  ('NOTIFICADOR', 1),
  ('ALBERCA', 1),
  ('GOTEO', 1),
  ('RECURRENCIA', 1),
  ('MANUAL', 1),
  ('SMS', 1),
  ('OPERATIVO', 1)
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre);
