import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv('backend/.env')
engine = create_engine(os.getenv('DATABASE_URL'))

with engine.connect() as conn:
    print("Actualizando tipos de columna en tabla gastos...")
    conn.execute(text("ALTER TABLE gastos ALTER COLUMN concepto TYPE TEXT;"))
    conn.commit()
    print("¡Columna concepto actualizada a TEXT!")
