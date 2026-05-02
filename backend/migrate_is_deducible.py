import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('backend/.env')
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    print("Añadiendo columna is_deducible a tabla gastos...")
    conn.execute(text("ALTER TABLE gastos ADD COLUMN IF NOT EXISTS is_deducible BOOLEAN DEFAULT TRUE;"))
    conn.commit()
    print("¡Tabla actualizada!")
