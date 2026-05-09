"""
Pipeline: Dataflow Streaming — Extracción de gastos 
"""
import argparse
import json
import logging
import random
import time

import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, StandardOptions, SetupOptions
from google.cloud import storage
import psycopg2
import vertexai
from vertexai.generative_models import GenerativeModel, Part

ETIQUETA_ERRORES = "errores"


def reintentos(fn, max_intentos: int = 4, espera_base: float = 2.0):
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


class ExtraerConGemini(beam.DoFn):
    """Descarga el ticket de GCS, llama a Gemini y devuelve los datos extraídos."""

    def __init__(self, project_id: str):
        self.project_id = project_id

    def setup(self):
        vertexai.init(project=self.project_id)
        self.model = GenerativeModel(model_name="gemini-2.5-flash")
        self.storage_client = storage.Client(project=self.project_id)
        logging.info("[Vertex] Worker inicializado")

    def process(self, element: dict):
        expense_id = element.get("expense_id", "desconocido")
        try:
            bucket = self.storage_client.bucket(element["bucket_name"])
            blob = bucket.blob(element["object_name"])
            image_bytes = blob.download_as_bytes()

            prompt = (
                "Extrae del siguiente recibo: proveedor, fecha (formato DD-MM-YYYY), concepto e importe_total. "
                "Responde ÚNICAMENTE con un JSON con las claves: proveedor, fecha, concepto, importe_total."
            )
            response = reintentos(lambda: self.model.generate_content([
                Part.from_data(data=image_bytes, mime_type=element["mime_type"]),
                prompt,
            ]))

            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            datos = json.loads(text.strip())
            yield {**element, "datos_extraidos": datos, "status": "done"}

        except Exception as e:
            logging.error("[Gemini] Error en expense_id=%s: %s", expense_id, e)
            yield beam.pvalue.TaggedOutput(
                ETIQUETA_ERRORES,
                {**element, "status": "error", "error_detail": str(e)},
            )


class ActualizarPostgres(beam.DoFn):
    """UPDATE del draft en PostgreSQL con los datos extraídos por Gemini."""

    def __init__(self, db_host: str, db_name: str, db_user: str, db_pass: str):
        self.db_host = db_host
        self.db_name = db_name
        self.db_user = db_user
        self.db_pass = db_pass

    def setup(self):
        self.conn = psycopg2.connect(
            host=self.db_host, database=self.db_name,
            user=self.db_user, password=self.db_pass,
        )
        logging.info("[Postgres] Conexión establecida")

    def process(self, element: dict):
        expense_id = element.get("expense_id")
        status = element.get("status", "error")
        datos = element.get("datos_extraidos", {})

        try:
            cursor = self.conn.cursor()
            if status == "done" and expense_id:
                cursor.execute(
                    """
                    UPDATE gastos SET proveedor=%s, fecha=%s, concepto=%s, importe_total=%s
                    WHERE id=%s
                    """,
                    (
                        datos.get("proveedor"),
                        datos.get("fecha"),
                        datos.get("concepto"),
                        datos.get("importe_total"),
                        expense_id,
                    ),
                )
                logging.info("[Postgres] Draft actualizado — expense_id=%s | proveedor=%s", expense_id, datos.get("proveedor"))
            elif status == "error" and expense_id:
                # Marcar como error para que el frontend lo detecte
                cursor.execute("UPDATE gastos SET concepto=%s WHERE id=%s", (f"ERROR: {element.get('error_detail', '')[:200]}", expense_id))
            self.conn.commit()
            cursor.close()
        except Exception as e:
            self.conn.rollback()
            logging.error("[Postgres] Error al actualizar draft: %s", e)

        yield element

    def teardown(self):
        if hasattr(self, "conn") and self.conn:
            self.conn.close()


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project_id",     required=True)
    parser.add_argument("--db_host",        required=True)
    parser.add_argument("--db_name",        required=True)
    parser.add_argument("--db_user",        required=True)
    parser.add_argument("--db_pass",        required=True)
    args, pipeline_args = parser.parse_known_args()

    options = PipelineOptions(pipeline_args, project=args.project_id)
    options.view_as(StandardOptions).streaming = True
    options.view_as(SetupOptions).save_main_session = True

    sub_tickets = f"projects/{args.project_id}/subscriptions/sub-tickets"

    with beam.Pipeline(options=options) as p:
        mensajes = (
            p
            | "LeerTickets"  >> beam.io.ReadFromPubSub(subscription=sub_tickets)
            | "Parsear"      >> beam.FlatMap(parsear_mensaje).with_output_types(dict)
        )

        resultado = (
            mensajes
            | "ExtraerConGemini" >> beam.ParDo(ExtraerConGemini(args.project_id))
                                        .with_outputs(ETIQUETA_ERRORES, main="ok")
        )

        _ = (
            resultado.ok
            | "ActualizarPostgres_OK" >> beam.ParDo(ActualizarPostgres(args.db_host, args.db_name, args.db_user, args.db_pass))
        )

        _ = (
            resultado[ETIQUETA_ERRORES]
            | "ActualizarPostgres_Error" >> beam.ParDo(ActualizarPostgres(args.db_host, args.db_name, args.db_user, args.db_pass))
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("apache_beam.utils.subprocess_server").setLevel(logging.ERROR)
    logging.info("[Pipeline] Iniciando pipeline de extracción de gastos")
    run()

# local:
# python pipeline_gastos.py \
#   --project_id proyectodataia3 \
#   --db_host 34.175.105.251 \
#   --db_name aitonomo_db \
#   --db_user admin \
#   --db_pass "Edem2526." \
#   --region europe-southwest1 \
#   --gemini_api_key "TU_API_KEY" \
#   --runner DirectRunner
