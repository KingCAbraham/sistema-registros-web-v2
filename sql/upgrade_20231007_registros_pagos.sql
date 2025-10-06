-- Ajustes incrementales para agregar columnas de pagos al catálogo de registros.
-- Ejecuta este script sobre una base existente que aún no tenga los campos.
ALTER TABLE registros
  ADD COLUMN IF NOT EXISTS pago_inicial DECIMAL(12,2) NULL;
ALTER TABLE registros
  ADD COLUMN IF NOT EXISTS pago_semanal DECIMAL(12,2) NULL;
ALTER TABLE registros
  ADD COLUMN IF NOT EXISTS duracion_semanas INT NULL;
