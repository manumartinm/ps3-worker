import os
import tempfile
import json
import logging
from typing import Any, Dict
import pandas as pd

from ps3_shared.lib.amqp import AMQPManager
from ps3_worker.constants import (
    AMQP_HOST, AMQP_PORT, AMQP_USERNAME, AMQP_PASSWORD, 
    AMQP_VIRTUAL_HOST, AMQP_QUEUE_PDF_PROCESSING
)
from ps3_worker.services.minio_service import MinioService
from ps3_worker.services.mongo_service import MongoService
from ps3_worker.services.pdf_pipeline import PDFPipeline

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Nombre de la cola a consumir
QUEUE_NAME: str = AMQP_QUEUE_PDF_PROCESSING

async def process_message(body: bytes) -> None:
    """
    Procesa un mensaje de la cola AMQP que contiene información de una tarea PDF
    """
    try:
        # Parsear el mensaje
        data: Dict[str, Any] = json.loads(body)
        task_id: str = data["task_id"]
        filename: str = data["filename"]
        minio_path: str = data["minio_path"]
        
        logger.info(f"Iniciando procesamiento de tarea: {task_id}, archivo: {filename}")
        
        # Inicializar servicios
        minio_service = MinioService()
        mongo_service = MongoService()
        pdf_pipeline = PDFPipeline()
        
        try:
            # Actualizar estado de la tarea a "processing"
            mongo_service.update_task_status(task_id, "processing")
            
            # Crear directorio temporal para el PDF
            with tempfile.TemporaryDirectory() as temp_dir:
                pdf_temp_path = os.path.join(temp_dir, filename)
                
                # Descargar PDF de MinIO
                logger.info(f"Descargando PDF de MinIO: {minio_path}")
                pdf_downloaded = minio_service.download_pdf(task_id, filename, pdf_temp_path)
                
                if not pdf_downloaded:
                    raise Exception(f"No se pudo descargar el PDF de MinIO: {minio_path}")
                
                # Crear directorio temporal para las imágenes
                images_temp_dir = os.path.join(temp_dir, "images")
                os.makedirs(images_temp_dir, exist_ok=True)
                
                # Procesar PDF con el pipeline
                logger.info(f"Procesando PDF con pipeline: {pdf_temp_path}")
                df_odds_path, df_explanations = await pdf_pipeline.extract_data_from_pdf(
                    pdf_temp_path, images_temp_dir, task_id
                )
                
                # Verificar que se obtuvieron datos
                if df_odds_path.empty and df_explanations.empty:
                    raise Exception("No se pudieron extraer datos del PDF")
                
                # Subir archivos parquet a MinIO
                parquet_paths = []
                
                if not df_odds_path.empty:
                    # Subir DataFrame de odds path
                    odds_path_filename = f"odds_path_{filename.replace('.pdf', '.parquet')}"
                    odds_path_minio_path = minio_service.upload_parquet(
                        task_id, odds_path_filename, df_odds_path, "odds_path"
                    )
                    if odds_path_minio_path:
                        parquet_paths.append(odds_path_minio_path)
                        logger.info(f"Archivo odds path subido: {odds_path_minio_path}")
                
                if not df_explanations.empty:
                    # Subir DataFrame de explicaciones
                    explanations_filename = f"explanations_{filename.replace('.pdf', '.parquet')}"
                    explanations_minio_path = minio_service.upload_parquet(
                        task_id, explanations_filename, df_explanations, "explanations"
                    )
                    if explanations_minio_path:
                        parquet_paths.append(explanations_minio_path)
                        logger.info(f"Archivo explicaciones subido: {explanations_minio_path}")
                
                # Actualizar tarea en MongoDB
                if parquet_paths:
                    # Actualizar rutas de archivos parquet
                    mongo_service.update_task_paths(
                        task_id, 
                        parquet_path=parquet_paths[0] if parquet_paths else None
                    )
                    
                    # Marcar tarea como completada
                    mongo_service.update_task_status(
                        task_id, 
                        "completed",
                        parquet_paths=parquet_paths
                    )
                    
                    logger.info(f"Tarea {task_id} completada exitosamente. Archivos parquet: {parquet_paths}")
                else:
                    raise Exception("No se pudieron subir los archivos parquet a MinIO")
                
        except Exception as e:
            logger.error(f"Error procesando tarea {task_id}: {e}")
            
            # Marcar tarea como fallida
            mongo_service.update_task_status(
                task_id, 
                "failed",
                error_message=str(e)
            )
            
            raise
            
        finally:
            # Cerrar servicios
            minio_service.close()
            mongo_service.close()
            pdf_pipeline.close()
            
    except Exception as e:
        logger.error(f"Error inesperado en process_message: {e}")


def amqp_callback(ch, method, properties, body: bytes) -> None:
    """
    Callback para procesar mensajes AMQP
    """
    try:
        logger.info(f"Mensaje recibido en {QUEUE_NAME}")
        
        # Procesar el mensaje de forma asíncrona
        import asyncio
        asyncio.run(process_message(body))
        
        # Confirmar procesamiento exitoso
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info(f"Mensaje procesado exitosamente: {method.delivery_tag}")
        
    except Exception as e:
        logger.error(f"Error en callback AMQP: {e}")
        
        # Rechazar el mensaje en caso de error
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
        logger.error(f"Mensaje rechazado: {method.delivery_tag}")


def data_consumer() -> None:
    """
    Función principal del consumer que se conecta a AMQP y espera mensajes
    """
    try:
        # Crear conexión AMQP
        amqp = AMQPManager(
            host=AMQP_HOST,
            port=AMQP_PORT,
            username=AMQP_USERNAME,
            password=AMQP_PASSWORD,
            virtual_host=AMQP_VIRTUAL_HOST
        )
        
        # Conectar y declarar cola
        amqp.connect()
        amqp.declare_queue(QUEUE_NAME)
        
        logger.info(f"Esperando mensajes en la cola '{QUEUE_NAME}'. Para salir presiona CTRL+C.")
        
        # Consumir mensajes
        amqp.consume(QUEUE_NAME, amqp_callback)
        
    except KeyboardInterrupt:
        logger.info("Interrupción recibida, cerrando consumer...")
    except Exception as e:
        logger.error(f"Error en consumer: {e}")
    finally:
        try:
            amqp.close()
            logger.info("Conexión AMQP cerrada")
        except:
            pass


if __name__ == "__main__":
    data_consumer()
