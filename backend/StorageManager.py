import os
from google.cloud import storage

class StorageManager:
    def __init__(self):
        # El nombre del bucket debe coincidir con el de tu variables.tf
        self.bucket_name = os.getenv("GCP_BUCKET_NAME", "bucket-aitonomo-docs")
        try:
            self.storage_client = storage.Client()
        except Exception as e:
            print(f"[Warning] Failed to initialize Google Cloud Storage Client: {e}")
            self.storage_client = None

    def upload_file(self, file_content, destination_blob_name):
        """Sube un archivo al bucket y devuelve la URL pública."""
        try:
            if not self.storage_client:
                raise Exception("Storage client not configured.")
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(destination_blob_name)
            
            # Subimos el contenido (bytes)
            blob.upload_from_string(file_content)
            
            # Devolvemos la URL para guardarla en PostgreSQL
            return blob.public_url
        except Exception as e:
            print(f"Error subiendo al bucket: {e}")
            return None
        
    def download_file(self, destination_blob_name):
        """Trae el archivo de la nube de vuelta a la oficina (en bytes)."""
        try:
            if not self.storage_client:
                raise Exception("Storage client not configured.")
            bucket = self.storage_client.bucket(self.bucket_name)
            blob = bucket.blob(destination_blob_name)
            return blob.download_as_bytes()
        except Exception as e:
            print(f"Error al descargar de la nube: {e}")
            return None
        
sm = StorageManager()