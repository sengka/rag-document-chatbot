import os
from dotenv import load_dotenv

load_dotenv()

# Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Embedding modeli (yerel, ücretsiz, API gerektirmez)
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Chunking ayarları dokumanın kaça bölüneceğini belirler
CHUNK_SIZE = 800       # karakter cinsinden
CHUNK_OVERLAP = 150    # karakter cinsinden

# Retrieval ayarları
TOP_K = 4  # her soruda getirilecek chunk sayısı

# Dosya yolları dosya nereye kaydedilecek
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploaded_docs")
INDEX_DIR = os.path.join(BASE_DIR, "vector_index")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(INDEX_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".doc", ".docx"}
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_LANG = "tur+eng"  # Türkçe + İngilizce