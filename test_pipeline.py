from app.document_processor import process_file
from app.embeddings import embed_texts, embed_query
from app.vector_store import get_vector_store

# 1. Dosyayı işle (oku + chunkla)
file_path = "uploaded_docs/test.txt"  # kendi test dosyanın yoluyla değiştir
chunks = process_file(file_path)
print(f"{len(chunks)} chunk oluşturuldu.\n")

# 2. Chunk'ları embedding'e çevir
texts = [c.text for c in chunks]
embeddings = embed_texts(texts)
print(f"Embedding shape: {embeddings.shape}\n")

# 3. Vektör store'a ekle
store = get_vector_store("vector_index")  # tek kullanıcılı deneme dizini
store.add_chunks(chunks, embeddings)
print(f"Index'te toplam {store.index.ntotal} vektör var.\n")

# 4. Bir soru sor, en yakın chunk'ları bul
question = "Bu sistemin mimarisi nasıl?"
query_vec = embed_query(question)
results = store.search(query_vec, top_k=2)

print(f"Soru: {question}\n")
for r in results:
    print(f"Skor: {r['score']:.4f} | Kaynak: {r['chunk'].source}")
    print(r['chunk'].text[:200])
    print("---")

from app.rag import ask

print("\n=== RAG TEST ===\n")
result = ask("Bu sistemin mimarisi nasıl?")
print("Cevap:", result["answer"])
print("Kaynaklar:", result["sources"])