import logging
import tempfile
import os
from typing import Optional, Any
import pandas as pd

from ps3_worker.constants import (
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_SECURE,
    MINIO_BUCKET_PDFS, MINIO_BUCKET_PARQUETS
)
from ps3_shared.lib.minio import MinioManager

logger = logging.getLogger(__name__)


class MinioService:
    """Servicio para manejar las operaciones de MinIO en el worker"""
    
    def __init__(self):
        self.minio_manager = MinioManager(
            MINIO_ENDPOINT, 
            MINIO_ACCESS_KEY, 
            MINIO_SECRET_KEY, 
            MINIO_SECURE
        )
        
        # Asegurar que los buckets existan
        self._ensure_buckets_exist()
    
    def _ensure_buckets_exist(self):
        """Asegurar que los buckets de MinIO existan"""
        try:
            self.minio_manager.make_bucket(MINIO_BUCKET_PDFS)
            self.minio_manager.make_bucket(MINIO_BUCKET_PARQUETS)
            logger.info("Buckets de MinIO verificados/creados")
        except Exception as e:
            logger.error(f"Error al crear buckets de MinIO: {e}")
    
    def download_pdf(self, task_id: str, filename: str, output_path: str) -> bool:
        """Descargar un PDF de MinIO"""
        try:
            # Estructura: {task_id}/pdfs/{filename}
            minio_object_name = f"{task_id}/pdfs/{filename}"
            
            # Descargar archivo de MinIO
            self.minio_manager.download_file(
                MINIO_BUCKET_PDFS,
                minio_object_name,
                output_path
            )
            
            logger.info(f"PDF descargado exitosamente: {minio_object_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error al descargar PDF: {e}")
            return False
    
    def upload_parquet(self, task_id: str, filename: str, df: pd.DataFrame, parquet_type: str = "data") -> Optional[str]:
        """Subir un archivo parquet a MinIO"""
        try:
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix=".parquet") as temp_file:
                temp_file_path = temp_file.name
            
            # Guardar DataFrame como parquet
            df.to_parquet(temp_file_path, index=False)
            
            # Generar nombre único para el archivo en MinIO
            # Estructura: {task_id}/parquets/{parquet_type}_{filename}
            minio_object_name = f"{task_id}/parquets/{parquet_type}_{filename}"
            
            # Subir archivo a MinIO
            self.minio_manager.upload_file(
                MINIO_BUCKET_PARQUETS,
                minio_object_name,
                temp_file_path
            )
            
            # Limpiar archivo temporal
            os.unlink(temp_file_path)
            
            logger.info(f"Parquet subido exitosamente: {minio_object_name}")
            return minio_object_name
            
        except Exception as e:
            logger.error(f"Error al subir parquet: {e}")
            return None
    
    def close(self):
        """Cerrar conexión a MinIO"""
        try:
            logger.info("Conexión a MinIO cerrada")
        except Exception as e:
            logger.error(f"Error al cerrar conexión a MinIO: {e}") 