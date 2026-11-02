import os
import pickle
import threading
import faiss
import numpy as np
from typing import Dict, List, Optional

from app.document_processor import Chunk

EMBEDDING_DIM = 384  # paraphrase-multilingual-MiniLM-L12-v2 çıktı boyutu


class VectorStore:
    """Tek bir kullanıcının FAISS indeksi; dosyaları kendi dizininde durur."""

    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        self.index_path = os.path.join(index_dir, "faiss.index")
        self.metadata_path = os.path.join(index_dir, "metadata.pkl")
        self.lock = threading.RLock()
        self.index: faiss.Index
        self.chunks: List[Chunk] = []  # FAISS'teki sıraya paralel chunk listesi
        self._load_or_create()

    def _load_or_create(self):
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            self.index = faiss.read_index(self.index_path)
            with open(self.metadata_path, "rb") as f:
                self.chunks = pickle.load(f)
        else:
            self.index = faiss.IndexFlatIP(EMBEDDING_DIM)
            self.chunks = []

    def add_chunks(self, chunks: List[Chunk], embeddings: np.ndarray):
        """Yeni chunk'ları ve embedding'lerini index'e ekler."""
        if len(chunks) == 0:
            return
        with self.lock:
            self.index.add(embeddings)
            self.chunks.extend(chunks)
            self.save()

    def save(self):
        """Index ve metadata'yı diske kaydeder."""
        with self.lock:
            os.makedirs(self.index_dir, exist_ok=True)
            faiss.write_index(self.index, self.index_path)
            with open(self.metadata_path, "wb") as f:
                pickle.dump(self.chunks, f)

    def remove_source(self, source: str) -> int:
        """Bir dosyanın bütün parçalarını indeksten çıkarır; çıkarılan parça sayısını döndürür."""
        with self.lock:
            keep = [i for i, c in enumerate(self.chunks) if c.source != source]
            removed = len(self.chunks) - len(keep)
            if removed == 0:
                return 0
            vectors = self.index.reconstruct_n(0, self.index.ntotal) if self.index.ntotal else None
            index = faiss.IndexFlatIP(EMBEDDING_DIM)
            if keep:
                index.add(np.ascontiguousarray(vectors[keep]))
            self.index = index
            self.chunks = [self.chunks[i] for i in keep]
            self.save()
            return removed

    def search(self, query_embedding: np.ndarray, top_k: int = 4, sources: Optional[List[str]] = None) -> List[dict]:
        """
        Verilen sorgu vektörüne en yakın top_k chunk'ı döndürür.
        sources verilirse, sadece o dosyalardan gelen chunk'lar dikkate alınır.
        """
        with self.lock:
            if self.index.ntotal == 0:
                return []

            query_vec = query_embedding.reshape(1, -1)

            # Filtre varsa, eleme sonrası yeterli sonuç kalması için daha fazla aday çekiyoruz
            search_k = self.index.ntotal if sources is not None else min(top_k, self.index.ntotal)

            scores, indices = self.index.search(query_vec, search_k)

            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:
                    continue
                chunk = self.chunks[idx]

                if sources is not None and chunk.source not in sources:
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


_stores: Dict[str, VectorStore] = {}
_stores_lock = threading.Lock()


def get_vector_store(index_dir: str) -> VectorStore:
    """Dizin başına (kullanıcı başına) tek VectorStore örneği."""
    with _stores_lock:
        store = _stores.get(index_dir)
        if store is None:
            store = VectorStore(index_dir)
            _stores[index_dir] = store
        return store


def drop_vector_store(index_dir: str) -> None:
    """Kullanıcı silinince önbellekteki indeksi bırakır."""
    with _stores_lock:
        _stores.pop(index_dir, None)
