import base64
import json
import functions_framework
import sqlalchemy
import vertexai
import requests
from vertexai.generative_models import GenerativeModel, GenerationConfig
import os

# 1. Configuración del Proyecto y Cloud SQL
PROJECT_ID = os.getenv("GCP_PROJECT_ID", "project3grupo4")
REGION = os.getenv("GCP_REGION", "europe-southwest1")

# Datos de conexión
DB_USER = os.getenv("DB_USER", "admin")
DB_PASS = os.getenv("DB_PASS", "Edem2526.")
DB_NAME = os.getenv("DB_NAME", "aitonomo_db")
DB_HOST = os.getenv("DB_HOST", "34.175.20.225")

# Inicializar Vertex AI
vertexai.init(project=PROJECT_ID, location=REGION)

# 2. Configuración del Engine (Conexión Directa por IP)
pool = sqlalchemy.create_engine(
    f"postgresql+pg8000://{DB_USER}:{DB_PASS}@{DB_HOST}:5432/{DB_NAME}",
    pool_size=5,
    max_overflow=2,
    pool_timeout=30
)

def obtener_nuevas_subvenciones():
    """Obtiene las últimas convocatorias reales desde la API de BDNS."""
    url = "https://www.infosubvenciones.es/bdnstrans/api/convocatorias/busqueda"
    payload = {
        "indicePagina": 0,
        "elementosPorPagina": 10,
        "campoOrden": "fecha",
        "direccion": "desc",
        "filtro": {}
    }
    
    try:
        print("--- LOG: Consultando API de infosubvenciones.es ---")
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        subvenciones = []
        for item in data:
            # El ID de la convocatoria es el código BDNS
            id_bdns = str(item.get("id", ""))
            titulo = item.get("titulo", "Sin título")
            organo = item.get("organo", "Desconocido")
            instrumento = item.get("instrumento", "")
            
            # Construimos un bloque de texto con toda la info disponible para que Gemini la analice
            texto_para_analizar = f"""
            TÍTULO: {titulo}
            ÓRGANO CONVOCANTE: {organo}
            IDENTIFICADOR BDNS: {id_bdns}
            TIPO DE AYUDA: {instrumento}
            """
            
            subvenciones.append({
                "id_bdns": id_bdns,
                "texto_legal": texto_para_analizar.strip()
            })
            
        print(f"--- LOG: Se han recuperado {len(subvenciones)} nuevas convocatorias ---")
        return subvenciones
        
    except Exception as e:
        print(f"❌ ERROR haciendo scraping/API: {str(e)}")
        return []

@functions_framework.http
def procesar_bdns(request):
    print("--- LOG 1: Función iniciada (Scraping Real) ---")
    subvenciones = obtener_nuevas_subvenciones()
    
    if not subvenciones:
        print("--- LOG: No hay subvenciones para procesar. Finalizando. ---")
        return "Sin datos"

    # Configuración del modelo Gemini
    model = GenerativeModel("gemini-2.5-flash")
    config_json = GenerationConfig(response_mime_type="application/json")
    
    for sub in subvenciones:
        print(f"--- LOG 2: Procesando BDNS {sub['id_bdns']} con Gemini ---")
        texto = sub["texto_legal"]
        
        prompt = f"""
        Actúa como un experto en subvenciones. Extrae la información clave del siguiente resumen técnico en formato JSON:
        - "titulo": El título de la subvención.
        - "cnae_target": Los códigos CNAE (4 dígitos) que podrían aplicar a esta ayuda, separados por comas. Si no se mencionan explícitamente, infiere los más probables basándote en el título y el órgano (ej. si es para digitalización, incluye 6201, 6202).
        - "fecha_cierre": Busca menciones a plazos o fechas límite y devuelve el formato DD-MM-YYYY. Si no hay una fecha clara, devuelve null.
        
        Texto a analizar: {texto}
        """
        
        try:
            # 1. Llamada a la IA para extraer datos
            respuesta = model.generate_content(prompt, generation_config=config_json)
            datos_ia = json.loads(respuesta.text)
            print(f"--- LOG 3: IA analizó con éxito: {datos_ia['titulo']} ---")
            
            # 2. Inserción en Base de Datos con lógica ON CONFLICT (Upsert)
            with pool.connect() as db_conn:
                insert_stmt = sqlalchemy.text("""
                    INSERT INTO subvenciones (id_bdns, titulo, cnae_target, fecha_cierre, texto_completo) 
                    VALUES (:id_bdns, :titulo, :cnae_target, CAST(:fecha_cierre AS DATE), :texto_completo)
                    ON CONFLICT (id_bdns) 
                    DO UPDATE SET 
                        titulo = EXCLUDED.titulo,
                        cnae_target = EXCLUDED.cnae_target,
                        fecha_cierre = EXCLUDED.fecha_cierre,
                        texto_completo = EXCLUDED.texto_completo;
                """)
                
                db_conn.execute(insert_stmt, parameters={
                    "id_bdns": sub["id_bdns"],
                    "titulo": datos_ia.get("titulo", "Subvención sin título"),
                    "cnae_target": datos_ia.get("cnae_target", ""),
                    "fecha_cierre": datos_ia.get("fecha_cierre") if datos_ia.get("fecha_cierre") else None,
                    "texto_completo": texto
                })
                db_conn.commit()
                
            print(f"✅ LOG 5: ÉXITO. Subvención {sub['id_bdns']} guardada.")
            
        except Exception as error:
            print(f"❌ ERROR procesando BDNS {sub['id_bdns']}: {str(error)}")
            continue
            
    return "Ejecución finalizada"
