import base64
import json
import functions_framework
import sqlalchemy
import vertexai
import requests
import os
import xml.etree.ElementTree as ET
from vertexai.generative_models import GenerativeModel, GenerationConfig

# 1. Configuración del Proyecto y Cloud SQL
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "project3grupo4")
REGION = os.getenv("GCP_REGION", "europe-southwest1") # Para la BD

DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "Edem2526.")
DB_NAME = os.getenv("DB_NAME", "aitonomo_db")
DB_HOST = os.getenv("DB_HOST", "34.175.20.225")

# INICIALIZACIÓN IA: Usamos el centro de datos que tiene el modelo activo
vertexai.init(project=PROJECT_ID, location="europe-west1")

pool = sqlalchemy.create_engine(
    f"postgresql+pg8000://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}",
    pool_size=5,
    max_overflow=2,
    pool_timeout=30
)

def obtener_nuevas_subvenciones(limite=50):
    """Obtiene subvenciones del BOE y descarga el texto completo de cada una."""
    url_boe = "https://www.boe.es/rss/canal.php?c=ayudas"
    
    try:
        print("--- LOG: Consultando fuente oficial del BOE ---")
        response = requests.get(url_boe, timeout=15)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        
        subvenciones = []
        items = root.findall('.//item')
        
        print(f"--- LOG: Total items encontrados en el RSS: {len(items)} ---")

        for item in items[:limite]:
            titulo = item.find('title').text if item.find('title') is not None else "Sin título"
            link = item.find('link').text if item.find('link') is not None else ""
            descripcion = item.find('description').text if item.find('description') is not None else ""
            
            # Extraemos el ID oficial (BOE-...)
            id_bdns = link.split('id=')[-1] if 'id=' in link else titulo[:20].replace(" ", "_")
            
            # --- NUEVA LÓGICA: EXTRAER EL TEXTO COMPLETO DEL XML INDIVIDUAL ---
            texto_completo_boe = ""
            if id_bdns.startswith("BOE-"):
                url_xml_detalle = f"https://www.boe.es/diario_boe/xml.php?id={id_bdns}"
                try:
                    res_detalle = requests.get(url_xml_detalle, timeout=10)
                    if res_detalle.status_code == 200:
                        root_detalle = ET.fromstring(res_detalle.content)
                        # El BOE guarda el texto del documento dentro de la etiqueta <texto>
                        nodo_texto = root_detalle.find('.//texto')
                        if nodo_texto is not None:
                            # Extraemos todo el texto puro, quitando etiquetas HTML internas
                            texto_completo_boe = "".join(nodo_texto.itertext()).strip()
                except Exception as e:
                    print(f"Aviso: No se pudo obtener el texto extra de {id_bdns}: {e}")
            # -------------------------------------------------------------------

            texto_para_analizar = f"""
            TÍTULO: {titulo}
            DESCRIPCIÓN Y ÓRGANO: {descripcion}
            ENLACE OFICIAL: {link}
            
            --- TEXTO COMPLETO DEL BOE ---
            {texto_completo_boe[:15000]} 
            """
            # NOTA: Limitamos el texto a 15.000 caracteres por si es una ley gigantesca, 
            # para no saturar a la IA ni gastar demasiados tokens.
            
            subvenciones.append({
                "id_bdns": id_bdns,
                "texto_legal": texto_para_analizar.strip()
            })
            
        print(f"--- LOG: Se procesarán {len(subvenciones)} subvenciones con texto extendido ---")
        return subvenciones
        
    except Exception as e:
        print(f"❌ ERROR leyendo el BOE: {str(e)}")
        return []

@functions_framework.http
def procesar_bdns(request):
    print("--- LOG 1: Función iniciada ---")
    
    subvenciones = obtener_nuevas_subvenciones(limite=50)
    
    if not subvenciones:
        print("--- LOG: No hay subvenciones para procesar ---")
        return "Sin datos", 200

    # Usamos el modelo que sabemos que está disponible
    model = GenerativeModel("gemini-2.5-flash")
    config_json = GenerationConfig(response_mime_type="application/json")
    
    for sub in subvenciones:
        print(f"--- LOG 2: Procesando {sub['id_bdns']} ---")
        
        texto = sub["texto_legal"]
        
        prompt = f"""
            Eres un analista experto en subvenciones públicas en España. Extrae información estructurada del texto proporcionado.

            DEVUELVE ÚNICAMENTE un JSON válido (sin texto adicional, sin explicaciones, sin markdown).

            Formato exacto de salida:
            {{
            "titulo": string,
            "cnae_target": string,
            "fecha_cierre": string|null
            }}

            REGLAS:

            1. "titulo"
            - Extrae el título oficial de la subvención.
            - Limpia texto irrelevante (ej. "Extracto de...", "BDNS", etc.).
            - Máximo 150 caracteres.

            2. "cnae_target"
            - Devuelve códigos CNAE de 4 dígitos separados por comas (ej: "6201, 5610").
            - Si aparecen explícitamente → úsalos.
            - Si NO aparecen:
            - Infiere SOLO si es muy claro (ej. tecnología → 6201, hostelería → 5610).
            - Si no es evidente → devuelve "" (string vacío).
            - NO inventes códigos aleatorios.

            3. "fecha_cierre"
            - Busca fecha límite de solicitud.
            - Formato obligatorio: YYYY-MM-DD
            - Si hay varias fechas → usa la más relevante para solicitud.
            - Si no hay fecha clara → null

            4. Validación estricta:
            - No inventar información
            - No añadir campos extra
            - JSON debe ser parseable directamente con json.loads()

            Texto a analizar:
            {texto}
            """
        
        try:
            respuesta = model.generate_content(prompt, generation_config=config_json)
            datos_ia = json.loads(respuesta.text)
            
            with pool.connect() as db_conn:
                insert_stmt = sqlalchemy.text("""
                    INSERT INTO subvenciones (id_bdns, titulo, cnae_target, fecha_cierre, texto_completo) 
                    VALUES (:id_bdns, :titulo, :cnae_target, CAST(:fecha_cierre AS DATE), :texto_completo)
                    ON CONFLICT (id_bdns) DO NOTHING;
                """)
                
                db_conn.execute(insert_stmt, {
                    "id_bdns": sub["id_bdns"],
                    "titulo": datos_ia.get("titulo", "Subvención sin título"),
                    "cnae_target": datos_ia.get("cnae_target", ""),
                    "fecha_cierre": datos_ia.get("fecha_cierre"),
                    "texto_completo": texto
                })
                
                db_conn.commit()
                
            print(f"✅ Guardado (o ignorado si ya existía): {sub['id_bdns']}")
            
        except Exception as error:
            print(f"❌ ERROR procesando {sub['id_bdns']}: {str(error)}")
            continue
            
    return "Ejecución finalizada", 200