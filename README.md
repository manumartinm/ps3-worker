# PS3 Worker

Worker para procesar PDFs y extraer datos usando modelos de lenguaje avanzados.

## Funcionalidad

El worker recibe mensajes de la API a través de una cola AMQP y procesa los PDFs siguiendo este flujo:

1. **Recepción de Mensaje**: Recibe un mensaje con `task_id`, `filename` y `minio_path`
2. **Descarga de PDF**: Descarga el PDF desde MinIO usando la estructura de carpetas
3. **Procesamiento**: Convierte el PDF a imágenes y extrae datos usando VLLM
4. **Generación de Parquets**: Crea dos archivos parquet:
   - `odds_path_{filename}.parquet`: Datos calculados del odds path
   - `explanations_{filename}.parquet`: Explicaciones de los campos extraídos
5. **Almacenamiento**: Sube los archivos parquet a MinIO
6. **Actualización de Estado**: Actualiza el estado de la tarea en MongoDB

## Estructura de Archivos

```
ps3_worker/
├── ps3_worker/
│   ├── consumers/
│   │   └── data_consumer_in.py      # Consumer principal AMQP
│   ├── services/
│   │   ├── minio_service.py         # Servicio para MinIO
│   │   ├── mongo_service.py         # Servicio para MongoDB
│   │   └── pdf_pipeline.py          # Pipeline de procesamiento PDF
│   └── constants.py                  # Configuración
├── config.py                         # Configuración de entorno
├── env.example                       # Variables de entorno de ejemplo
└── README.md                         # Este archivo
```

## Configuración

### Variables de Entorno

Copia el archivo `env.example` a `.env` y configura:

```bash
# Configuración de MongoDB
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=ps3_webapp
MONGO_COLLECTION_TASKS=tasks

# Configuración de MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_SECURE=false
MINIO_BUCKET_PDFS=pdfs
MINIO_BUCKET_PARQUETS=parquets

# Configuración de AMQP (RabbitMQ)
AMQP_HOST=localhost
AMQP_PORT=5672
AMQP_USERNAME=guest
AMQP_PASSWORD=guest
AMQP_VIRTUAL_HOST=/
AMQP_QUEUE_PDF_PROCESSING=pdf_processing

# Claves de API para modelos de lenguaje
GOOGLE_API_KEY=your_google_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

## Instalación

1. **Instalar dependencias**:
```bash
uv sync
```

2. **Configurar variables de entorno** (ver sección anterior)

3. **Ejecutar el worker**:
```bash
python -m ps3_worker.consumers.data_consumer_in
```

## Flujo de Trabajo

### 1. Recepción de Mensaje
El worker consume mensajes de la cola `pdf_processing` con esta estructura:
```json
{
  "task_id": "abc123...",
  "filename": "document.pdf",
  "minio_path": "abc123/pdf/document.pdf",
  "timestamp": "2024-01-01T00:00:00"
}
```

### 2. Procesamiento del PDF
- Descarga el PDF desde MinIO
- Convierte a imágenes JPG
- Extrae variantes funcionales usando VLLM
- Procesa cada variante para extraer datos de investigación

### 3. Generación de Resultados
Crea dos DataFrames:
- **Odds Path**: Datos calculados del odds path calculator
- **Explicaciones**: Explicaciones detalladas de cada campo extraído

### 4. Almacenamiento
- Sube ambos archivos parquet a MinIO en la estructura:
  ```
  {task_id}/parquets/
  ├── odds_path_{filename}.parquet
  └── explanations_{filename}.parquet
  ```
- Actualiza el estado de la tarea en MongoDB

## Estados de Tarea

- **pending**: Tarea creada, esperando procesamiento
- **processing**: PDF siendo procesado
- **completed**: Procesamiento exitoso, archivos parquet disponibles
- **failed**: Error en el procesamiento

## Logs

El worker genera logs detallados para:
- Recepción de mensajes
- Descarga de archivos
- Procesamiento del PDF
- Subida de resultados
- Errores y excepciones

## Server-Sent Events (SSE)

El worker implementa Server-Sent Events para notificar en tiempo real el progreso del procesamiento de PDFs. Los eventos se envían a través del servicio SSE integrado.

### Tipos de Eventos Enviados

- **`progress`**: Progreso del procesamiento con porcentaje y etapa
- **`status`**: Cambios de estado de la tarea
- **`error`**: Errores durante el procesamiento
- **`completion`**: Tarea completada con resultados

### Etapas de Progreso

1. **`init`** (0%): Inicio del procesamiento
2. **`conversion`** (10-20%): Conversión de PDF a imágenes
3. **`extraction`** (30-40%): Extracción de variantes funcionales
4. **`processing`** (40-80%): Procesamiento de cada variante
5. **`calculation`** (80%): Cálculo del odds path
6. **`finalization`** (90%): Generación de explicaciones
7. **`completed`** (100%): Procesamiento completado

## Dependencias

- **ps3_shared**: Librerías compartidas (MinIO, MongoDB, AMQP)
- **pandas**: Manipulación de datos
- **asyncio**: Procesamiento asíncrono
- **logging**: Sistema de logs
- **SSE**: Server-Sent Events para notificaciones en tiempo real

## Monitoreo

Para monitorear el worker:
1. **Logs**: Revisar la salida de consola
2. **Cola AMQP**: Verificar mensajes en RabbitMQ
3. **MongoDB**: Consultar estado de tareas
4. **MinIO**: Verificar archivos generados

## Troubleshooting

### Error de Conexión a MinIO
- Verificar credenciales y endpoint
- Asegurar que MinIO esté ejecutándose

### Error de Conexión a MongoDB
- Verificar URI de conexión
- Asegurar que MongoDB esté ejecutándose

### Error de Conexión a AMQP
- Verificar credenciales de RabbitMQ
- Asegurar que la cola exista

### Error en Procesamiento de PDF
- Verificar claves de API de modelos de lenguaje
- Revisar logs de VLLM para errores específicos
