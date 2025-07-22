from typing import Optional, List, Any, Type, Dict
from pydantic import BaseModel
import google.generativeai as genai
from ollama import chat
from backend.constants import GOOGLE_API_KEY
import os
import time
import json
from enum import Enum

genai.configure(api_key=GOOGLE_API_KEY)

class LLMProvider(Enum):
    gemini = "gemini"
    ollama = "ollama"

class BaseChatClient:
    def send_message_once(
        self,
        prompt_text: str,
        image_paths: Optional[List[str]] = None,
        model: Optional[Type[BaseModel]] = None
    ) -> str:
        raise NotImplementedError

class GeminiChatClient(BaseChatClient):
    def __init__(self, model_name: str = "gemini-2.5-pro"):
        self.model_name = model_name

    def send_message_once(
        self,
        prompt_text: str,
        image_paths: Optional[List[str]] = None,
        model: Optional[Type[BaseModel]] = None
    ) -> Any:
        generative_model = genai.GenerativeModel(self.model_name)
        generation_config = {
            "temperature": 0.4,
            "max_output_tokens": 10000,
        }
        if model:
            generation_config["response_mime_type"] = "application/json"
            generation_config["response_schema"] = model

        if image_paths:
            image_parts = [self._load_image_as_part(path) for path in image_paths if os.path.exists(path)]
            response = generative_model.generate_content(
                [prompt_text] + image_parts,
                generation_config=generation_config,
            )
        else:
            response = generative_model.generate_content(
                [prompt_text],
                generation_config=generation_config,
            )
        return response.text

    def _load_image_as_part(self, path: str):
        with open(path, "rb") as f:
            image_data = f.read()
        return {
            "mime_type": "image/png",
            "data": image_data,
        }

class OllamaChatClient(BaseChatClient):
    def __init__(self, model_name: str = "gemma:7b"):
        self.model_name = model_name

    def send_message_once(
        self,
        prompt_text: str,
        image_paths: Optional[List[str]] = None,
        model: Optional[Type[BaseModel]] = None
    ) -> Any:
        messages = [{
            "role": "user",
            "content": prompt_text
        }]
        valid_image_paths = [path for path in (image_paths or []) if os.path.exists(path)]
        if valid_image_paths:
            messages[0]["images"] = valid_image_paths
        response = chat(
            model=self.model_name,
            messages=messages,
            format=model.model_json_schema() if model else None
        )
        return response['message']['content']

class VLLMChatClient:
    def __init__(self, model_name: str = 'gemma:7b', provider: LLMProvider = LLMProvider.ollama):
        self.model_name = model_name
        self.provider = provider
        self._client = self._get_client()

    def _get_client(self) -> BaseChatClient:
        if self.provider == LLMProvider.gemini:
            return GeminiChatClient(self.model_name)
        elif self.provider == LLMProvider.ollama:
            return OllamaChatClient(self.model_name)
        else:
            raise ValueError(f"Proveedor desconocido: {self.provider}")

    def send_message(
        self,
        prompt_text: str,
        image_paths: Optional[List[str]] = None,
        model: Optional[Type[BaseModel]] = None,
        retries: int = 3,
        retry_delay: int = 2
    ) -> Optional[Type[BaseModel]] | str:
        attempt = 0
        last_error = None

        while attempt < retries:
            try:
                response = self._client.send_message_once(
                    prompt_text=prompt_text,
                    image_paths=image_paths,
                    model=model
                )

                print("Respuesta cruda recibida del modelo:\n", response)
                if model:
                    return model.model_validate_json(response)
                else:
                    return response

            except (json.JSONDecodeError, Exception) as e:
                last_error = str(e)
                print(f"[ERROR DE PARSE] Intento {attempt + 1}: {last_error}")
                attempt += 1
                time.sleep(retry_delay)

        print("Fallo tras agotar los reintentos.")
        return None
