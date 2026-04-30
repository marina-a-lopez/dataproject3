"""
Pipeline: Dataflow Streaming — Extracción y confirmación de gastos

Dos topics, dos ramas independientes:

  topic-tickets      → Gemini extrae datos → Firestore (status: done) → FCM al usuario
  topic-confirmaciones → INSERT en PostgreSQL (Datastream replica a BigQuery)
"""
import argparse
import json
import logging
import random
import time

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, SetupOptions
from google.cloud import firestore, storage
from firebase_admin import messaging
import firebase_admin
import psycopg2
import google.generativeai as genai

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

SCHEMA_GASTO = {
    "type": "object",
    "properties": {
        "proveedor":     {"type": "string"},
        "fecha":         {"type": "string", "description": "Formato YYYY-MM-DD"},
        "concepto":      {"type": "string"},
        "importe_total": {"type": "number"},
    },
    "required": ["proveedor", "fecha", "concepto", "importe_total"],
}

ETIQUETA_ERRORES = "errores"

# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def reintentos(fn, max_intentos: int = 4, espera_base: float = 2.0):
    """Backoff exponencial ante errores transitorios de la API."""
    for intento in range(max_intentos):
        try:
            return fn()
        except Exception as e:
            es_transitorio = any(t in str(e).lower() for t in ("429", "quota", "resource exhausted", "unavailable"))
            if es_transitorio and intento < max_intentos - 1:
                espera = espera_base * (2 ** intento) + random.uniform(0, 1)
                logging.warning("[Reintentos] %s — esperando %.1fs (intento %d/%d)", e, espera, intento + 1, max_intentos)
                time.sleep(espera)
            else:
                raise


def parsear_mensaje(message: bytes):
    try:
        yield json.loads(message.decode("utf-8"))
    except Exception as e:
        logging.error("[PubSub] Error al parsear mensaje: %s", e)

# ---------------------------------------------------------------------------
# DoFns — rama topic-tickets
# ---------------------------------------------------------------------------

class ExtraerConGemini(beam.DoFn):
    """Llama a Gemini con el ticket en GCS y devuelve los datos extraídos."""

    def __init__(self, project_id: str, region: str = "europe-west1", gemini_api_key: str = ""):
        self.project_id = project_id
        self.region = region
        self.gemini_api_key = gemini_api_key

    def setup(self):
        genai.configure(api_key=self.gemini_api_key)
        self.model = genai.GenerativeModel(model_name="gemini-2.5-flash")
        self.storage_client = storage.Client(project=self.project_id)
        logging.info("[Gemini] Worker inicializado")

    def process(self, element: dict):
        job_id = element.get("job_id", "desconocido")
        try:
            # Descargar imagen desde GCS
            bucket = self.storage_client.bucket(element["bucket_name"])
            blob = bucket.blob(element["object_name"])
            image_bytes = blob.download_as_bytes()

            prompt = (
                "Extrae del siguiente recibo: proveedor, fecha (formato YYYY-MM-DD), concepto e importe_total. "
                "Responde ÚNICAMENTE con un JSON con las claves: proveedor, fecha, concepto, importe_total."
            )
            response = reintentos(lambda: self.model.generate_content([
                {"mime_type": element["mime_type"], "data": image_bytes},
                prompt,
            ]))

            # Limpiar posible markdown del JSON
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            datos = json.loads(text.strip())
            yield {**element, "datos_extraidos": datos, "status": "done"}

        except Exception as e:
            logging.error("[Gemini] Error en job_id=%s: %s", job_id, e)
            yield beam.pvalue.TaggedOutput(
                ETIQUETA_ERRORES,
                {**element, "status": "error", "error_detail": str(e)},
            )


class ActualizarFirestore(beam.DoFn):
    """Escribe el resultado (éxito o error) en Firestore."""

    def __init__(self, project_id: str):
        self.project_id = project_id

    def setup(self):
        self.db = firestore.Client(project=self.project_id)

    def process(self, element: dict):
        job_id = element.get("job_id", "desconocido")
        status = element.get("status", "error")

        payload = {"status": status, "user_id": element.get("user_id")}
        if status == "done":
            payload["data"] = element.get("datos_extraidos", {})
        else:
            payload["error_detail"] = element.get("error_detail", "")

        self.db.collection("expense_extractions").document(job_id).set(payload, merge=True)
        logging.info("[Firestore] job_id=%s → status=%s", job_id, status)
        yield element


class EnviarFCM(beam.DoFn):
    """Push notification al usuario para que revise y confirme el ticket."""

    def setup(self):
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app()

    def process(self, element: dict):
        fcm_token = element.get("fcm_token")
        if not fcm_token:
            yield element
            return

        datos = element.get("datos_extraidos", {})
        try:
            messaging.send(messaging.Message(
                notification=messaging.Notification(
                    title="¡Ticket procesado!",
                    body=f"{datos.get('importe_total', 0)}€ en {datos.get('proveedor', 'tu recibo')}. Revisa y confirma.",
                ),
                data={"job_id": element.get("job_id", ""), "action": "REVIEW_TICKET"},
                token=fcm_token,
            ))
            logging.info("[FCM] Notificación enviada — user_id=%s", element.get("user_id"))
        except Exception as e:
            logging.warning("[FCM] Error al enviar notificación: %s", e)

        yield element

# ---------------------------------------------------------------------------
# DoFn — rama topic-confirmaciones
# ---------------------------------------------------------------------------

class GuardarEnPostgres(beam.DoFn):
    """
    INSERT en la tabla gastos de PostgreSQL.
    Solo se ejecuta cuando el usuario confirma desde la app.
    Datastream replica automáticamente los cambios a BigQuery.
    """

    def __init__(self, db_host: str, db_name: str, db_user: str, db_pass: str, project_id: str):
        self.db_host = db_host
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass
        self.project_id = project_id

    def setup(self):
        self.conn = psycopg2.connect(
            host=self.db_host, database=self.db_name,
            user=self.db_user, password=self.db_pass,
        )
        logging.info("[Postgres] Conexión establecida")

    def process(self, element: dict):
        datos = element.get("datos_extraidos", {})
        url_ticket = f"gs://{element.get('bucket_name', '')}/{element.get('object_name', '')}"
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO gastos (id, usuario_id, fecha, proveedor, concepto, importe_total, url_ticket, created_at)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    element["user_id"],
                    datos.get("fecha"),
                    datos.get("proveedor"),
                    datos.get("concepto"),
                    datos.get("importe_total"),
                    url_ticket,
                ),
            )
            self.conn.commit()
            cursor.close()
            logging.info("[Postgres] Gasto insertado — user_id=%s | proveedor=%s", element.get("user_id"), datos.get("proveedor"))

            # Marcar job como confirmado en Firestore
            job_id = element.get("job_id")
            if job_id:
                firestore.Client(project=self.project_id).collection(
                    "expense_extractions"
                ).document(job_id).set({"status": "confirmed"}, merge=True)

        except Exception as e:
            self.conn.rollback()
            logging.error("[Postgres] Error al insertar gasto: %s", e)

        yield element

    def teardown(self):
        if hasattr(self, "conn") and self.conn:
            self.conn.close()

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id", required=True)
    parser.add_argument("--db_host",    required=True)
    parser.add_argument("--db_name",    required=True)
    parser.add_argument("--db_user",    required=True)
    parser.add_argument("--db_pass",    required=True)
    parser.add_argument("--region",     default="europe-west1")
    parser.add_argument("--gemini_api_key", required=True)
    args, pipeline_args = parser.parse_known_args()

    options = PipelineOptions(pipeline_args, project=args.project_id)
    options.view_as(StandardOptions).streaming = True
    options.view_as(SetupOptions).save_main_session = True

    sub_tickets = f"projects/{args.project_id}/subscriptions/sub-tickets"
    sub_confirmaciones = f"projects/{args.project_id}/subscriptions/sub-confirmaciones"

    with beam.Pipeline(options=options) as p:

        # ── Rama 1: topic-tickets → Gemini → Firestore → FCM ──────────────
        mensajes_tickets = (
            p
            | "LeerTickets"         >> beam.io.ReadFromPubSub(subscription=sub_tickets)
            | "ParsearTicket"        >> beam.FlatMap(parsear_mensaje).with_output_types(dict)
        )

        resultado = (
            mensajes_tickets
            | "ExtraerConGemini" >> beam.ParDo(ExtraerConGemini(args.project_id, args.region, args.gemini_api_key))
                                        .with_outputs(ETIQUETA_ERRORES, main="ok")
        )

        _ = (
            resultado.ok
            | "ActualizarFirestore_OK" >> beam.ParDo(ActualizarFirestore(args.project_id))
            | "EnviarFCM"              >> beam.ParDo(EnviarFCM())
        )

        _ = (
            resultado[ETIQUETA_ERRORES]
            | "ActualizarFirestore_Error" >> beam.ParDo(ActualizarFirestore(args.project_id))
        )

        # ── Rama 2: topic-confirmaciones → INSERT en PostgreSQL ────────────
        _ = (
            p
            | "LeerConfirmaciones"         >> beam.io.ReadFromPubSub(subscription=sub_confirmaciones)
            | "ParsearConfirmacion"         >> beam.FlatMap(parsear_mensaje).with_output_types(dict)
            | "GuardarEnPostgres"           >> beam.ParDo(
                GuardarEnPostgres(args.db_host, args.db_name, args.db_user, args.db_pass, args.project_id)
            )
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("apache_beam.utils.subprocess_server").setLevel(logging.ERROR)
    logging.info("[Pipeline] Iniciando pipeline de extracción de gastos")
    run()


# python pipeline_gastos.py \
#   --project_id proyectodataia3 \
#   --db_host 34.175.105.251 \
#   --db_name aitonomo_db \
#   --db_user admin \
#   --db_pass "Edem2526." \
#   --region europe-southwest1 \
#   --gemini_api_key "AIzaSyDhNVU8VBbwkcHmLxbpoyYMyr_Ky6nlrl8" \
#   --runner DirectRunner