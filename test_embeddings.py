from app.embeddings import embed_texts
import numpy as np

texts = [
    "Kedi çok tatlı bir hayvandır.",
    "Köpek sadık bir dosttur.",
    "Bugün hava çok güneşli.",
]

embeddings = embed_texts(texts)
print(f"Embedding boyutu (shape): {embeddings.shape}\n")

# Cosine similarity = normalize edilmiş vektörlerin dot product'ı
def similarity(a, b):
    return float(np.dot(a, b))

print("Kedi <-> Köpek benzerliği:", similarity(embeddings[0], embeddings[1]))
print("Kedi <-> Hava benzerliği: ", similarity(embeddings[0], embeddings[2]))
print("Köpek <-> Hava benzerliği:", similarity(embeddings[1], embeddings[2]))