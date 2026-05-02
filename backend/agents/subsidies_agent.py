import json
import ast
from vertexai.generative_models import GenerativeModel
from vertexai.language_models import TextEmbeddingModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import Usuario

class SubsidiesAgent:
    def __init__(self):
        self.model = GenerativeModel('gemini-2.5-flash')
        try:
            self.embedding_model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        except Exception as e:
            print(f"Warning: Could not load embedding model: {e}")
            self.embedding_model = None

    def _get_embedding(self, text: str):
        if not self.embedding_model: return None
        try:
            return self.embedding_model.get_embeddings([text])[0].values
        except:
            return None

    def get_subsidies_for_user(self, user: Usuario, db: Session) -> dict:
        try:
            context_text = ""
            subvenciones_db = []
            
            # Buscar en DB si hay RAG configurado y el usuario tiene CNAE/IAE
            search_query = ""
            if user.cnae:
                from utils.cnae_mapping import CNAE_MAPPING
                cnae_desc = CNAE_MAPPING.get(user.cnae, "")
                search_query = f"Subvenciones para CNAE {user.cnae} {cnae_desc}"
            elif user.iae:
                search_query = f"Subvenciones para IAE {user.iae}"
                
            if search_query and self.embedding_model:
                query_embedding = self._get_embedding(search_query)
                if query_embedding:
                    # RAG search in subvenciones table
                    sql_query = text('''
                        SELECT titulo, texto_completo, fecha_cierre 
                        FROM subvenciones 
                        ORDER BY embedding <=> cast(:vec as vector) 
                        LIMIT 3
                    ''')
                    
                    resultados = db.execute(sql_query, {"vec": str(query_embedding)}).fetchall()
                    
                    if resultados:
                        context_text = "SUBVENCIONES RECUPERADAS DE LA BASE DE DATOS:\n"
                        for res in resultados:
                            titulo, texto_completo, fecha_cierre = res
                            subvenciones_db.append({"titulo": titulo, "fecha_cierre": str(fecha_cierre)})
                            context_text += f"- Título: {titulo}\n  Texto: {texto_completo}\n  Cierre: {fecha_cierre}\n\n"
                            
            if not context_text:
                context_text = "No se han encontrado subvenciones específicas en la base de datos para este perfil. Da consejos generales sobre dónde buscar subvenciones para autónomos en España, por ejemplo el Kit Digital."

            prompt = f"""
            Eres AItonomo, un experto asesor fiscal para autónomos. Tu tarea es informar al usuario sobre posibles subvenciones basadas en su perfil.
            
            DATOS DEL USUARIO:
            - Nombre: {user.nombre} {user.apellidos}
            - Comunidad Autónoma/Provincia: {user.provincia}
            - CNAE: {user.cnae or 'No especificado'}
            - IAE: {user.iae or 'No especificado'}
            
            {context_text}
            
            TAREA:
            Explica de forma clara, directa y "para dummies" las subvenciones recuperadas que le podrían aplicar, los requisitos generales y próximos pasos recomendados.
            Usa un tono profesional, animado y accesible. Formatea tu respuesta en Markdown limpio. NO pongas la palabra "markdown" ni bloques genericos de código ```.
            """
            
            response = self.model.generate_content(prompt)
            texto_respuesta = response.text.strip()
            
            if texto_respuesta.startswith('```markdown'):
                 texto_respuesta = texto_respuesta[11:]
            if texto_respuesta.startswith('```'):
                 texto_respuesta = texto_respuesta[3:]
            if texto_respuesta.endswith('```'):
                 texto_respuesta = texto_respuesta[:-3]
                 
            return {
                "status": "success",
                "rag_used": len(subvenciones_db) > 0,
                "subvenciones_db": subvenciones_db,
                "answer": texto_respuesta.strip()
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": f"Error en el agente de subvenciones: {str(e)}"
            }

subsidies_agent_instance = SubsidiesAgent()
