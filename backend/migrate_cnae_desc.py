import os
import sys

# Asegurar que podemos importar desde el directorio actual
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Usuario
from utils.cnae_mapping import CNAE_MAPPING

def migrate_cnae():
    if not SessionLocal:
        print("No se pudo conectar a la base de datos.")
        return

    db = SessionLocal()
    try:
        usuarios = db.query(Usuario).filter(Usuario.cnae.isnot(None)).all()
        actualizados = 0
        for user in usuarios:
            if user.cnae in CNAE_MAPPING:
                nueva_desc = CNAE_MAPPING[user.cnae]
                if user.desc_producto != nueva_desc:
                    user.desc_producto = nueva_desc
                    actualizados += 1
        
        db.commit()
        print(f"Migración completada. Se han actualizado {actualizados} usuarios.")
    except Exception as e:
        print(f"Error durante la migración: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Iniciando migración de descripciones de CNAE...")
    migrate_cnae()
