-- crea tablas si no existen
CREATE TABLE IF NOT EXISTS usuarios (
  id INT PRIMARY KEY AUTO_INCREMENT,
  username VARCHAR(100) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'agente',
  activo BOOLEAN DEFAULT TRUE,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tipo_convenio (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(100) UNIQUE NOT NULL,
  activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS bocas_cobranza (
  id INT PRIMARY KEY AUTO_INCREMENT,
  nombre VARCHAR(100) UNIQUE NOT NULL,
  activo BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS base_general (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  cliente_unico VARCHAR(100) NOT NULL,
  nombre_cte VARCHAR(255),
  gerencia VARCHAR(255),
  producto VARCHAR(255),
  fidiapago VARCHAR(255),
  gestion_desc TEXT,
  cargado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_bg_cu (cliente_unico)
);

CREATE TABLE IF NOT EXISTS registros (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  cliente_unico VARCHAR(100) NOT NULL,
  nombre_cte_snap VARCHAR(255),
  gerencia_snap VARCHAR(255),
  producto_snap VARCHAR(255),
  fidiapago_snap VARCHAR(255),
  gestion_desc_snap TEXT,
  tipo_convenio_id INT NOT NULL,
  boca_cobranza_id INT NOT NULL,
  fecha_promesa DATE NOT NULL,
  telefono VARCHAR(30),
  semana INT,
  notas TEXT,
  archivo_convenio VARCHAR(255),
  archivo_pago VARCHAR(255),
  archivo_gestion VARCHAR(255),
  creado_por INT NOT NULL,
  creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_reg_cu (cliente_unico),
  CONSTRAINT fk_tc FOREIGN KEY (tipo_convenio_id) REFERENCES tipo_convenio(id),
  CONSTRAINT fk_bc FOREIGN KEY (boca_cobranza_id) REFERENCES bocas_cobranza(id),
  CONSTRAINT fk_user FOREIGN KEY (creado_por) REFERENCES usuarios(id)
);
