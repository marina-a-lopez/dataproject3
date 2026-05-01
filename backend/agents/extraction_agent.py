import json
import ast
from vertexai.generative_models import GenerativeModel, Part
from .user_context import get_user_context

class ExtractionAgent:
    def __init__(self):
        # Asegúrate de que el modelo esté configurado e inicializado en la aplicación principal
        self.model = GenerativeModel('gemini-2.5-flash')
        
    def process_receipt_with_context(self, file_bytes: bytes, mime_type: str, user_id: int) -> dict:
        """
        Analiza un ticket/factura en base al contexto profesional del usuario (CNAE, Profesión).
        Devuelve los datos extraídos y un flag hitl_required si el gasto es sospechoso para su perfil.
        """
        # 1. Obtener el contexto del usuario (El "User Context Aggregator")
        user_context = get_user_context(user_id)
        
        # 2. Construir el prompt inyectando el contexto
        prompt = f"""
        Eres un agente experto en extracción de datos y validación fiscal para autónomos en España.
        
        CONTEXTO DEL USUARIO (AUTÓNOMO):
        - Profesión: {user_context.get('profession')}
        - Código CNAE: {user_context.get('cnae_code')} - {user_context.get('cnae_description')}
        - Categorías deducibles comunes: {', '.join(user_context.get('deductible_categories', []))}
        - Categorías NO deducibles / alertas: {', '.join(user_context.get('non_deductible_categories_alerts', []))}
        
        TAREA:
        1. Analiza el documento adjunto (ticket o factura de gasto).
        2. Extrae los campos requeridos.
        3. Compara el concepto del gasto principal con el CONTEXTO DEL USUARIO.
        4. Calcula un 'confidence_score' (de 0.0 a 1.0) sobre la precisión de tu extracción.
        5. Determina si este gasto es lógicamente deducible para su profesión. Por ejemplo, un "paquete de pañales" o "compra en supermercado" NO es deducible para un diseñador gráfico, por lo que requeriría aclaración.
        6. Si el gasto NO cuadra claramente con la profesión o es muy dudoso, marca "needs_clarification" como true y explica el porqué en "clarification_reason".
        
        FORMATO DE SALIDA ESTRICTO (JSON):
        {{
            "proveedor": "Nombre del establecimiento",
            "fecha": "YYYY-MM-DD",
            "concepto": "Resumen de 2-3 palabras de la compra",
            "importe_total": 0.00,
            "confidence_score": 0.95,
            "needs_clarification": false,
            "clarification_reason": "Explicación breve si needs_clarification es true, o null si es false"
        }}
        
        IMPORTANTE: Devuelve ÚNICAMENTE un JSON válido, sin bloques de código markdown ni texto adicional.
        """
        
        try:
            # 3. Llamada a Gemini 2.5 Flash
            response = self.model.generate_content([
                Part.from_data(data=file_bytes, mime_type=mime_type),
                prompt
            ])
            
            # 4. Limpieza y parseo de la respuesta
            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].strip()
                
            try:
                extracted_data = json.loads(text)
            except json.JSONDecodeError:
                # Fallback
                extracted_data = ast.literal_eval(text)
            
            # 5. Embeber el contexto para respuesta completa
            result = {
                "status": "success",
                "extracted_data": extracted_data,
                "user_context_applied": {
                    "profession": user_context.get('profession'),
                    "cnae_code": user_context.get('cnae_code')
                },
                "hitl_required": extracted_data.get("needs_clarification", False)
            }
            return result
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Error en el procesamiento del agente de extracción: {str(e)}",
                "hitl_required": True # Si hay error, requerimos humano por defecto
            }

# Instancia global (singleton) para ser importada por main.py
extraction_agent_instance = ExtractionAgent()
