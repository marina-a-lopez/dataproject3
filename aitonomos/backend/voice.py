
import os
import json
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# Inicializar el cliente de Gemini
def get_client():
    return genai.Client()

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

def process_voice_to_text(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Procesa el audio y lo transcribe a texto."""
    client = get_client()
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            types.Part.from_bytes(
                data=audio_bytes,
                mime_type='audio/wav'
            ),
            "Por favor, transcribe exactamente este audio a texto."
        ]
    )
    return response.text

def extract_client_data(text: str) -> dict:
    """Extrae los datos del cliente a partir de un texto libre."""
    system_prompt = """Eres un asistente para autónomos en España.
    Tu objetivo es extraer datos de clientes a partir de un texto libre.
    Si algún dato no se menciona, déjalo como null o vacío.
    Asegúrate de formatear bien el NIF/CIF y las direcciones.
    Solo extrae lo que se menciona en el texto."""
    
    client = get_client()
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            system_prompt,
            text
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ClientExtraction,
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
    
    client = get_client()
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            system_prompt,
            text
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=QuoteExtraction,
        )
    )
    
    try:
        return json.loads(response.text)
    except Exception as e:
        print("Error parsing json from Gemini: ", response.text)
        return {}
