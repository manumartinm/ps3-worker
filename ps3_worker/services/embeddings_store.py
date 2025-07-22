import torch
from qdrant_client import QdrantClient
# pyrefly: ignore  # import-error
from transformers import AutoTokenizer, AutoModel
from typing import List, Optional, Optional
from qdrant_client.models import Distance, VectorParams, PointStruct, UpdateStatus

def mean_pooling(model_output, attention_mask):
    embeddings = model_output[0]
    mask = attention_mask.unsqueeze(-1).expand(embeddings.size()).float()

    return torch.sum(embeddings * mask, 1) / torch.clamp(mask.sum(1), min=1e-9)

class EmbeddingStore:
    def __init__(
        self,
        model_name: str = "NeuML/bioclinical-modernbert-base-embeddings",
        qdrant_host: Optional[str] = "localhost",
        qdrant_port: Optional[int] = 6333,
        collection_name: str = "document_embeddings",
        distance_metric: Distance = Distance.COSINE
    ):
        print(f"Inicializando EmbeddingStore con modelo: {model_name}")
        self.model_name = model_name
        self.collection_name = collection_name
        self.distance_metric = distance_metric

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            print("Modelo de embeddings cargado exitosamente.")
        except Exception as e:
            print(f"Error al cargar el modelo '{model_name}': {e}")
            raise

        try:
            test_inputs = self.tokenizer("Test sentence for dimension.", return_tensors='pt')
            with torch.no_grad():
                test_output = self.model(**test_inputs)

            test_embedding = mean_pooling(test_output, test_inputs['attention_mask'])
            self.vector_dimension = test_embedding.shape[1]

            print(f"Dimensión del vector determinada: {self.vector_dimension}")
        except Exception as e:
             print(f"Error al determinar la dimensión del vector: {e}")
             raise

        print("Conectando a Qdrant...")
        try:
            self.client = QdrantClient(":memory:")
            print(f"Conectado a Qdrant local en {qdrant_host}:{qdrant_port}")
        except Exception as e:
            print(f"Error al conectar a Qdrant: {e}")
            raise

    def create_collection(self):
        try:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_dimension, distance=self.distance_metric),
            )
        except Exception as e:
            print(f"Error al crear/recrear la colección '{self.collection_name}': {e}")
            raise

    def generate_embeddings(self, sentences: List[str]) -> torch.Tensor:
        if not sentences:
            print("Lista de frases/fragmentos vacía. No se generarán embeddings.")
            return torch.empty(0, self.vector_dimension)

        inputs = self.tokenizer(
            sentences,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors='pt'
        )

        if next(self.model.parameters()).is_cuda:
             inputs = {k: v.to('cuda') for k, v in inputs.items()}

        with torch.no_grad():
            output = self.model(**inputs)

        embeddings = mean_pooling(output, inputs['attention_mask'])
        embeddings = embeddings.cpu()

        print(f"Embeddings generados para {len(sentences)} fragmentos.")
        return embeddings


    def store_embeddings(self, sentences: List[str], ids: Optional[List[int]] = None) -> UpdateStatus:
        if not sentences:
            print("Lista de frases/fragmentos vacía. No se almacenarán puntos en Qdrant.")
            return UpdateStatus.COMPLETED

        print(f"Generando y almacenando embeddings para {len(sentences)} fragmentos...")

        embeddings_tensor = self.generate_embeddings(sentences)

        points_to_upsert = []
        embeddings_list = embeddings_tensor.tolist()

        if ids is None:
            ids = list(range(len(sentences)))
        elif len(ids) != len(sentences):
            raise ValueError("La longitud de la lista de IDs debe coincidir con la longitud de la lista de frases.")

        for i, (sentence, embedding) in enumerate(zip(sentences, embeddings_list)):
            points_to_upsert.append(
                PointStruct(
                    id=ids[i],
                    vector=embedding,
                    payload={"text": sentence},
                )
            )

        try:
            result = self.client.upsert(
                collection_name=self.collection_name,
                wait=True,
                points=points_to_upsert,
            )
            print(f"Operación Upsert completada con estado: {result.status}")

            return result.status
        except Exception as e:
            print(f"Error durante la operación de upsert en Qdrant: {e}")
            raise


    def retrieve_similar(self, query_text: str, limit: int = 5):
        if not query_text:
            print("Texto de consulta vacío. No se realizará la búsqueda.")
            return []

        print(f"Buscando fragmentos similares a: '{query_text}' en la colección '{self.collection_name}'...")

        try:
            query_embedding_tensor = self.generate_embeddings([query_text])
            query_embedding_list = query_embedding_tensor[0].tolist()

            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding_list,
                with_payload=True,
                with_vectors=False,
            )

            print(f"Búsqueda completada. Encontrados {len(search_result)} resultados.")
            return search_result
        except Exception as e:
            print(f"Error durante la búsqueda en Qdrant: {e}")
