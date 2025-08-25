import logging
from datetime import datetime
from typing import Optional
from ps3_worker.constants import MONGO_URI, MONGO_DB_NAME, MONGO_COLLECTION_TASKS
from ps3_shared.lib.mongo import MongoManager

logger = logging.getLogger(__name__)


class MongoService:
    """Servicio para manejar las operaciones de MongoDB en el worker"""
    
    def __init__(self):
        self.mongo_manager = MongoManager(MONGO_URI, MONGO_DB_NAME)
        self.collection = MONGO_COLLECTION_TASKS
    
    def get_task_by_id(self, task_id: str) -> Optional[dict]:
        """Obtener una tarea por su ID"""
        try:
            task_dict = self.mongo_manager.find_one(self.collection, {"id": task_id})
            if task_dict:
                logger.info(f"Tarea {task_id} obtenida exitosamente")
                return task_dict
            return None
        except Exception as e:
            logger.error(f"Error al obtener tarea {task_id}: {e}")
            return None
    
    def update_task_status(self, task_id: str, status: str, **kwargs) -> bool:
        """Actualizar el estado de una tarea"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.now(),
                **kwargs
            }
            
            if status == "processing":
                update_data["processing_started_at"] = datetime.now()
            elif status in ["completed", "failed"]:
                update_data["completed_at"] = datetime.now()
            
            modified_count = self.mongo_manager.update_one(
                self.collection, 
                {"id": task_id}, 
                update_data
            )
            
            if modified_count > 0:
                logger.info(f"Tarea {task_id} actualizada a estado: {status}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error al actualizar tarea {task_id}: {e}")
            return False
    
    def update_task_paths(self, task_id: str, minio_path: str = None, parquet_path: str = None) -> bool:
        """Actualizar las rutas de archivos de una tarea"""
        try:
            update_data = {"updated_at": datetime.now()}
            
            if minio_path:
                update_data["minio_path"] = minio_path
            if parquet_path:
                update_data["parquet_path"] = parquet_path
            
            modified_count = self.mongo_manager.update_one(
                self.collection,
                {"id": task_id},
                update_data
            )
            
            return modified_count > 0
        except Exception as e:
            logger.error(f"Error al actualizar rutas de tarea {task_id}: {e}")
            return False
    
    def close(self):
        """Cerrar conexión a MongoDB"""
        self.mongo_manager.close() 