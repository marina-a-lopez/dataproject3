import json
import logging
import re
import os
from typing import List, Dict, Any
import vertexai
from vertexai.rag import RagRetrievalConfig, RagResource, retrieval_query
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import text
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("RAG_Matching_Service")

def get_user_matches(
    project_id: str = None,
    location: str = "us-central1",
    corpus_id: str = "subvenciones_corpus",
    instance_connection_name: str = None,
    db_user: str = "admin",
    db_password: str = None,
    db_name: str = "postgres"
) -> str:
    """
    Función optimizada para realizar matching semántico entre usuarios y subvenciones.
    Diseñada para ser integrada en Cloud Run o ejecutada en notebooks.
    
    Args:
        project_id: ID del proyecto GCP. Si es None, usa GCP_PROJECT_ID del entorno.
        location: Región de Vertex AI.
        corpus_id: ID del Corpus en RAG Engine.
        instance_connection_name: Nombre de conexión Cloud SQL (project:region:instance).
        db_user: Usuario de DB.
        db_password: Password de DB.
        db_name: Nombre de DB.
        
    Returns:
        str: JSON con el mapeo usuario_id -> subvenciones recomendadas.
    """
    
    # Priorizar variables de entorno si no se pasan argumentos
    project_id = project_id or os.getenv("GCP_PROJECT_ID")
    db_password = db_password or os.getenv("DB_PASSWORD")
    instance_connection_name = instance_connection_name or os.getenv("INSTANCE_CONNECTION_NAME", f"{project_id}:us-central1:db-aitonomo")
    
    if not project_id:
        return json.dumps({"error": "GCP_PROJECT_ID no configurado"})

    # 1. Inicialización de Vertex AI
    try:
        vertexai.init(project=project_id, location=location)
    except Exception as e:
        logger.error(f"Error inicializando Vertex AI: {e}")
        return json.dumps({"error": "Vertex AI Init Failed", "details": str(e)})

    # 2. Conexión Eficiente a Cloud SQL
    connector = Connector()
    
    def getconn():
        return connector.connect(
            instance_connection_name,
            "pg8000",
            user=db_user,
            password=db_password,
            db=db_name
        )

    # Motor SQLAlchemy con pool de conexiones
    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=getconn)
    
    # 3. Lectura de Usuarios
    users_data = []
    try:
        with engine.connect() as conn:
            # Query optimizada para el esquema solicitado
            result = conn.execute(text("SELECT id, provincia, cnae, descripcion_actividad FROM usuarios"))
            users_data = [dict(row._mapping) for row in result]
            logger.info(f"Procesando {len(users_data)} usuarios desde Cloud SQL.")
    except Exception as e:
        logger.error(f"Error en Cloud SQL: {e}")
        return json.dumps({"error": "Database error", "details": str(e)})
    finally:
        # Cerramos el conector pero el pool de engine puede persistir si se integra en API
        connector.close()

    # 4. Matching Semántico via RAG Engine
    recommendations_map = {}
    corpus_name = f"projects/{project_id}/locations/{location}/ragCorpora/{corpus_id}"
    
    # Recuperamos los top 10 candidatos para aplicar filtro territorial posterior
    retrieval_config = RagRetrievalConfig(top_k=10)

    for user in users_data:
        u_id = str(user['id'])
        u_provincia = (user['provincia'] or "").strip().lower()
        
        # Consulta enriquecida: Actividad + CNAE
        query_text = (
            f"Subvenciones para actividad '{user['descripcion_actividad']}' "
            f"con código CNAE {user['cnae']}."
        )
        
        try:
            # Ejecución del RetrievalQuery
            # Nota: Utiliza internamente text-embedding-005 configurado en el corpus
            response = retrieval_query(
                rag_resources=[RagResource(rag_corpus=corpus_name)],
                text=query_text,
                rag_retrieval_config=retrieval_config
            )
            
            user_recs = []
            
            for context in response.contexts:
                content = context.text.lower()
                
                # FILTRO POST-BÚSQUEDA: Relevancia Territorial
                # Verificamos si la provincia coincide o si es de ámbito nacional/estatal
                if u_provincia in content or "nacional" in content or "estatal" in content:
                    
                    # Extracción del ID_BDNS (Metadatos o Regex)
                    id_bdns = "ID_PENDIENTE"
                    if hasattr(context, 'metadata') and 'id_bdns' in context.metadata:
                        id_bdns = context.metadata['id_bdns']
                    else:
                        # Extracción por patrón si no hay metadatos estructurados
                        match = re.search(r'bdns[:\s]+(\d+)', content)
                        if match: id_bdns = match.group(1)

                    user_recs.append({
                        "id_bdns": id_bdns,
                        "score": getattr(context, 'score', 0.0),
                        "territorio_match": u_provincia in content
                    })
            
            # Ordenar por relevancia
            recommendations_map[u_id] = sorted(user_recs, key=lambda x: x['score'], reverse=True)
            
        except Exception as e:
            logger.warning(f"Error en RAG para usuario {u_id}: {e}")
            recommendations_map[u_id] = []
            if "quota" in str(e).lower():
                logger.error("Cuota de API excedida.")
                break

    return json.dumps(recommendations_map, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    # Test rápido si se ejecuta localmente o en Notebook
    # Asegúrate de tener las credenciales en el .env o entorno
    print("Iniciando matching de subvenciones...")
    res = get_user_matches()
    print(res)
