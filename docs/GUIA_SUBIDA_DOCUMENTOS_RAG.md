# Guía de Subida de Documentos para el Agente RAG

Para que tu agente pueda decirte si un gasto es deducible basándose en la LIRPF, LIVA y las tarifas de IAE, sigue estos pasos para subir los documentos a Google Cloud.

## 1. Localiza tu Bucket en Google Cloud
Tu infraestructura de Terraform ya ha creado un bucket para documentos. 
1. Ve a la [Consola de Google Cloud Storage](https://console.cloud.google.com/storage/browser).
2. Busca el bucket que se llama algo como `bucket-aitonomo-docs-project3grupo4`.

## 2. Prepara los Archivos (BOE)
Asegúrate de tener los archivos en formato **PDF** o **Texto plano (.txt)**. Los archivos que mencionaste son:
- `lirpf_ley_35_2006.pdf`
- `reglamento_irpf_rd_439_2007.pdf`
- `liva_ley_37_1992.pdf`
- `tarifas_iae_rdl_1175_1990.pdf`

## 3. Sube los Archivos
1. Entra en el bucket desde la consola.
2. Crea una carpeta llamada `normativas` (opcional, pero recomendado).
3. Sube los archivos directamente allí.

## 4. Ejecuta la Ingesta (RAG)
Una vez subidos, deberás ejecutar el script que estoy creando para que la IA lea esos PDFs y los guarde en la base de datos de forma que el agente pueda consultarlos.

El comando será:
```powershell
python backend/ingest_tax_docs.py
```

## 5. ¿Qué hará el Agente después?
Cuando subas un ticket, el sistema:
1. Detectará tu **IAE** (ej: 849).
2. Detectará el **Concepto** del gasto (ej: "Compra de monitor").
3. Buscará en los archivos del BOE que subiste cualquier mención a "monitor" o "equipos informáticos" para ese IAE.
4. Te dirá: *"Es deducible según el Art. X de la LIRPF que subiste"*.
