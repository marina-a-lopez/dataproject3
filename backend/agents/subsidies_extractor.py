"""import os
import vertexai
from vertexai.generative_models import GenerativeModel

class SubsidiesExtractorAgent:
    def __init__(self):
        # Usamos gemini-2.5-flash para procesar texto rápido y de manera estructurada
        self.model = GenerativeModel('gemini-2.5-flash')

    def process_scraped_text(self, texto_sucio: str) -> list:
        prompt = f
        Actúa como un extractor de datos profesional. Analiza el siguiente texto de una web de subvenciones y genera una lista de objetos JSON.

        Campos obligatorios por cada subvención:

        id_bdns: El código identificador oficial de la BDNS (si no existe, inventa uno único de 6 dígitos).

        titulo: Nombre oficial de la subvención.

        cnae_target: Los códigos CNAE a los que va dirigida (separados por comas).

        fecha_cierre: Fecha límite en formato AAAA-MM-DD.

        texto_completo: Un resumen técnico que incluya cuantía, requisitos y pasos para solicitarla.

        Formato de salida: JSON puro (una lista de objetos).

        Texto a procesar: {texto_sucio}
        

        try:
            response = self.model.generate_content(prompt)
            texto_respuesta = response.text.strip()
            
            # Limpiar posible formato markdown (```json ... ```)
            if texto_respuesta.startswith('```json'):
                texto_respuesta = texto_respuesta[7:]
            elif texto_respuesta.startswith('```'):
                texto_respuesta = texto_respuesta[3:]
            
            if texto_respuesta.endswith('```'):
                texto_respuesta = texto_respuesta[:-3]
                
            texto_respuesta = texto_respuesta.strip()
            
            # Parsear la cadena JSON a lista de diccionarios de Python
            import json
            resultados = json.loads(texto_respuesta)
            return resultados
        except Exception as e:
            import traceback
            traceback.print_exc()
            return [{"error": f"Error procesando el texto: {str(e)}"}]

# Instancia singleton para ser usada en otros scripts o endpoints
subsidies_extractor_instance = SubsidiesExtractorAgent()
"""