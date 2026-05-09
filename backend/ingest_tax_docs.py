import os
import sys
import io
import uuid
import PyPDF2
from google.cloud import storage
import vertexai
from vertexai.language_models import TextEmbeddingModel
from dotenv import load_dotenv

# Ensure we can import from backend
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import SessionLocal, ReglaDeduccion, init_db

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", f"bucket-aitonomo-docs-{GCP_PROJECT_ID}")

def get_text_from_pdf(pdf_bytes):
    text = ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        print(f"Error reading PDF: {e}")
    return text

def chunk_text(text, chunk_size=1000, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def get_embedding(text: str):
    try:
        model = TextEmbeddingModel.from_pretrained("text-embedding-004")
        embeddings = model.get_embeddings([text])
        return embeddings[0].values
    except Exception as e:
        print(f"Error getting embedding: {e}")
        return None

def run_ingestion():
    # Ensure tables are created
    init_db()
    
    print(f"Starting ingestion from bucket: {GCP_BUCKET_NAME}")
    vertexai.init(project=GCP_PROJECT_ID, location="europe-southwest1")
    
    storage_client = storage.Client(project=GCP_PROJECT_ID)
    bucket = storage_client.bucket(GCP_BUCKET_NAME)
    blobs = bucket.list_blobs()
    
    db = SessionLocal()
    
    processed_count = 0
    for blob in blobs:
        if not blob.name.endswith(".pdf") and not blob.name.endswith(".txt"):
            continue
            
        print(f"Processing: {blob.name}")
        content = blob.download_as_bytes()
        
        if blob.name.endswith(".pdf"):
            text = get_text_from_pdf(content)
        else:
            text = content.decode("utf-8")
            
        if not text.strip():
            print(f"No text found in {blob.name}")
            continue
            
        # Optional: Try to identify if it targets a specific IAE by filename
        # In a real scenario, this could be extracted via LLM. Here we leave it null or extract from name.
        iae_contexto = None
        if "iae" in blob.name.lower():
            iae_contexto = "Tarifas IAE"
            
        chunks = chunk_text(text, chunk_size=1500, overlap=200)
        print(f"  -> Generated {len(chunks)} chunks.")
        
        for i, chunk in enumerate(chunks):
            print(f"    -> Embedding chunk {i+1}/{len(chunks)}...")
            vector = get_embedding(chunk)
            
            if vector:
                regla = ReglaDeduccion(
                    id=uuid.uuid4(),
                    contenido=chunk,
                    fuente=os.path.basename(blob.name),
                    iae_contexto=iae_contexto,
                    embedding=vector
                )
                db.add(regla)
        
        db.commit()
        processed_count += 1
        print(f"  -> Finished {blob.name} and saved to database.")
        
    db.close()
    print(f"\nIngestion complete. Processed {processed_count} documents.")

if __name__ == "__main__":
    run_ingestion()
