from typing import Optional, List, Any, Type, Dict
from pydantic import BaseModel
import google.generativeai as genai
from ollama import chat
from openai import OpenAI
from anthropic import Anthropic
import os
import time
import json
import base64
import re
import mimetypes
from enum import Enum

# Para Google Colab
try:
    from google.colab import userdata
    GOOGLE_API_KEY = userdata.get('GEMINI_API_KEY')
    OPENAI_API_KEY = userdata.get('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = userdata.get('CLAUDE_API_KEY')
except ImportError:
    # Para entorno local, usar variables de entorno
    from ps3_worker.constants import GOOGLE_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY

genai.configure(api_key=GOOGLE_API_KEY)


def get_image_mime_type(file_path: str) -> str:
    """Detecta el tipo MIME de una imagen basado en su extensión y contenido."""
    # Intentar detectar por extensión
    mime_type, _ = mimetypes.guess_type(file_path)
    
    if mime_type and mime_type.startswith('image/'):
        return mime_type
    
    # Fallback a tipos comunes basado en extensión
    ext = file_path.lower().split('.')[-1] if '.' in file_path else ''
    mime_map = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'webp': 'image/webp',
        'tiff': 'image/tiff',
        'svg': 'image/svg+xml'
    }
    
    return mime_map.get(ext, 'image/png')  # Fallback a PNG si no se puede determinar


class LLMProvider(Enum):
    gemini = "gemini"
    ollama = "ollama"
    openai = "openai"
    claude = "claude"

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
        
        # Verificar si la respuesta es válida
        if response.text:
            return response.text
        else:
            # Si no hay texto, verificar si hay contenido en las partes
            if hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content:
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        # Intentar extraer texto de las partes
                        text_parts = []
                        for part in candidate.content.parts:
                            if hasattr(part, 'text') and part.text:
                                text_parts.append(part.text)
                        if text_parts:
                            return ' '.join(text_parts)
            
            # Si no se puede extraer texto, devolver un mensaje de error
            raise ValueError("Gemini no devolvió una respuesta válida")

    def _load_image_as_part(self, path: str):
        with open(path, "rb") as f:
            image_data = f.read()
        mime_type = get_image_mime_type(path)
        return {
            "mime_type": mime_type,
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

class OpenAIChatClient(BaseChatClient):
    def __init__(self, model_name: str = "gpt-4o"):
        self.model_name = model_name
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def send_message_once(
        self,
        prompt_text: str,
        image_paths: Optional[List[str]] = None,
        model: Optional[Type[BaseModel]] = None
    ) -> Any:
        messages = [{"role": "user", "content": prompt_text}]
        
        if image_paths:
            content = [{"type": "text", "text": prompt_text}]
            for path in image_paths:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        image_data = f.read()
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    mime_type = get_image_mime_type(path)
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{base64_image}"
                        }
                    })
            messages[0]["content"] = content

        if model:
            response = self.client.chat.completions.parse(
                model=self.model_name,
                messages=messages,
                response_format=model,
                max_completion_tokens=10000
            )
            return response.choices[0].message.parsed
        else:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_completion_tokens=10000
            )
            return response.choices[0].message.content

class ClaudeChatClient(BaseChatClient):
    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022"):
        self.model_name = model_name
        # Configurar cliente con timeout y configuración optimizada
        self.client = Anthropic(
            api_key=ANTHROPIC_API_KEY,
            timeout=60.0,  # 60 segundos de timeout
            max_retries=2  # Reintentos automáticos
        )

    def send_message_once(
        self,
        prompt_text: str,
        image_paths: Optional[List[str]] = None,
        model: Optional[Type[BaseModel]] = None
    ) -> Any:
        if model:
            prompt_text += f"""

            Make sure the response follow a valid ```json response format, respond only the json which must be like:

            {model.model_json_schema()}
            """

        # Construir el contenido del mensaje
        content = [{"type": "text", "text": prompt_text}]
        
        # Agregar imágenes si se proporcionan
        if image_paths:
            for path in image_paths:
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        image_data = f.read()
                    base64_image = base64.b64encode(image_data).decode('utf-8')
                    mime_type = get_image_mime_type(path)
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": base64_image
                        }
                    })

        request_params = {
            "model": self.model_name,
            "max_tokens": 10000,
            "temperature": 0.4,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }

        try:
            response = self.client.messages.create(**request_params)

            if model:
                text_content = response.content[0].text.strip()

                json_pattern = r'```json\s*(.*?)\s*```'
                json_match = re.search(json_pattern, text_content, re.DOTALL)

                if json_match:
                    json_content = json_match.group(1).strip()
                    json_response = json.loads(json_content)
                    if "data" not in json_response or len(json_response.keys()) > 1:
                        json_response = {
                            "data": [
                                json_response
                            ]
                        }

                    if not isinstance(json_response["data"], list):
                        json_response["data"] = [json_response["data"]]

                    return model.model_validate(json_response)
                try:
                    json_response = json.loads(text_content)
                    return model.model_validate(json_response)
                except json.JSONDecodeError:
                    raise ValueError(f"No se encontró JSON válido en la respuesta: {text_content}")
            else:
                return response.content[0].text

        except Exception as e:
            raise e

class VLLMChatClient:
    def __init__(self, provider: LLMProvider = LLMProvider.ollama, model_name: str = 'gemma:7b'):
        self.model_name = model_name
        self.provider = provider
        self._client = self._get_client()

    def _get_client(self) -> BaseChatClient:
        if self.provider == LLMProvider.gemini:
            return GeminiChatClient(self.model_name)
        elif self.provider == LLMProvider.ollama:
            return OllamaChatClient(self.model_name)
        elif self.provider == LLMProvider.openai:
            return OpenAIChatClient(self.model_name)
        elif self.provider == LLMProvider.claude:
            return ClaudeChatClient(self.model_name)
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

                if model:
                    if isinstance(response, str):
                        return model.model_validate_json(response)
                    elif hasattr(response, 'model_dump'):
                        json_response = response.model_dump_json()
                        return model.model_validate_json(json_response)
                    else:
                        return model.model_validate_json(str(response))
                else:
                    return response

            except (json.JSONDecodeError, Exception) as e:
                last_error = str(e)
                print(f"[ERROR DE PARSE] Intento {attempt + 1}: {last_error}")
                attempt += 1
                time.sleep(retry_delay)

        print("Fallo tras agotar los reintentos.")
        return None
