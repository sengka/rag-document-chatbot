from app.document_processor import extract_text, chunk_text

# Test etmek istediğin dosyanın yolunu buraya yaz
file_path = "uploaded_docs/test.txt"

text = extract_text(file_path)
print(f"Toplam karakter sayısı: {len(text)}\n")

chunks = chunk_text(text, source="test.txt")

print(f"Toplam chunk sayısı: {len(chunks)}\n")

for chunk in chunks:
    print(f"--- Chunk {chunk.chunk_index} (id: {chunk.id[:8]}...) ---")
    print(f"Uzunluk: {len(chunk.text)} karakter")
    print(chunk.text)
    print()