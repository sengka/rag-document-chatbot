from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL
from typing import Optional, List

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client

def build_prompt(question: str, retrieved_chunks: list) -> str:
    """Bulunan chunk'ları ve soruyu birleştirip LLM'e gönderilecek prompt'u oluşturur."""
    context_parts = []
    for i, item in enumerate(retrieved_chunks):
        chunk = item["chunk"]
        context_parts.append(f"[Kaynak {i+1}: {chunk.source}]\n{chunk.text}")

    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""Aşağıda kullanıcının yüklediği dokümanlardan alınmış ilgili bölümler var. Bu bölümlere dayanarak kullanıcının sorusunu cevapla.

Kurallar:
- Sadece aşağıdaki bağlamda verilen bilgiyi kullan, kendi genel bilgini ekleme.
- Eğer cevap bağlamda yoksa, "Bu sorunun cevabını yüklenen dokümanlarda bulamadım." de.
- Cevabını Türkçe ver, net ve öz ol.

BAĞLAM:
{context}

SORU: {question}

CEVAP:"""

    return prompt

def ask(question: str, top_k: int = 4, sources: Optional[List[str]] = None) -> dict:
    """Soruyu alır, ilgili chunk'ları bulur, LLM'den cevap üretir."""
    from app.embeddings import embed_query
    from app.vector_store import get_vector_store

    store = get_vector_store()

    if store.index.ntotal == 0:
        return {
            "answer": "Henüz hiç doküman yüklenmemiş. Lütfen önce bir doküman yükle.",
            "sources": [],
        }

    query_vec = embed_query(question)
    retrieved = store.search(query_vec, top_k=top_k)

    prompt = build_prompt(question, retrieved)

    client = get_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
    )

    answer = response.choices[0].message.content

    sources = list({item["chunk"].source for item in retrieved})

    return {
        "answer": answer,
        "sources": sources,
    }
