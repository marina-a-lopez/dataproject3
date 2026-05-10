-- Script para migrar usuarios existentes que ya tienen un código CNAE
-- pero cuya descripción (desc_producto) no ha sido sincronizada.

UPDATE usuarios
SET desc_producto = cnae_mappings.descripcion
FROM cnae_mappings
WHERE usuarios.cnae = cnae_mappings.codigo
AND (usuarios.desc_producto IS NULL OR usuarios.desc_producto = 'Producto' OR usuarios.desc_producto = '');
