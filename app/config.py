import os
from dotenv import load_dotenv

load_dotenv()

# Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Embedding modeli (yerel, ücretsiz, API gerektirmez)
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"

# Chunking ayarları dokumanın kaça bölüneceğini belirler
CHUNK_SIZE = 800       # karakter cinsinden
CHUNK_OVERLAP = 150    # karakter cinsinden

# Retrieval ayarları
TOP_K = 4  # her soruda getirilecek chunk sayısı

# Dosya yolları: her kullanıcının dosyaları ve indeksi VERI_DIZINI/<userId>/ altında
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERI_DIZINI = os.path.realpath(os.getenv("ARI_VERI_DIZINI", os.path.join(BASE_DIR, "kovan_verisi")))

# Mindshire ile paylaşılan gizli anahtar (Express isteği imzalar)
ARI_GIZLI = os.getenv("ARI_GIZLI", "")

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}
TESSERACT_CMD = os.getenv("TESSERACT_CMD", r"C:\Program Files\Tesseract-OCR\tesseract.exe")
TESSERACT_LANG = "tur+eng"  # Türkçe + İngilizce

# Sınırlar (kullanıcı başına)
MAKS_DOSYA_BAYT = 20 * 1024 * 1024
MAKS_DOSYA_SAYISI = 30
MAKS_TOPLAM_BAYT = 100 * 1024 * 1024
MAKS_PDF_SAYFA = 150
MAKS_SORU = 300
