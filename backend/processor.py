
import os
import json
import ast
from datetime import datetime
import tempfile
import vertexai
from vertexai.generative_models import GenerativeModel, Part

def configure_gemini(api_key=None):
    """Configura la API de Gemini. En Cloud Run usa ADC."""
    try:
        # La inicialización principal ya ocurre en main.py
        # Pero si se llama de forma aislada, aseguramos que tenga contexto
        if not vertexai.preview.initializer._global_config.project:
            vertexai.init(
                project=os.getenv('GCP_PROJECT_ID', 'project3grupo4'),
                location=os.getenv('GCP_LOCATION', 'europe-southwest1')
            )
        return True
    except Exception as e:
        print(f"Error configuring Gemini: {e}")
        return False

def extract_invoice_data(content, mime_type="image/jpeg"):
    """
    Extrae los datos de una factura o nota de entrega a partir de un archivo JSON.
    
    Args:
        content: Contenido del archivo.
        mime_type: Tipo MIME del contenido.
        
    Devuelve:
        dict: Extrae los datos de una factura o nota de entrega a partir de un archivo JSON.
    """
    model = GenerativeModel('gemini-2.5-flash')
    
    if mime_type == "video/mp4":
        mime_type = "audio/mp4" # Fuerza el procesamiento de audio para notas de voz
        
    if mime_type.startswith("audio/") or mime_type == "audio/mp4":
        current_date = datetime.now().strftime("%Y-%m-%d")
        prompt = f"""
        You are an expert financial assistant processing a voice note for an invoice.
        TODAY'S DATE: {current_date}
        
        Crucial: Extract only the following three key details relative to the service provided:
        1. CLIENT NAME (Who is the invoice for?)
        2. ITEMS/SERVICES (What was provided? quantity? price per unit?)
        3. TOTAL AMOUNT (If manually stated, otherwise assume unit_price * quantity)
        4. DATE (If explicitly mentioned, use it. If NOT mentioned, use TODAY'S DATE: {current_date})

        Output strict JSON:
        {{
            "client_name": "Name of Client",
            "date": "YYYY-MM-DD",
            "invoice_number": "DRAFT-00X",
            "items": [
                {{
                    "description": "Clear description of service/product",
                    "quantity": number (default 1),
                    "unit_price": number,
                    "total": number
                }}
            ],
            "total_amount": number
        }}
        
        Ignore conversational filler. If the user says "factura para Pepsi", the client is Pepsi.
        """
    else:
        prompt = """
        You are an expert financial assistant. Analyze this document (invoice or delivery note).
        Extract the following information in strict JSON format:
        - invoice_number (string, if available)
        - date (string, YYYY-MM-DD)
        - client_name (string, vendor or bill to depending on context)
        - client_address (string)
        - items (list of objects with 'description', 'quantity', 'unit_price', 'total')
        - total_amount (number)
        - currency (string)
        
        If a field is missing, use null. do not include markdown code fence blocks.
        """
    
    try:
        response = model.generate_content([
            {'mime_type': mime_type, 'data': content},
            prompt
        ])
        
        # Limpia el texto de la respuesta para asegurar que sea un JSON válido
        text = response.text.strip()
        
        # Elimina los bloques de código markdown si están presentes
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].strip()
            
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Si no se puede parsear como JSON, intenta como literal
            try:
                return ast.literal_eval(text)
            except Exception:
                raise ValueError(f"No se pudo analizar la respuesta: {text[:100]}...")
                
    except Exception as e:
        return {"error": str(e)}


def extract_expense_data(file_bytes, mime_type):
    try:
        model = GenerativeModel('gemini-2.5-flash')
        
        prompt = """
        Analyze this receipt or expense document.
        Extract the following data in strict JSON format:
        {
          "proveedor": "Name of the business/vendor",
          "fecha": "Date of the expense in YYYY-MM-DD",
          "concepto": "A short 2-3 word summary of what was bought",
          "importe_total": 0.00 (the final total amount as a float)
        }
        Return ONLY the raw JSON string. Do not include markdown tags.
        """
        
        response = model.generate_content([
            Part.from_data(data=file_bytes, mime_type=mime_type),
            prompt
        ])
        # Salida del parseo
        text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)
        
    except Exception as e:
        return {"error": f"Error formateando la extracción: {str(e)}"}

def ask_ai_consultant(user_data, question):
    try:
        model = GenerativeModel('gemini-2.5-flash')
        
        cnae_code = user_data.get('cnae', 'Desconocido')
        prompt = f"""
        You are 'AItonomo', an expert financial AI consultant for a freelancer/business.
        Below is the user's financial data context extracted from their database:
        
        {json.dumps(user_data, indent=2, ensure_ascii=False)}
        
        When the user asks about their own finances, invoices, or clients, answer ONLY based on the provided data.
        However, if the user asks for advice, news, grants, or subsidies (subvenciones), you must act as a proactive advisor.
        The user's CNAE (National Classification of Economic Activities) code is: {cnae_code}.
        Utilize your knowledge to provide relevant Spanish BOE (Boletín Oficial del Estado) subsidies, grants, and news affecting this specific sector.
        Explain these legal or administrative concepts in a very simple, direct, and understandable way ("para dummies") without confusing legal jargon.
        Use professional but accessible language. Format your response in clean Markdown. Do not output generic wrappers like ```markdown.
        
        User's question: {question}
        """
        
        response = model.generate_content(prompt)
        # Limpiar bloques de codigo si los añade
        text = response.text
        if text.startswith('```markdown'):
             text = text[11:]
        if text.startswith('```'):
             text = text[3:]
        if text.endswith('```'):
             text = text[:-3]
        return {"answer": text.strip()}
    except Exception as e:
        return {"error": f"Error consulting AI: {str(e)}"}
