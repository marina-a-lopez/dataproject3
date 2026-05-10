import os
import json
import urllib.request
import re

CACHE_FILE = "iae_cache.json"
MAPEO_IAE = {}

def cargar_catalogo_iae():
    """
    Descarga o lee del cache el catálogo de IAEs y devuelve un diccionario global MAPEO_IAE.
    El formato es { "Epigrafe_formateado": "Sección X, Epígrafe Y - Descripcion" }.
    """
    global MAPEO_IAE
    
    # Si ya lo hemos cargado en memoria en esta sesión, lo devolvemos
    if MAPEO_IAE:
        return MAPEO_IAE
        
    # Intentar leer del cache local primero
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                MAPEO_IAE = json.load(f)
            return MAPEO_IAE
        except Exception as e:
            print(f"Error al leer el cache IAE: {e}")

    # Si no hay cache o falla, descargar de internet
    url = "https://datosabiertos.regiondemurcia.es/catalogo/recursos/ayuntamiento-de-molina-de-segura/fiscal-iae.json"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            for item in data:
                epi = item.get("Epigrafe", "").strip()
                sec = item.get("Seccion", "").strip()
                desc = item.get("Descripcion", "").strip()
                
                if not epi:
                    continue
                
                # Formatear epígrafes de 4 dígitos: de '7212' a '721.2'
                epi_formateado = epi
                if len(epi) == 4 and epi.isdigit():
                    epi_formateado = f"{epi[:3]}.{epi[3]}"
                    
                # Generar el string descriptivo rico en contexto
                valor_completo = f"Sección {sec}, Epígrafe {epi_formateado} - {desc}"
                
                # Guardar en el diccionario. Si hay duplicados (mismo epígrafe en distintas secciones),
                # guardaremos el último, o podríamos juntarlos, pero mantendremos el último por simplicidad
                # o podemos indexar por un hash, pero el usuario pidió que la key sea el epígrafe.
                MAPEO_IAE[epi_formateado] = valor_completo
                # También guardamos el original por si acaso alguien lo busca sin punto
                if epi_formateado != epi:
                    MAPEO_IAE[epi] = valor_completo
                    
            # Guardar el mapeo en cache para la próxima vez
            try:
                with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                    json.dump(MAPEO_IAE, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Error al guardar el cache IAE: {e}")
                
            return MAPEO_IAE
            
    except Exception as e:
        print(f"Error al descargar el catálogo IAE: {e}")
        return {}
