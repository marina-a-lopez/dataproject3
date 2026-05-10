import json
import os

# Define paths
cnae_mapping_path = r'c:\Users\sevil\OneDrive\Escritorio\IAP3\dataproject3\backend\utils\cnae_mapping.py'
output_sql_path = r'c:\Users\sevil\OneDrive\Escritorio\IAP3\dataproject3\backend\cnae_inserts.sql'

def generate_sql():
    # Read the mapping file
    with open(cnae_mapping_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract the dictionary part
    start_index = content.find('{')
    end_index = content.rfind('}') + 1
    dict_str = content[start_index:end_index]
    
    # Use eval to get the dict (safely since it's our own file)
    cnae_mapping = eval(dict_str)
    
    # Generate INSERT statements
    with open(output_sql_path, 'w', encoding='utf-8') as f:
        f.write("-- CNAE Mapping Data\n")
        f.write("CREATE TABLE IF NOT EXISTS cnae_mappings (\n")
        f.write("    codigo VARCHAR(10) PRIMARY KEY,\n")
        f.write("    descripcion TEXT NOT NULL\n")
        f.write(");\n\n")
        
        f.write("INSERT INTO cnae_mappings (codigo, descripcion) VALUES\n")
        
        items = list(cnae_mapping.items())
        for i, (code, desc) in enumerate(items):
            # Escape single quotes in description
            desc_escaped = desc.replace("'", "''").replace("\n", " ")
            comma = "," if i < len(items) - 1 else ";"
            f.write(f"('{code}', '{desc_escaped}'){comma}\n")
            
        f.write("\n-- Trigger function to update desc_producto\n")
        f.write("CREATE OR REPLACE FUNCTION update_user_desc_producto()\n")
        f.write("RETURNS TRIGGER AS $$\n")
        f.write("BEGIN\n")
        f.write("    IF NEW.cnae IS NOT NULL THEN\n")
        f.write("        SELECT descripcion INTO NEW.desc_producto\n")
        f.write("        FROM cnae_mappings\n")
        f.write("        WHERE codigo = NEW.cnae;\n")
        f.write("        \n")
        f.write("        -- If not found, keep old or set default\n")
        f.write("        IF NEW.desc_producto IS NULL THEN\n")
        f.write("            NEW.desc_producto = 'Producto';\n")
        f.write("        END IF;\n")
        f.write("    END IF;\n")
        f.write("    RETURN NEW;\n")
        f.write("END;\n")
        f.write("$$ LANGUAGE plpgsql;\n\n")
        
        f.write("DROP TRIGGER IF EXISTS trg_update_user_desc_producto ON usuarios;\n")
        f.write("CREATE TRIGGER trg_update_user_desc_producto\n")
        f.write("BEFORE INSERT OR UPDATE OF cnae ON usuarios\n")
        f.write("FOR EACH ROW\n")
        f.write("EXECUTE FUNCTION update_user_desc_producto();\n")

if __name__ == "__main__":
    generate_sql()
    print(f"Generated {output_sql_path}")
