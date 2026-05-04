import logging
import re
import os
from typing import List, Dict, Any
import vertexai
from vertexai.rag import RagRetrievalConfig, RagResource, retrieval_query
from sqlalchemy.orm import Session
from database import Usuario

# Configuración de Logging
logger = logging.getLogger("RAG_Subsidies_Agent")

class RagSubsidiesAgent:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID", "Project3Grupo4")
        self.location = os.getenv("GCP_LOCATION", "us-central1")
        self.corpus_id = os.getenv("RAG_CORPUS_ID", "subvenciones_corpus")
        self.initialized = False

    def _initialize(self):
        if not self.initialized:
            try:
                vertexai.init(project=self.project_id, location=self.location)
                self.initialized = True
            except Exception as e:
                logger.error(f"Error initializing Vertex AI: {e}")

    def get_recommendations(self, user: Usuario, db: Session, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Obtiene recomendaciones de subvenciones personalizadas usando RAG Engine.
        """
        self._initialize()
        
        if not user.cnae and not user.desc_producto:
            return []

        corpus_name = f"projects/{self.project_id}/locations/{self.location}/ragCorpora/{self.corpus_id}"
        
        # Consulta semántica mejorada
        query_text = f"Subvenciones para actividad {user.desc_producto or ''} con CNAE {user.cnae or ''}"
        
        try:
            retrieval_config = RagRetrievalConfig(top_k=top_k * 2) # Recuperamos de más para filtrar territorialmente
            
            response = retrieval_query(
                rag_resources=[RagResource(rag_corpus=corpus_name)],
                text=query_text,
                rag_retrieval_config=retrieval_config
            )
            
            recommendations = []
            user_provincia = (user.provincia or "").strip().lower()

            for context in response.contexts:
                content = context.text.lower()
                
                # Filtro territorial (Provincia o Nacional)
                if user_provincia in content or "nacional" in content or "estatal" in content:
                    
                    # Extracción de ID_BDNS (Prioriza metadatos)
                    id_bdns = "N/A"
                    if hasattr(context, 'metadata') and 'id_bdns' in context.metadata:
                        id_bdns = context.metadata['id_bdns']
                    else:
                        match = re.search(r'bdns[:\s]+(\d+)', content)
                        if match: id_bdns = match.group(1)

                    # Intentamos extraer un título limpio si no está en metadatos
                    titulo = "Subvención Identificada"
                    first_line = context.text.split('\n')[0]
                    if len(first_line) < 100:
                        titulo = first_line

                    recommendations.append({
                        "id_bdns": id_bdns,
                        "titulo": titulo,
                        "score": getattr(context, 'score', 0.0),
                        "snippet": context.text[:200] + "..."
                    })
            
            # Devolvemos solo el top_k después del filtrado
            return sorted(recommendations, key=lambda x: x['score'], reverse=True)[:top_k]

        except Exception as e:
            logger.error(f"Error in RagSubsidiesAgent: {e}")
            return []

# Instancia única del agente
rag_subsidies_agent_instance = RagSubsidiesAgent()
