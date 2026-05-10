import base64
import json
import functions_framework
import vertexai
import requests
import os
import xml.etree.ElementTree as ET
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from vertexai.generative_models import (
    GenerativeModel,
    GenerationConfig
)

# ==========================================================
# CONFIGURACIÓN
# ==========================================================

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
REGION = os.getenv("GCP_REGION", "europe-southwest1")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# ==========================================================
# INICIALIZACIÓN VERTEX AI
# ==========================================================

vertexai.init(
    project=PROJECT_ID,
    location="europe-west1"
)

# ==========================================================
# CONEXIÓN BBDD (Cloud SQL proxy via Unix socket)
# ==========================================================

def get_db_conn():
    import psycopg2
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=5432,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME
    )

# ==========================================================
# OBTENER FECHA MÁS RECIENTE EN BD
# ==========================================================

def obtener_max_fecha_publicacion():
    """Devuelve la fecha_publicacion más reciente guardada en BD, o None si la tabla está vacía."""
    conn = get_db_conn()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(fecha_publicacion) FROM subvenciones")
        result = cursor.fetchone()
        return result[0] if result and result[0] else None
    finally:
        conn.close()

# ==========================================================
# OBTENER NUEVAS SUBVENCIONES
# ==========================================================

def obtener_nuevas_subvenciones():
    """
    Recorre el RSS del BOE y devuelve subvenciones nuevas.
    Para en cuanto encuentra un item con fecha_publicacion
    anterior a (max_fecha_bd - 1 día).
    """
    url_boe = "https://www.boe.es/rss/canal.php?c=ayudas"

    max_fecha_bd = obtener_max_fecha_publicacion()
    if max_fecha_bd:
        if max_fecha_bd.tzinfo is None:
            max_fecha_bd = max_fecha_bd.replace(tzinfo=timezone.utc)
        fecha_corte = max_fecha_bd - timedelta(days=1)
        print(f"--- LOG: Fecha más reciente en BD: {max_fecha_bd.date()} | Corte: {fecha_corte.date()} ---")
    else:
        fecha_corte = None
        print("--- LOG: BD vacía, procesando todo el RSS ---")

    try:
        print("--- LOG: Consultando RSS oficial BOE ---")
        response = requests.get(url_boe, timeout=15)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        items = root.findall(".//item")
        print(f"--- LOG: Total items RSS encontrados: {len(items)} ---")

        subvenciones = []

        conn = get_db_conn()
        cursor = conn.cursor()
        try:
            for item in items:

                # ==================================================
                # DATOS RSS
                # ==================================================
                titulo = (
                    item.find("title").text
                    if item.find("title") is not None
                    else "Sin titulo"
                )
                link = (
                    item.find("link").text
                    if item.find("link") is not None
                    else ""
                )
                descripcion = (
                    item.find("description").text
                    if item.find("description") is not None
                    else ""
                )

                # ==================================================
                # PARSEAR FECHA DE PUBLICACIÓN
                # ==================================================
                pub_date_raw = (
                    item.find("pubDate").text
                    if item.find("pubDate") is not None
                    else None
                )
                fecha_publicacion = None
                if pub_date_raw:
                    try:
                        fecha_publicacion = parsedate_to_datetime(pub_date_raw)
                        if fecha_publicacion.tzinfo is None:
                            fecha_publicacion = fecha_publicacion.replace(tzinfo=timezone.utc)
                    except Exception:
                        fecha_publicacion = None

                # ==================================================
                # PARAR SI LA FECHA ES ANTERIOR AL CORTE
                # ==================================================
                if fecha_corte and fecha_publicacion and fecha_publicacion < fecha_corte:
                    print(f"--- LOG: Item del {fecha_publicacion.date()} es anterior al corte ({fecha_corte.date()}). Parando. ---")
                    break

                # ==================================================
                # EXTRAER ID BOE
                # ==================================================
                id_bdns = (
                    link.split("id=")[-1]
                    if "id=" in link
                    else titulo[:20].replace(" ", "_")
                )

                # ==================================================
                # SALTAR SI YA EXISTE EN BBDD
                # ==================================================
                cursor.execute(
                    "SELECT 1 FROM subvenciones WHERE id_bdns = %s LIMIT 1",
                    (id_bdns,)
                )
                if cursor.fetchone():
                    print(f"--- LOG: Ya existe {id_bdns}, saltando ---")
                    continue

                print(f"--- LOG: Nueva subvencion detectada {id_bdns} ---")

                # ==================================================
                # DESCARGAR TEXTO COMPLETO DEL XML
                # ==================================================
                texto_completo_boe = ""
                if id_bdns.startswith("BOE-"):
                    try:
                        res_detalle = requests.get(
                            f"https://www.boe.es/diario_boe/xml.php?id={id_bdns}",
                            timeout=10
                        )
                        if res_detalle.status_code == 200:
                            root_detalle = ET.fromstring(res_detalle.content)
                            nodo_texto = root_detalle.find(".//texto")
                            if nodo_texto is not None:
                                texto_completo_boe = "".join(nodo_texto.itertext()).strip()
                    except Exception as e:
                        print(f"Aviso: no se pudo descargar texto de {id_bdns}: {e}")

                texto_para_analizar = f"""
                TITULO: {titulo}

                DESCRIPCION Y ORGANO:
                {descripcion}

                ENLACE OFICIAL:
                {link}

                --- TEXTO COMPLETO DEL BOE ---
                {texto_completo_boe[:15000]}
                """

                subvenciones.append({
                    "id_bdns": id_bdns,
                    "fecha_publicacion": fecha_publicacion,
                    "texto_legal": texto_para_analizar.strip()
                })
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        print(f"ERROR leyendo el BOE: {str(e)}")
        return []

# ==========================================================
# CLOUD FUNCTION
# ==========================================================

@functions_framework.http
def procesar_bdns(request):

    print("--- LOG 1: Funcion iniciada ---")

    try:
        subvenciones = obtener_nuevas_subvenciones()
    except Exception as e:
        import traceback
        print(f"ERROR en obtener_nuevas_subvenciones: {e}")
        print(traceback.format_exc())
        return f"Error: {e}", 500

    if not subvenciones:
        print("--- LOG: No hay subvenciones nuevas ---")
        return "Sin datos nuevos", 200

    # ======================================================
    # MODELO IA
    # ======================================================

    model = GenerativeModel("gemini-2.5-flash")

    config_json = GenerationConfig(
        response_mime_type="application/json",
        temperature=0.1
    )

    CNAE_MAPPING = {
    "011": "Cultivos no perennes",
    "0111": "Cultivo de cereales, distintos de arroz, leguminosas y oleaginosas",
    "0112": "Cultivo de arroz",
    "0113": "Cultivo de hortalizas, raices y tuberculos",
    "0114": "Cultivo de cana de azucar",
    "0115": "Cultivo de tabaco",
    "0116": "Cultivo de plantas para fibras textiles",
    "0119": "Otros cultivos no perennes",
    "012": "Cultivos perennes",
    "0121": "Cultivo de la vid",
    "0122": "Cultivo de frutos tropicales y subtropicales",
    "0123": "Cultivo de citricos",
    "0124": "Cultivo de frutos con hueso y pepitas",
    "0125": "Cultivo de otros arboles y arbustos frutales y frutos secos",
    "0126": "Cultivo de frutos oleaginosos",
    "0127": "Cultivo de plantas para bebidas",
    "0128": "Cultivo de especias, plantas aromaticas, medicinales y farmaceuticas",
    "0129": "Otros cultivos perennes",
    "013": "Propagacion de plantas",
    "0130": "Propagacion de plantas",
    "014": "Produccion ganadera",
    "0141": "Explotacion de ganado bovino para la produccion de leche",
    "0142": "Explotacion de otro ganado bovino y bufalos",
    "0143": "Explotacion de caballos y otros equinos",
    "0144": "Explotacion de camellos y otros camelidos",
    "0145": "Explotacion de ganado ovino y caprino",
    "0146": "Explotacion de ganado porcino",
    "0147": "Avicultura",
    "0148": "Otras explotaciones de ganado",
    "015": "Produccion agricola combinada con la produccion ganadera",
    "0150": "Produccion agricola combinada con la produccion ganadera",
    "016": "Actividades de apoyo a la agricultura y ganaderia",
    "0161": "Actividades de apoyo a la agricultura",
    "0162": "Actividades de apoyo a la ganaderia",
    "0163": "Actividades de preparacion posterior a la cosecha",
    "017": "Caza, captura de animales y servicios relacionados",
    "0170": "Caza, captura de animales y servicios relacionados",
    "021": "Silvicultura y otras actividades forestales",
    "0210": "Silvicultura y otras actividades forestales",
    "022": "Explotacion de la madera",
    "0220": "Explotacion de la madera",
    "023": "Recoleccion de productos silvestres, excepto madera",
    "0230": "Recoleccion de productos silvestres, excepto madera",
    "024": "Servicios de apoyo a la silvicultura",
    "0240": "Servicios de apoyo a la silvicultura",
    "0311": "Pesca marina",
    "0312": "Pesca en agua dulce",
    "032": "Acuicultura",
    "0321": "Acuicultura marina",
    "0322": "Acuicultura en agua dulce",
    "101": "Procesado y conservacion de carne",
    "102": "Procesado y conservacion de pescados",
    "103": "Procesado y conservacion de frutas y hortalizas",
    "104": "Fabricacion de aceites y grasas",
    "105": "Fabricacion de productos lacteos",
    "106": "Fabricacion de productos de molineria",
    "107": "Fabricacion de productos de panaderia",
    "108": "Fabricacion de otros productos alimenticios",
    "109": "Fabricacion de productos para alimentacion animal",
    "110": "Fabricacion de bebidas",
    "120": "Industria del tabaco",
    "131": "Preparacion e hilado de fibras textiles",
    "132": "Fabricacion de tejidos textiles",
    "139": "Fabricacion de otros productos textiles",
    "141": "Confeccion de prendas de vestir",
    "151": "Curtido y fabricacion de articulos de cuero",
    "152": "Fabricacion de calzado",
    "161": "Aserrado y cepillado de la madera",
    "162": "Fabricacion de productos de madera y corcho",
    "171": "Fabricacion de pasta papelera y papel",
    "172": "Fabricacion de articulos de papel y carton",
    "181": "Artes graficas",
    "191": "Coquerias",
    "192": "Refino de petroleo",
    "201": "Fabricacion de productos quimicos basicos",
    "202": "Fabricacion de pesticidas y productos agroquimicos",
    "203": "Fabricacion de pinturas y barnices",
    "204": "Fabricacion de articulos de limpieza",
    "205": "Fabricacion de otros productos quimicos",
    "211": "Fabricacion de productos farmaceuticos de base",
    "212": "Fabricacion de especialidades farmaceuticas",
    "221": "Fabricacion de productos de caucho",
    "222": "Fabricacion de productos de plastico",
    "231": "Fabricacion de vidrio",
    "232": "Fabricacion de productos ceramicos refractarios",
    "233": "Fabricacion de productos ceramicos para construccion",
    "234": "Fabricacion de otros productos ceramicos",
    "235": "Fabricacion de cemento, cal y yeso",
    "236": "Fabricacion de elementos de hormigon",
    "241": "Fabricacion de productos basicos de hierro y acero",
    "242": "Fabricacion de tubos y perfiles de acero",
    "244": "Produccion de metales no ferreos",
    "251": "Fabricacion de elementos metalicos para construccion",
    "261": "Fabricacion de componentes electronicos",
    "262": "Fabricacion de ordenadores",
    "263": "Fabricacion de equipos de telecomunicaciones",
    "264": "Fabricacion de productos electronicos de consumo",
    "265": "Fabricacion de instrumentos de medida",
    "271": "Fabricacion de motores y transformadores electricos",
    "272": "Fabricacion de pilas y acumuladores",
    "273": "Fabricacion de cables",
    "274": "Fabricacion de equipos de iluminacion",
    "275": "Fabricacion de aparatos domesticos",
    "281": "Fabricacion de maquinaria de uso general",
    "282": "Fabricacion de otra maquinaria de uso general",
    "283": "Fabricacion de maquinaria agraria",
    "284": "Fabricacion de maquinaria para metales",
    "289": "Fabricacion de maquinaria para usos especificos",
    "291": "Fabricacion de vehiculos de motor",
    "292": "Fabricacion de carrocerias",
    "293": "Fabricacion de repuestos de vehiculos",
    "301": "Construccion naval",
    "302": "Fabricacion de locomotoras",
    "303": "Construccion aeronautica",
    "310": "Fabricacion de muebles",
    "321": "Fabricacion de joyeria",
    "322": "Fabricacion de instrumentos musicales",
    "323": "Fabricacion de articulos de deporte",
    "324": "Fabricacion de juegos y juguetes",
    "325": "Fabricacion de instrumentos medicos",
    "331": "Reparacion de maquinaria y equipos",
    "332": "Instalacion de maquinas industriales",
    "351": "Produccion y distribucion de energia electrica",
    "352": "Produccion de gas",
    "353": "Suministro de vapor y aire acondicionado",
    "360": "Captacion y distribucion de agua",
    "370": "Recogida y tratamiento de aguas residuales",
    "381": "Recogida de residuos",
    "382": "Valorizacion de residuos",
    "383": "Eliminacion de residuos",
    "390": "Actividades de descontaminacion",
    "410": "Construccion de edificios",
    "421": "Construccion de carreteras y vias ferreas",
    "422": "Construccion de redes",
    "429": "Construccion de otros proyectos de ingenieria civil",
    "431": "Demolicion y preparacion de terrenos",
    "432": "Instalaciones electricas y de fontaneria",
    "433": "Acabado de edificios",
    "439": "Otras actividades de construccion especializada",
    "461": "Intermediarios del comercio al por mayor",
    "462": "Comercio al por mayor de materias primas agrarias",
    "463": "Comercio al por mayor de alimentos y bebidas",
    "464": "Comercio al por mayor de articulos de uso domestico",
    "465": "Comercio al por mayor de equipos TIC",
    "466": "Comercio al por mayor de maquinaria",
    "467": "Comercio al por mayor de vehiculos",
    "468": "Otro comercio al por mayor especializado",
    "469": "Comercio al por mayor no especializado",
    "471": "Comercio al por menor no especializado",
    "472": "Comercio al por menor de alimentos",
    "473": "Comercio al por menor de combustible",
    "474": "Comercio al por menor de equipos TIC",
    "475": "Comercio al por menor de articulos de uso domestico",
    "476": "Comercio al por menor de articulos culturales",
    "477": "Comercio al por menor de otros articulos",
    "478": "Comercio al por menor de vehiculos",
    "491": "Transporte de pasajeros por ferrocarril",
    "492": "Transporte de mercancias por ferrocarril",
    "493": "Otro transporte terrestre de pasajeros",
    "494": "Transporte de mercancias por carretera",
    "495": "Transporte por tuberia",
    "501": "Transporte maritimo de pasajeros",
    "502": "Transporte maritimo de mercancias",
    "511": "Transporte aereo de pasajeros",
    "512": "Transporte aereo de mercancias",
    "521": "Deposito y almacenamiento",
    "522": "Actividades auxiliares del transporte",
    "531": "Actividades postales",
    "532": "Otras actividades postales y mensajeria",
    "551": "Hoteles y alojamientos similares",
    "552": "Alojamientos turisticos",
    "553": "Campings",
    "559": "Otros servicios de alojamiento",
    "561": "Restaurantes y puestos de comidas",
    "562": "Servicios de catering",
    "563": "Servicios de bebidas",
    "581": "Edicion de libros y periodicos",
    "582": "Edicion de programas informaticos",
    "591": "Actividades cinematograficas y de video",
    "592": "Actividades de grabacion de sonido",
    "601": "Actividades de radiodifusion",
    "602": "Actividades de television",
    "611": "Actividades de telecomunicaciones",
    "619": "Otras actividades de telecomunicaciones",
    "621": "Actividades de programacion informatica",
    "622": "Actividades de consultoria informatica",
    "629": "Otros servicios TIC",
    "631": "Infraestructura informatica y hosting",
    "639": "Otros servicios de informacion",
    "641": "Intermediacion monetaria",
    "649": "Otros servicios financieros",
    "651": "Seguros",
    "652": "Reaseguros",
    "653": "Fondos de pensiones",
    "661": "Actividades auxiliares a servicios financieros",
    "662": "Actividades auxiliares a seguros",
    "663": "Actividades de gestion de fondos",
    "681": "Actividades inmobiliarias por cuenta propia",
    "682": "Alquiler de bienes inmobiliarios",
    "683": "Actividades inmobiliarias por cuenta de terceros",
    "691": "Actividades juridicas",
    "692": "Actividades de contabilidad y auditoria",
    "701": "Actividades de sedes centrales",
    "702": "Consultoria de gestion empresarial",
    "711": "Servicios tecnicos de arquitectura e ingenieria",
    "712": "Ensayos y analisis tecnicos",
    "721": "Investigacion y desarrollo en ciencias naturales",
    "722": "Investigacion y desarrollo en ciencias sociales",
    "731": "Publicidad",
    "732": "Estudios de mercado",
    "733": "Relaciones publicas",
    "741": "Actividades de diseno especializado",
    "742": "Actividades de fotografia",
    "743": "Actividades de traduccion",
    "749": "Otras actividades profesionales y tecnicas",
    "750": "Actividades veterinarias",
    "771": "Alquiler de vehiculos",
    "772": "Alquiler de efectos personales",
    "773": "Alquiler de maquinaria",
    "781": "Actividades de agencias de colocacion",
    "782": "Empresas de trabajo temporal",
    "791": "Agencias de viajes y operadores turisticos",
    "800": "Servicios de investigacion y seguridad",
    "811": "Servicios integrales a edificios",
    "812": "Actividades de limpieza",
    "813": "Actividades de jardineria",
    "821": "Actividades administrativas de oficina",
    "822": "Actividades de centros de llamadas",
    "823": "Organizacion de convenciones y ferias",
    "829": "Otras actividades de apoyo a empresas",
    "841": "Administracion publica",
    "851": "Educacion preprimaria",
    "852": "Educacion primaria",
    "853": "Educacion secundaria",
    "854": "Educacion terciaria",
    "855": "Otra educacion",
    "856": "Actividades auxiliares a la educacion",
    "861": "Actividades hospitalarias",
    "862": "Actividades medicas y odontologicas",
    "869": "Otras actividades sanitarias",
    "871": "Asistencia residencial con cuidados sanitarios",
    "872": "Asistencia residencial para salud mental",
    "873": "Asistencia residencial para personas mayores",
    "879": "Otras actividades de asistencia residencial",
    "881": "Servicios sociales sin alojamiento",
    "889": "Otras actividades de servicios sociales",
    "901": "Actividades de creacion artistica",
    "902": "Actividades de artes escenicas",
    "903": "Actividades de apoyo a las artes",
    "911": "Actividades de bibliotecas y archivos",
    "912": "Actividades de museos y sitios historicos",
    "913": "Conservacion del patrimonio cultural",
    "914": "Jardines botanicos y parques zoologicos",
    "920": "Actividades de juegos de azar",
    "931": "Actividades deportivas",
    "932": "Otras actividades recreativas",
    "941": "Organizaciones empresariales y profesionales",
    "942": "Actividades sindicales",
    "949": "Otras actividades asociativas",
    "951": "Reparacion de ordenadores y equipos de comunicacion",
    "952": "Reparacion de efectos personales y articulos domesticos",
    "953": "Reparacion de vehiculos",
    "961": "Lavado y limpieza de prendas",
    "962": "Peluqueria y tratamientos de belleza",
    "963": "Pompas funebres",
    "969": "Otros servicios personales",
    "970": "Hogares como empleadores de personal domestico"
    }

    # ======================================================
    # PROCESAR SUBVENCIONES
    # ======================================================

    for sub in subvenciones:

        print(f"--- LOG 2: Procesando {sub['id_bdns']} ---")

        texto = sub["texto_legal"]

        prompt = f"""
        Eres un analista experto en subvenciones publicas en Espana para una plataforma de autonomos.
        
        A continuacion tienes el MAPPING OFICIAL DE CNAE:
        {json.dumps(CNAE_MAPPING, ensure_ascii=False)}

        DEVUELVE UNICAMENTE un JSON valido (sin texto adicional).

        Formato exacto de salida:
        {{
            "titulo": string,
            "cnae_target": string,
            "apto_autonomos": boolean,
            "motivo_autonomos": string,
            "fecha_cierre": string|null
        }}

        REGLAS:
        1. "titulo": Titulo oficial, maximo 150 caracteres.
        
        2. "cnae_target": 
           - Si la ayuda sirve para cualquier negocio (digitalizacion, cuota de autonomos, eficiencia energetica general), devuelve "".
           - Si es de un sector concreto, devuelve los codigos del MAPPING separados por comas.
           
        3. "apto_autonomos": (PIENSA EN UN AUTONOMO DE A PIE)
           - true SOLO SI menciona expresamente "autonomos", "RETA", "personas fisicas con actividad economica" o "micropymes".
           - false OBLIGATORIAMENTE si:
             * Proyectos de gran envergadura o infraestructuras publicas.
             * Dirigidas a Ayuntamientos, Diputaciones, Universidades, ONG, Asociaciones, Fundaciones.
             * Exige forma juridica (S.L., S.A., Cooperativas).
             * Ayudas al cine o producciones audiovisuales masivas.
             * "Empresas" pero un autonomo individual no tiene capacidad real para el proyecto.
           - Ante la duda de que un autonomo NO sea el publico objetivo, devuelve false.
           
        4. "motivo_autonomos": Explica brevemente a quien va dirigida o por que un autonomo no puede pedirla.
        
        5. "fecha_cierre": Busca el plazo. Si dice "15 dias desde la publicacion", calculalo en formato YYYY-MM-DD. Si no hay forma de saberlo, pon null.

        Texto a analizar:
        {texto}
        """

        max_reintentos = 3
        retraso_base = 5

        for intento in range(max_reintentos):
            try:
                respuesta = model.generate_content(
                    prompt,
                    generation_config=config_json
                )

                datos_ia = json.loads(respuesta.text)

                # ==================================================
                # SANITIZACIÓN DEL BOOLEANO
                # ==================================================
                apto_raw = datos_ia.get("apto_autonomos", False)
                apto_autonomos = str(apto_raw).lower().strip() == "true"
                motivo = datos_ia.get("motivo_autonomos", "Sin motivo especificado")

                # ==================================================
                # NORMALIZAR CNAE: padding con ceros hasta 4 cifras
                # ==================================================
                cnae_raw = datos_ia.get("cnae_target", "") or ""
                cnae_normalizado = ",".join(
                    c.strip().zfill(4) for c in cnae_raw.split(",") if c.strip()
                )

                # ==================================================
                # INSERTAR EN BBDD (SIEMPRE, independiente de apto_autonomos)
                # ==================================================
                fecha_pub_str = (
                    sub["fecha_publicacion"].strftime("%Y-%m-%d")
                    if sub["fecha_publicacion"]
                    else None
                )

                with get_db_conn() as db_conn:
                    cursor = db_conn.cursor()
                    cursor.execute("""
                        INSERT INTO subvenciones (
                            id_bdns,
                            titulo,
                            cnae_target,
                            apto_autonomos,
                            fecha_publicacion,
                            fecha_cierre,
                            texto_completo
                        )
                        VALUES (%s, %s, %s, %s, %s::date, %s::date, %s)
                        ON CONFLICT (id_bdns) DO NOTHING;
                    """, (
                        sub["id_bdns"],
                        datos_ia.get("titulo", "Subvencion sin titulo"),
                        cnae_normalizado,
                        apto_autonomos,
                        fecha_pub_str,
                        datos_ia.get("fecha_cierre"),
                        datos_ia.get("motivo_autonomos", "") + "\n\n" + texto
                    ))
                    db_conn.commit()

                estado = "APTA" if apto_autonomos else "NO APTA"
                print(f"GUARDADA [{estado}]: {sub['id_bdns']} | {fecha_pub_str} | CNAE: '{cnae_normalizado}'")

                time.sleep(3)
                break

            except Exception as error:
                if "429" in str(error) and intento < max_reintentos - 1:
                    espera = retraso_base * (intento + 1)
                    print(f"Limite de API (429). Reintentando en {espera}s...")
                    time.sleep(espera)
                else:
                    print(f"ERROR definitivo procesando {sub['id_bdns']}: {str(error)}")
                    time.sleep(3)
                    break

    return "Ejecucion finalizada", 200
