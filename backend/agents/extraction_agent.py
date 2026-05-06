import json
import ast
from vertexai.generative_models import GenerativeModel, Part
from vertexai.language_models import TextEmbeddingModel
from sqlalchemy.orm import Session
from sqlalchemy import text

class ExtractionAgent:
    def __init__(self):
        self.model = GenerativeModel('gemini-2.5-flash')
        # Utilizamos embeddings para la búsqueda RAG
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

    def process_receipt_with_context(self, file_bytes: bytes, mime_type: str, user, db: Session) -> dict:
        """
        Analiza un ticket/factura, extrae el concepto, realiza búsqueda RAG en normativa fiscal
        basada en el IAE del usuario, y determina si es deducible.
        """
        try:
            # PASO 1: Extracción básica del ticket
            extract_prompt = """
            Extrae de este ticket/factura los siguientes datos en JSON estricto:
            {
                "proveedor": "Nombre",
                "fecha": "DD-MM-YYYY",
                "concepto": "Breve resumen de la compra (ej. monitor, comida, gasolina)",
                "importe_total": 0.00
            }
            Devuelve SOLO el JSON, sin formato markdown.
            """
            extract_res = self.model.generate_content([Part.from_data(data=file_bytes, mime_type=mime_type), extract_prompt])
            text_out = extract_res.text.strip().replace('```json', '').replace('```', '').strip()
            
            try:
                extracted_data = json.loads(text_out)
            except:
                extracted_data = ast.literal_eval(text_out)
                
            concepto = extracted_data.get("concepto", "Gasto general")
            
            # PASO 2: Búsqueda RAG en la base de datos de normativas
            contexto_normativo = ""
            if self.embedding_model and user.iae:
                search_query = f"Deducibilidad de {concepto} para la actividad IAE {user.iae}"
                query_embedding = self._get_embedding(search_query)
                
                if query_embedding:
                    # Búsqueda semántica usando pgvector (distancia coseno: <=>)
                    # Recuperamos los 3 fragmentos más relevantes
                    sql_query = text('''
                        SELECT contenido, fuente 
                        FROM reglas_deduccion 
                        ORDER BY embedding <=> cast(:vec as vector) 
                        LIMIT 3
                    ''')
                    
                    resultados = db.execute(sql_query, {"vec": str(query_embedding)}).fetchall()
                    
                    if resultados:
                        contexto_normativo = "NORMATIVA FISCAL RECUPERADA (RAG):\n"
                        for res in resultados:
                            contexto_normativo += f"- Fuente: {res[1]}\n  Texto: {res[0]}\n\n"
            
            # Si no hay RAG o IAE, indicamos que no hay normativas específicas
            if not contexto_normativo:
                contexto_normativo = "No se ha recuperado normativa específica para este IAE. Basarse en la regla general de gastos deducibles (afectación a la actividad)."

            # PASO 3: Validación final con RAG
            eval_prompt = f"""
            Eres un experto fiscal. Evalúa la deducibilidad de este gasto para el usuario:
            
            DATOS DEL GASTO:
            - Concepto: {concepto}
            - Importe: {extracted_data.get('importe_total')}
            
            DATOS DEL USUARIO:
            - IAE (Epígrafe): {user.iae or 'No especificado'}
            - CNAE: {user.cnae or 'No especificado'}
            
            {contexto_normativo}
            
            EVALÚA:
            1. ¿Es este gasto deducible para su actividad económica (IAE)?
            2. Si no es deducible o hay dudas (ej. comida, ropa no laboral), marca needs_clarification como true.
            3. Explica el porqué citando la normativa recuperada si es posible.
            
            Devuelve un JSON con el resultado final:
            {{
                "proveedor": "{extracted_data.get('proveedor')}",
                "fecha": "{extracted_data.get('fecha')}",
                "concepto": "{concepto}",
                "importe_total": {extracted_data.get('importe_total', 0.0)},
                "is_deducible": true,
                "needs_clarification": false,
                "clarification_reason": "Explicación de la decisión basada en la normativa"
            }}
            Solo JSON.
            """
            
            eval_res = self.model.generate_content([eval_prompt])
            eval_text = eval_res.text.strip().replace('```json', '').replace('```', '').strip()
            
            try:
                final_data = json.loads(eval_text)
            except:
                final_data = ast.literal_eval(eval_text)
            
            return {
                "status": "success",
                "extracted_data": final_data,
                "user_context_applied": {
                    "iae": user.iae,
                    "cnae": user.cnae,
                    "rag_used": bool(contexto_normativo and "NORMATIVA FISCAL" in contexto_normativo)
                },
                "hitl_required": final_data.get("needs_clarification", False)
            }
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {
                "status": "error",
                "error": f"Error en el agente: {str(e)}",
                "hitl_required": True
            }

extraction_agent_instance = ExtractionAgent()
