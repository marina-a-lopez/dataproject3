
import os

def show_prompt():
    file_path = r'C:\Users\Usuario\Desktop\IAPROYECT3\dataproject3\backend\agents\extraction_agent.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        import re
        match = re.search(r'extract_prompt = """(.*?)"""', content, re.DOTALL)
        if match:
            print("-" * 50)
            print("PROMPT ACTUAL (ANTES DE OPTIMIZAR):")
            print(match.group(1).strip())
            print("-" * 50)
        else:
            print("No se encontró el prompt en el archivo.")

if __name__ == "__main__":
    show_prompt()
