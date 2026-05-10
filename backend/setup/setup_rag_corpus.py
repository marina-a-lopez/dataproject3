import subprocess
import json
import urllib.request
import time

PROJECT_ID = "proyectodataia3"
LOCATION = "us-central1"

token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def api_call(method, url, body=None):
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code}:", e.read().decode())
        exit(1)

# Paso 1: Cambiar el proyecto a Serverless mode
print("⏳ Cambiando proyecto a Serverless mode...")
api_call(
    "PATCH",
    f"https://{LOCATION}-aiplatform.googleapis.com/v1beta1/projects/{PROJECT_ID}/locations/{LOCATION}/ragEngineConfig",
    {"ragManagedDbConfig": {"serverless": {}}}
)
print("✅ Serverless mode activado.")
time.sleep(5)

# Paso 2: Crear el corpus
print("⏳ Creando corpus RAG...")
result = api_call(
    "POST",
    f"https://{LOCATION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{LOCATION}/ragCorpora",
    {"display_name": "subvenciones-corpus"}
)

# La respuesta es una operación larga, el nombre del corpus está en metadata
corpus_name = result.get("metadata", {}).get("ragCorpus", {}).get("name", "") or result.get("name", "")
corpus_id = corpus_name.split("/")[-1]

print(f"\n✅ Corpus RAG creado.")
print(f"   Respuesta completa: {json.dumps(result, indent=2)}")
print(f"\n👉 Añade esto a terraform/terraform.tfvars:")
print(f'   rag_corpus_id = "{corpus_id}"')
