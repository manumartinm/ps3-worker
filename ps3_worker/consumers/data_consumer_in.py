import os
import re
import hashlib
import json
from typing import Any, Dict
import pandas as pd

from ps3_shared.entities.gene_variant import FunctionalVariants
from ps3_shared.entities.research_data import ResearchArticle
from ps3_shared.lib.amqp import AMQPManager

from ps3_worker.prompts.first_extraction_prompt import first_extraction_prompt
from ps3_worker.services.doc_managament import DocManagament
from ps3_worker.services.odds_path_calculator import OddsPathCalculator
from ps3_worker.services.vllm_client import LLMProvider, VLLMChatClient

# Configuración de conexión AMQP
AMQP_URL: str = os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/")
QUEUE_NAME: str = "ps3:data:In"


def generate_secure_random_hash(length: int = 32) -> str:
    random_bytes: bytes = os.urandom(32)
    sha256_hash: str = hashlib.sha256(random_bytes).hexdigest()
    return sha256_hash[:length]


def process_message(body: bytes) -> None:
    try:
        data: Dict[str, Any] = json.loads(body)
        pdf_base64: str = data["pdf_base64"]
        temporal_hash_name: str = f"temp_{generate_secure_random_hash(8)}.pdf"
        conversor_pdf: DocManagament = DocManagament(pdf_base64, temporal_hash_name)

        conversor_pdf.to_jpgs()
        final_data: list = []
        vllm_chat_client: VLLMChatClient = VLLMChatClient(
            "gemini-2.5-pro", LLMProvider.gemini
        )

        variants_extraction_mocked: Dict[str, Any] = {
            "data": [
                {"gene": "FLNC", "variant": "p.V123A"},
                {"gene": "FLNC", "variant": "p.A1539T"},
                {"gene": "FLNC", "variant": "p.R2133H"},
                {"gene": "FLNC", "variant": "p.A2430V"},
            ]
        }
        variants_extraction: FunctionalVariants = FunctionalVariants.model_validate(
            variants_extraction_mocked
        )

        for variant in variants_extraction.data[:1]:
            first_extraction: ResearchArticle = vllm_chat_client.send_message(
                prompt_text=first_extraction_prompt.format(**variant.model_dump()),
                image_paths=[
                    os.path.join(conversor_pdf.data_dir, f"page_{i}.jpg")
                    for i in range(1, conversor_pdf.n_pages)
                ],
                model=ResearchArticle,
                retries=3,
            )
            final_data.append(first_extraction)

        final_data = [first_extraction.model_dump() for first_extraction in final_data]
        valid_values: list = []
        for doc in final_data:
            values: Dict[str, Any] = {key: value["value"] for key, value in doc.items()}
            valid_values.append(values)

        df_extraction: pd.DataFrame = pd.DataFrame(valid_values)
        calculator: OddsPathCalculator = OddsPathCalculator(df_extraction)
        df_odds_path: pd.DataFrame = calculator.calculate()

        response: Dict[str, Any] = {
            "extracted_data": final_data,
            "odds_path_data": df_odds_path.to_dict(orient="records"),
        }
        print("[INFO] Proceso completado. Respuesta:", json.dumps(response, indent=2))
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        if "conversor_pdf" in locals():
            conversor_pdf.remove_data_dir()


def amqp_callback(ch, method, properties, body: bytes) -> None:
    print(f"[INFO] Mensaje recibido en {QUEUE_NAME}")
    process_message(body)
    ch.basic_ack(delivery_tag=method.delivery_tag)


def data_consumer() -> None:
    match = re.match(r"amqp://(.*?):(.*?)@(.*?):(\d+)(/.*)?", AMQP_URL)
    if not match:
        raise ValueError("AMQP_URL mal formado")
    username, password, host, port, _ = match.groups()
    port = int(port)
    amqp = AMQPManager(host=host, port=port, username=username, password=password)
    amqp.declare_queue(QUEUE_NAME)
    print(
        f"[INFO] Esperando mensajes en la cola '{QUEUE_NAME}'. Para salir presiona CTRL+C."
    )
    amqp.consume(QUEUE_NAME, amqp_callback)
