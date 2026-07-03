import os
import pickle
import faiss
import numpy as np
from typing import List, Optional

from app.config import INDEX_DIR
from app.document_processor import Chunk

INDEX_PATH = os.path.join(INDEX_DIR, "faiss.index")
METADATA_PATH = os.path.join(INDEX_DIR, "metadata.pkl")

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 modelinin çıktı boyutu

class VectorStore:
    def __init__(self):
        self.index: faiss.Index
        self.chunks: List[Chunk] = []  # FAISS'teki sıraya paralel chunk listesi
        self._load_or_create()

    def _load_or_create(self):
        if os.path.exists(INDEX_PATH) and os.path.exists(METADATA_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            with open(METADATA_PATH, "rb") as f:
                self.chunks = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
            self.chunks = []

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray):
        """Yeni chunk'ları ve embedding'lerini index'e ekler."""
        if len(chunks) == 0:
            return

        self.index.add(embeddings)
        self.chunks.extend(chunks)
        self.save()

    def save(self):
        """Index ve metadata'yı diske kaydeder."""
        faiss.write_index(self.index, INDEX_PATH)
        with open(METADATA_PATH, "wb") as f:
            pickle.dump(self.chunks, f)

    def search(self, query_embedding: np.ndarray, top_k: int = 4, sources: Optional[List[str]] = None) -> List[dict]:
        """
        Verilen sorgu vektörüne en yakın top_k chunk'ı döndürür.
        sources verilirse, sadece o dosyalardan gelen chunk'lar dikkate alınır.
        """
        if self.index.ntotal == 0:
            return []

        query_vec = query_embedding.reshape(1, -1)

        # Filtre varsa, eleme sonrası yeterli sonuç kalması için daha fazla aday çekiyoruz
        search_k = self.index.ntotal if sources else min(top_k, self.index.ntotal)

        scores, indices = self.index.search(query_vec, search_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            chunk = self.chunks[idx]

            if sources and chunk.source not in sources:
                continue

            results.append({
                "chunk": chunk,
                "score": float(score),
            })

            if len(results) >= top_k:
                break

        return results

    def list_sources(self) -> List[str]:
        """Index'teki benzersiz dosya adlarını döndürür."""
        return sorted({chunk.source for chunk in self.chunks})

_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore()
    return _store