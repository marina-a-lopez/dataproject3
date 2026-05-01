
import sys
import os

# Añadir el directorio actual al path para poder importar los módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agents.user_context import get_user_context
from agents.extraction_agent import ExtractionAgent
import json

def test_context_aggregator():
    print("--- Probando User Context Aggregator (Mock) ---")
    
    # Probar con ID 1 (Diseñador)
    context_1 = get_user_context(1)
    print(f"Usuario 1: {context_1['profession']} (CNAE: {context_1['cnae_code']})")
    assert context_1['profession'] == "Diseñador Gráfico"
    
    # Probar con ID 2 (Fontanero)
    context_2 = get_user_context(2)
    print(f"Usuario 2: {context_2['profession']} (CNAE: {context_2['cnae_code']})")
    assert context_2['profession'] == "Fontanero"
    
    print("✓ Context Aggregator funcionando correctamente.\n")

def check_logic_structure():
    print("--- Comprobando Estructura del Agente de Extracción ---")
    agent = ExtractionAgent()
    
    if hasattr(agent, 'process_receipt_with_context'):
        print("✓ El método 'process_receipt_with_context' existe.")
    else:
        print("✗ El método 'process_receipt_with_context' NO existe.")

    print("\nPara una prueba real con Gemini, necesitarías ejecutar:")
    print("1. El servidor: 'uvicorn main:app --reload'")
    print("2. Una petición CURL como esta (necesitas un archivo ticket.jpg):")
    print("""
    curl -X POST "http://127.0.0.1:8000/api/v1/expenses/extract" \\
         -F "file=@ticket.jpg" \\
         -F "user_id=1"
    """)

if __name__ == "__main__":
    try:
        test_context_aggregator()
        check_logic_structure()
        print("\nPrueba de integración técnica superada.")
    except Exception as e:
        print(f"\nError durante la comprobación: {e}")
