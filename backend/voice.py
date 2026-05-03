import os
import json
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from dotenv import load_dotenv

load_dotenv()

def _clean_schema(schema: dict) -> dict:
    """Elimina anyOf con null que Vertex AI no soporta. Convierte Optional[X] -> X."""
    if isinstance(schema, dict):
        if "anyOf" in schema:
            non_null = [s for s in schema["anyOf"] if s.get("type") != "null"]
            if len(non_null) == 1:
                cleaned = {**schema, **non_null[0]}
                cleaned.pop("anyOf")
                return _clean_schema(cleaned)
        return {k: _clean_schema(v) for k, v in schema.items()}
    if isinstance(schema, list):
        return [_clean_schema(i) for i in schema]
    return schema


class ClientExtraction(BaseModel):
    nombre_empresa: str = Field(description="Nombre o nombre de la empresa del cliente", default="")
    nif_cif: str = Field(description="NIF, DNI o CIF del cliente", default="")
    telefono: Optional[str] = Field(description="Número de teléfono", default=None)
    email: Optional[str] = Field(description="Correo electrónico", default=None)
    direccion_fiscal: str = Field(description="Dirección fiscal completa", default="")
    direccion_comercial: Optional[str] = Field(description="Dirección comercial si es distinta", default=None)

class QuoteLine(BaseModel):
    concepto: str = Field(description="Concepto de la línea de presupuesto o factura", default="")
    cantidad: float = Field(description="Cantidad de unidades", default=1.0)
    precio_unitario: float = Field(description="Precio unitario en euros", default=0.0)

class QuoteExtraction(BaseModel):
    lineas: list[QuoteLine] = Field(description="Lista de líneas o conceptos a facturar", default=[])

class CalendarExtraction(BaseModel):
    titulo: str = Field(description="Título corto y profesional del evento, máximo 5 palabras", default="Nuevo Evento")
    fecha: str = Field(description="Fecha del evento en formato ISO YYYY-MM-DD", default="")
    descripcion: Optional[str] = Field(description="Detalles adicionales, lugar, personas involucradas o notas del evento", default=None)
    tipo: str = Field(description="Categoría del evento: 'personal', 'fiscal' (impuestos, IVA, gestoría) o 'reunion' (clientes, Zoom, citas)", default="personal")
    color: str = Field(description="Color hexadecimal para la UI: #4a90e2 personal, #e74c3c fiscal, #27ae60 reunion", default="#4a90e2")

def process_voice_to_text(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Procesa el audio y lo transcribe a texto."""
    model = GenerativeModel('gemini-2.5-flash')
    response = model.generate_content([
        Part.from_data(
            data=audio_bytes,
            mime_type='audio/wav'
        ),
        "Por favor, transcribe exactamente este audio a texto."
    ])
    return response.text

def extract_client_data(text: str) -> dict:
    """Extrae los datos del cliente a partir de un texto libre."""
    system_prompt = """Eres un asistente para autónomos en España.
    Tu objetivo es extraer datos de clientes a partir de un texto libre.
    Si algún dato no se menciona, déjalo como null o vacío.
    Asegúrate de formatear bien el NIF/CIF y las direcciones.
    Solo extrae lo que se menciona en el texto."""
    
    model = GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(
        [
            system_prompt,
            text
        ],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            # Nota: Si falla response_schema con Vertex, pasarlo en el prompt. 
            # Pero en >=1.60 soporta dict de OpenAPI schema.
            response_schema=_clean_schema(ClientExtraction.model_json_schema()),
        )
    )
    
    # Devuelve como dict. El texto de la respuesta es un JSON string.
    try:
        return json.loads(response.text)
    except Exception as e:
        print("Error parsing json from Gemini: ", response.text)
        return {}

def extract_line_data(text: str, catalog_context: str = "") -> dict:
    """Extrae los conceptos y líneas de un presupuesto o factura a partir de un texto."""
    system_prompt = f"""Eres un asistente que extrae líneas de presupuestos o facturas a partir de un texto.
    Extrae cada concepto, cantidad y precio unitario que se mencione.
    Si solo se menciona un trabajo y un importe global, asume cantidad 1.
    {catalog_context}
    """
    
    model = GenerativeModel('gemini-2.5-flash')
    response = model.generate_content(
        [
            system_prompt,
            text
        ],
        generation_config=GenerationConfig(
            response_mime_type="application/json",
            response_schema=_clean_schema(QuoteExtraction.model_json_schema()),
        )
    )
    
    try:
        return json.loads(response.text)
    except Exception as e:
        print("Error parsing json from Gemini: ", response.text)
        return {}

def extract_calendar_event(text: str) -> dict:
    """Extrae los datos de un evento de calendario a partir de un texto libre (transcripción de audio).
    Razona sobre fechas relativas (mañana, el lunes, esta semana) usando la fecha de hoy como anclaje."""
    today_iso = datetime.now().strftime("%Y-%m-%d")
    day_names_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    today_weekday = day_names_es[datetime.now().weekday()]
    today_formatted = f"{today_weekday}, {datetime.now().strftime('%d/%m/%Y')}"

    system_prompt = f"""Eres un Agente de Gestión del Tiempo experto para autónomos en España.
Tu misión es extraer eventos de calendario a partir de notas de voz transcritas.

CONTEXTO TEMPORAL CRÍTICO:
- Hoy es: {today_formatted} (ISO: {today_iso})
- Si el usuario dice "mañana", calcula la fecha exacta sumando 1 día a hoy.
- Si menciona un día de la semana (ej. "el lunes"), se refiere al próximo lunes más cercano en el futuro.
- Si menciona "esta semana" sin día concreto, usa el viernes de esta semana.
- Si no menciona el año, asume el año actual a menos que la fecha ya haya pasado (usa el año siguiente).
- Si no se menciona ninguna fecha, usa la fecha de hoy ({today_iso}) y añade "Revisar fecha" en la descripción.

REGLAS DE EXTRACCIÓN:
1. TITULO: Crea un título ejecutivo conciso (máximo 5 palabras).
   Transforma lenguaje coloquial: "Tengo que ir al médico" → "Cita médica".
   "Reunión con el cliente Pepsi" → "Reunión Pepsi".
2. DESCRIPCIÓN: Incluye detalles relevantes: hora si se menciona, lugar, personas, notas importantes.
3. TIPO Y COLOR (elige uno):
   - 'fiscal' + '#e74c3c': Si menciona impuestos, IVA, IRPF, modelo 303/130/347, gestoría, hacienda, declaración.
   - 'reunion' + '#27ae60': Si menciona clientes, reunión, llamada, Zoom, Teams, visita comercial, presentación.
   - 'personal' + '#4a90e2': Citas médicas, formación, viajes, tareas personales o cualquier otro evento.
4. FECHA: Devuelve siempre en formato YYYY-MM-DD estricto.

Devuelve ÚNICAMENTE un JSON válido con los campos del esquema. Sin markdown, sin explicaciones."""

    client = get_client()
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            system_prompt,
            f"Texto de la nota de voz: {text}"
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CalendarExtraction,
        )
    )

    try:
        return json.loads(response.text)
    except Exception as e:
        print("Error parsing calendar json from Gemini: ", response.text)
        return {"titulo": "Nuevo Evento", "fecha": today_iso, "tipo": "personal", "color": "#4a90e2"}
