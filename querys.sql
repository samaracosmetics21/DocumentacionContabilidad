------consulta para facturas de MP
SELECT 
    NRODCTO, 
    PASSWORDIN, 
    BRUTO, 
    IVABRUTO, 
    VLRETFTE, 
    VRETICA, 
    VRETENIVA, 
    (bruto + IVABRUTO) AS SUBTOTAL, 
    ((bruto + IVABRUTO) - VLRETFTE - VRETICA - VRETENIVA) AS TOTAL
FROM 
    TRADE 
WHERE  
    NRODCTO LIKE '14662' AND ORIGEN='COM' AND TIPODCTO='FR'

------Consulta para facturas de servicios
SELECT 
    NRODCTO, 
    PASSWORDIN, 
    BRUTO, 
    IVABRUTO, 
    VLRETFTE, 
    VRETICA, 
    VRETENIVA, 
    (bruto + IVABRUTO) AS SUBTOTAL, 
    ((bruto + IVABRUTO) - VLRETFTE - VRETICA - VRETENIVA) AS TOTAL 
FROM 
    TRADE 
WHERE  
    NRODCTO LIKE '14662' AND ORIGEN='COM' AND TIPODCTO='FS'

    -----------------------------
    select trade.nrodcto, trade.bruto, trade.IVABRUTO, trade.NIT, mtprocli.nombre, mvtrade.CANTIDAD, mvtrade.nombre as nombre_referencia, mvtrade.producto as numero_referencia 
from trade 
inner join mvtrade on trade.nrodcto=mvtrade.nrodcto
inner join mtprocli on trade.nit=mtprocli.nit

where trade.nrodcto='11164' and trade.ORIGEN='COM' and trade.tipodcto='OC' and mvtrade.ORIGEN='COM' and mvtrade.tipodcto='OC' 

--------------------
-- Paso 1: Agregar las columnas con valores predeterminados
ALTER TABLE facturas
ADD COLUMN nrodcto_oc VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_NRODCTO',
ADD COLUMN bruto_oc DECIMAL(15, 2),
ADD COLUMN ivabruto_oc DECIMAL(15, 2),
ADD COLUMN nit_oc VARCHAR(20) NOT NULL DEFAULT 'DEFAULT_NIT',
ADD COLUMN nombre_cliente_oc VARCHAR(255) NOT NULL DEFAULT 'DEFAULT_NOMBRE_CLIENTE',
ADD COLUMN cantidad_oc INT,
ADD COLUMN nombre_referencia_oc VARCHAR(255),
ADD COLUMN numero_referencia_oc VARCHAR(50),
ADD COLUMN archivo_path_oc TEXT NOT NULL DEFAULT 'DEFAULT_PATH',
ADD COLUMN hora_registro_oc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
ADD COLUMN usuario_id_oc INT NOT NULL DEFAULT 1; -- Usamos 1 como valor predeterminado para el usuario, ajusta según el caso.


CREATE TABLE ordenes_compras (
    id SERIAL PRIMARY KEY,
    nrodcto_oc VARCHAR(50) NOT NULL DEFAULT 'DEFAULT_NRODCTO',
    bruto_oc DECIMAL(15, 2),
    ivabruto_oc DECIMAL(15, 2),
    nit_oc VARCHAR(20) NOT NULL DEFAULT 'DEFAULT_NIT',
    nombre_cliente_oc VARCHAR(255) NOT NULL DEFAULT 'DEFAULT_NOMBRE_CLIENTE',
    cantidad_oc INT,
    nombre_referencia_oc VARCHAR(255),
    numero_referencia_oc VARCHAR(50),
    archivo_path_oc TEXT NOT NULL DEFAULT 'DEFAULT_PATH',
    hora_registro_oc TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    usuario_id_oc INT NOT NULL DEFAULT 1
);

-----query pac actualizar masivo facturas por rango de fecha. desde servicio - aprobacion jefe servcio y lo dejamos en gestion final
UPDATE facturas
SET 
    hora_aprobacion = NOW(),
    aprobado_servicios = 15,
    usuario_asignado_servicios = 15,
    estado = 'Aprobado',
    pago_servicios = 'Aprobado',
    hora_aprobacion_pago_servicio = NOW(),
    estado_usuario_asignado = 'Aprobado',
    hora_aprobacion_asignado = NOW()
WHERE fecha_seleccionada >= '2025-06-01'
  AND fecha_seleccionada <  '2025-07-01';