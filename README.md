# AItonomo Pro

**AItonomo Pro** es una plataforma diseñada para facilitar la administración financiera básica de trabajadores autónomos y freelancers. Ofrece una interfaz unificada para automatizar la gestión de clientes, productos, facturas (tanto de ingresos como de gastos) utilizando Inteligencia Artificial.

## ¿Qué hace la aplicación?
La solución centraliza las operaciones más comunes de un autónomo mediante las siguientes funcionalidades:
- **Dashboard Financiero**: Muestra métricas clave del negocio, como ingresos totales pagados, facturación pendiente, facturas morosas, suma de gastos y el balance neto final.
- **Gestión de Facturación Integral**: Permite crear, guardar, listar y eliminar facturas, además de permitir actualizar su estado (Pendiente, Pagada, Enviada o Moroso) en un simulador de conexión con VeriFactu.
- **CRM Integrado (Clientes y Catálogo)**: Facilita mantener un registro de clientes recurrentes y un catálogo de productos o servicios que actúan como base de memoria unificada para el usuario.
- **Procesamiento Inteligente (IA)**:
  - **Captura de tickets/gastos**: Identifica y extrae automáticamente detalles financieros de documentos.
  - **Control por Voz**: Transcribe audios proporcionados por el usuario para obtener, por ejemplo, los datos del cliente, líneas de facturación o el importe total, y luego los inyecta en la aplicación listos para enviar.
- **Generador de Facturas PDF**: Exporta las facturas a un documento PDF directamente utilizable con diseño corporativo avanzado.

## ¿Cómo lo hace?
La aplicación está construida sobre un servidor **API REST (FastAPI) alojado en Google Cloud Run** que se encarga de guardar la información operativa en una base de datos **PostgreSQL (Cloud SQL)**. Además, los datos se replican en tiempo real hacia **BigQuery** mediante **Datastream**, alimentando dashboards analíticos avanzados.

Cuando el usuario sube un archivo (como un ticket) o envía una nota de voz, FastAPI llama de forma asíncrona a un modelo de IA (Google Gemini). El sistema genera un _prompt_ contextual donde se configuran directrices estrictas para que la IA extraiga los valores de interés (como cliente, fecha, conceptos, precios e importe final) y los retorne en un formato JSON limpio y estructurado. Si el usuario ya contaba con un catálogo previo de productos, el sistema envía temporalmente el catálogo a la IA para buscar coincidencias exactas de lo dictado.

A la hora de descargar la factura, el sistema coge los detalles de la venta y dibuja paso por paso la factura en un archivo `.pdf`, que es finalmente devuelto al usuario para su uso o distribución.

## Tecnologías y Herramientas Utilizadas (y su Por Qué)

- **FastAPI**: Elegido como backend y servidor principal para la API. Destaca por su extrema velocidad y capacidad de ejecutar operaciones asíncronas de manera nativa (ideal para peticiones remotas que tardan tiempo, como la IA), además de poseer validación de datos automática desde el código.
- **SQLAlchemy**: Utilizado como ORM (Object-Relational Mapper) principal. En lugar de escribir sentencias SQL a mano (que introducen vulnerabilidades e incrementan el tiempo de desarrollo), abstrae las tablas (Factura, Gasto, Producto, Cliente) a código de Python, integrando SQLite de manera segura y confiable.
- **Google Generative AI (Gemini 2.5 Flash)**: Es el "cerebro" utilizado para el OCR avanzado y extracción de datos inteligentes. Se escogido por su velocidad y gran capacidad de procesar inputs de distinto formato (texto, audio/video e imágenes), siendo el encargado de transcribir notas de voz y recuperar los datos.
- **Pydantic**: Empleado internamente por FastAPI para el tipado fuerte y la validación automática de datos JSON que entran a la aplicación (ej. verificando que los IDs NIF/CIF o números de teléfono cumplan la expresión regular básica).
- **FPDF2**: Librería muy ligera de generación de PDFs en Python. Permite crear fácilmente el diseño prémium de las facturas (ubicando rectángulos de diseño, tipografía customizada y las filas de la venta en posiciones x-y personalizadas).
- **Werkzeug**: Una biblioteca robusta desde donde utilizamos la funcionalidad específica de encriptación y comprobación de contraseñas de los usuarios en la base de datos (seguridad), mediante el algoritmo `pbkdf2:sha256`.
