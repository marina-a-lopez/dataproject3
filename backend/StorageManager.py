import os
from google.cloud import storage

class StorageManager:
    def __init__(self):
        # El nombre del bucket debe coincidir con el de tu variables.tf
        self.bucket_name = os.getenv("GCP_BUCKET_NAME", "bucket-aitonomo-docs")
        self._storage_client = None

    def _get_client(self):
        """Lazy init: crea el client de GCS en la primera llamada, no en el import."""
        if self._storage_client is None:
            try:
                self._storage_client = storage.Client()
            except Exception as e:
                raise Exception(f"No se pudo inicializar Google Cloud Storage: {e}")
        return self._storage_client

    def upload_file(self, file_content, destination_blob_name):
        """Sube un archivo al bucket y devuelve la URL pública."""
        try:
            client = self._get_client()
            bucket = client.bucket(self.bucket_name)
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
            client = self._get_client()
            bucket = client.bucket(self.bucket_name)
            blob = bucket.blob(destination_blob_name)
            return blob.download_as_bytes()
        except Exception as e:
            print(f"Error al descargar de la nube: {e}")
            return None

    # ─── Path builders: estructura usuario_id/tipo/... ────────────────────

    @staticmethod
    def path_factura(user_id, cliente_id, year, codigo):
        """Ej: {user_id}/facturas/{cliente_id}/{year}/{codigo}.pdf"""
        return f"{user_id}/facturas/{cliente_id}/{year}/{codigo}.pdf"

    @staticmethod
    def path_presupuesto(user_id, cliente_id, year, codigo):
        """Ej: {user_id}/presupuestos/{cliente_id}/{year}/{codigo}.pdf"""
        return f"{user_id}/presupuestos/{cliente_id}/{year}/{codigo}.pdf"

    @staticmethod
    def path_gasto(user_id, fecha, ext):
        """Ej: {user_id}/gastos/{year}/{month}/ticket_{fecha}_{uuid}.{ext}"""
        import uuid as _uuid
        year = fecha.strftime("%Y")
        month = fecha.strftime("%m")
        return f"{user_id}/gastos/{year}/{month}/ticket_{fecha.strftime('%Y%m%d')}_{_uuid.uuid4().hex[:8]}{ext}"

    @staticmethod
    def path_avatar(user_id, filename):
        """Ej: {user_id}/avatars/{filename}"""
        return f"{user_id}/avatars/{filename}"

    def download_file_from_url(self, url_pdf):
        """Extrae el blob path de una URL pública y descarga. Fallback para paths viejos."""
        if url_pdf and self.bucket_name in url_pdf:
            blob_name = url_pdf.split(f"{self.bucket_name}/")[-1]
            return self.download_file(blob_name)
        return None