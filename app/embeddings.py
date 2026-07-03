from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL_NAME
from typing import List
import numpy as np

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _model

def embed_texts(texts: List[str]) -> np.ndarray:
    """Bir liste metni embedding matrisine çevirir. Shape: (n, dim)"""
    model = get_model()
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return embeddings.astype("float32")


def embed_query(query: str) -> np.ndarray:
    """Tek bir sorguyu embedding vektörüne çevirir. Shape: (dim,)"""
    return embed_texts([query])[0]