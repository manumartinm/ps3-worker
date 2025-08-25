import logging
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class SSEService:
    """Servicio para manejar Server-Sent Events en el worker"""
    
    def __init__(self):
        self.active_connections: Dict[str, asyncio.Queue] = {}
        self.event_history: Dict[str, list] = {}
    
    async def register_connection(self, task_id: str) -> asyncio.Queue:
        """Registrar una nueva conexión SSE para una tarea"""
        if task_id not in self.active_connections:
            self.active_connections[task_id] = asyncio.Queue()
            self.event_history[task_id] = []
            logger.info(f"Nueva conexión SSE registrada para tarea: {task_id}")
        
        return self.active_connections[task_id]
    
    async def unregister_connection(self, task_id: str):
        """Desregistrar una conexión SSE"""
        if task_id in self.active_connections:
            del self.active_connections[task_id]
            logger.info(f"Conexión SSE desregistrada para tarea: {task_id}")
    
    async def send_event(self, task_id: str, event_type: str, data: Dict[str, Any]):
        """Enviar un evento SSE a una tarea específica"""
        try:
            event = {
                "id": f"{task_id}_{int(datetime.now().timestamp())}",
                "event": event_type,
                "data": json.dumps(data),
                "timestamp": datetime.now().isoformat()
            }
            
            # Agregar a historial
            if task_id in self.event_history:
                self.event_history[task_id].append(event)
                # Mantener solo los últimos 100 eventos
                if len(self.event_history[task_id]) > 100:
                    self.event_history[task_id] = self.event_history[task_id][-100:]
            
            # Enviar a conexiones activas
            if task_id in self.active_connections:
                await self.active_connections[task_id].put(event)
                logger.debug(f"Evento SSE enviado a tarea {task_id}: {event_type}")
            
        except Exception as e:
            logger.error(f"Error enviando evento SSE a tarea {task_id}: {e}")
    
    async def send_progress_event(self, task_id: str, stage: str, progress: int, message: str, **kwargs):
        """Enviar evento de progreso"""
        data = {
            "stage": stage,
            "progress": progress,
            "message": message,
            **kwargs
        }
        await self.send_event(task_id, "progress", data)
    
    async def send_status_event(self, task_id: str, status: str, message: str, **kwargs):
        """Enviar evento de cambio de estado"""
        data = {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        await self.send_event(task_id, "status", data)
    
    async def send_error_event(self, task_id: str, error: str, details: str = None):
        """Enviar evento de error"""
        data = {
            "error": error,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_event(task_id, "error", data)
    
    async def send_completion_event(self, task_id: str, results: Dict[str, Any]):
        """Enviar evento de completado"""
        data = {
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        await self.send_event(task_id, "completion", data)
    
    def get_event_history(self, task_id: str) -> list:
        """Obtener historial de eventos de una tarea"""
        return self.event_history.get(task_id, [])
    
    async def close(self):
        """Cerrar todas las conexiones SSE"""
        try:
            for task_id in list(self.active_connections.keys()):
                await self.unregister_connection(task_id)
            logger.info("Servicio SSE cerrado")
        except Exception as e:
            logger.error(f"Error cerrando servicio SSE: {e}")


# Instancia global del servicio SSE
sse_service = SSEService() 