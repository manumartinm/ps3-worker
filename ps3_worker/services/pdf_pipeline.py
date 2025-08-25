import logging
import os
import tempfile
import shutil
from typing import Tuple, Optional
import pandas as pd

from ps3_worker.services.doc_managament import DocManagament
from ps3_worker.services.odds_path_calculator import OddsPathCalculator
from ps3_worker.services.vllm_client import LLMProvider, VLLMChatClient
from ps3_worker.prompts.extract_variants_prompt import variants_prompt
from ps3_worker.prompts.first_extraction_prompt import first_extraction_prompt
from ps3_shared.entities.gene_variant import FunctionalVariants
from ps3_shared.entities.research_data import ResearchData
from ps3_worker.services.sse_service import sse_service

logger = logging.getLogger(__name__)


class PDFPipeline:
    """Pipeline para procesar PDFs y extraer datos"""
    
    def __init__(self):
        self.vllm_client = VLLMChatClient(
            provider=LLMProvider.openai, 
            model_name='gpt-5'
        )
    
    async def extract_data_from_pdf(self, pdf_path: str, output_path: str, task_id: str = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extrae datos de un PDF y retorna dos DataFrames:
        1. DataFrame con los datos de odds path calculados
        2. DataFrame con las explicaciones
        """
        try:
            logger.info(f"Iniciando procesamiento de PDF: {pdf_path}")
            
            if task_id:
                await sse_service.send_progress_event(task_id, "init", 0, "Iniciando procesamiento del PDF")
            
            # Convertir PDF a imágenes
            if task_id:
                await sse_service.send_progress_event(task_id, "conversion", 10, "Convirtiendo PDF a imágenes")
            
            conversor_pdf = DocManagament(pdf_path)
            conversor_pdf.to_jpgs(output_dir=output_path)
            
            if task_id:
                await sse_service.send_progress_event(task_id, "conversion", 20, f"PDF convertido a {conversor_pdf.n_pages} imágenes")
            
            final_data = []
            
            # Extraer DOI del nombre del archivo
            doi = pdf_path.split('/')[-1].replace("-", "/", 1).replace(".pdf", "")
            
            if task_id:
                await sse_service.send_progress_event(task_id, "extraction", 30, "Extrayendo variantes funcionales")
            
            # Extraer variantes funcionales
            variants_extraction = self.vllm_client.send_message(
                prompt_text=variants_prompt,
                image_paths=[f'{output_path}/page_{i}.jpg' for i in range(1, conversor_pdf.n_pages)],
                model=FunctionalVariants,
                retries=2
            )
            
            if len(variants_extraction.data) == 0 or len(variants_extraction.data) > 20:
                logger.warning(f"PDF {pdf_path}: No se encontraron variantes o demasiadas variantes")
                if task_id:
                    await sse_service.send_error_event(task_id, "No se encontraron variantes", f"Se encontraron {len(variants_extraction.data)} variantes")
                return pd.DataFrame(), pd.DataFrame()
            
            if task_id:
                await sse_service.send_progress_event(task_id, "extraction", 40, f"Variantes extraídas: {len(variants_extraction.data)}")
            
            # Procesar cada variante
            total_variants = len(variants_extraction.data)
            for i, variant in enumerate(variants_extraction.data):
                if task_id:
                    progress = 40 + int((i / total_variants) * 40)
                    await sse_service.send_progress_event(task_id, "processing", progress, f"Procesando variante {i+1}/{total_variants}")
                
                first_extraction = self.vllm_client.send_message(
                    prompt_text=first_extraction_prompt.format(**variant.model_dump()),
                    image_paths=[f'{output_path}/page_{i}.jpg' for i in range(1, conversor_pdf.n_pages)],
                    model=ResearchData,
                    retries=2
                )
                
                final_data.append(first_extraction.data)
            
            if task_id:
                await sse_service.send_progress_event(task_id, "calculation", 80, "Calculando odds path")
            
            # Crear DataFrame con los valores extraídos
            valid_values = []
            for doc in final_data:
                values = {
                    key: value['value'] for key, value in doc.model_dump().items()
                }
                valid_values.append(values)
            
            df_extraction = pd.DataFrame(valid_values)
            df_extraction['doi'] = doi
            
            # Calcular odds path
            calculator = OddsPathCalculator(df_extraction)
            df_odds_path = calculator.calculate()
            
            if task_id:
                await sse_service.send_progress_event(task_id, "finalization", 90, "Generando explicaciones")
            
            # Crear DataFrame con las explicaciones
            explanation_values = []
            for doc in final_data:
                explanations = {
                    key: value['explanation'] for key, value in doc.model_dump().items()
                }
                explanation_values.append(explanations)
            
            df_explanations = pd.DataFrame(explanation_values)
            df_explanations['doi'] = doi
            
            if task_id:
                await sse_service.send_progress_event(task_id, "completed", 100, "Procesamiento completado exitosamente")
                await sse_service.send_completion_event(task_id, {
                    "odds_path_records": len(df_odds_path),
                    "explanations_records": len(df_explanations),
                    "total_variants": len(variants_extraction.data)
                })
            
            logger.info(f"PDF {pdf_path} procesado exitosamente. Datos extraídos: {len(df_extraction)} registros")
            
            return df_odds_path, df_explanations
            
        except Exception as e:
            logger.error(f"Error procesando {pdf_path}: {e}")
            return pd.DataFrame(), pd.DataFrame()
        finally:
            # Limpiar directorio temporal
            try:
                if os.path.exists(output_path):
                    shutil.rmtree(output_path)
                    logger.info(f"Directorio temporal limpiado: {output_path}")
            except Exception as e:
                logger.error(f"Error al limpiar directorio temporal {output_path}: {e}")
    
    def close(self):
        """Cerrar conexiones"""
        try:
            logger.info("Pipeline cerrado")
        except Exception as e:
            logger.error(f"Error al cerrar pipeline: {e}") 