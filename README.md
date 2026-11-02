# Kendi Dokümanların ile Sohbet Et

> **Bu dal Mindshire+ "Arı" yan servisidir.** Servis yalnız `127.0.0.1`'de, Mindshire Express sunucusunun arkasında çalışır; eski bağımsız arayüz (`/`, `/static`, `/docs`) kapalıdır. Ayrıntılar aşağıda "Mindshire yan servisi" bölümünde.

TXT, PDF ve DOCX dosyaları yükleyip, bu dokümanlar üzerinden yapay zeka ile soru-cevap yapabileceğin bir RAG (Retrieval-Augmented Generation) uygulaması.

## Özellikler

- 📄 TXT, PDF, DOC/DOCX dosya desteği
- 🔍 Taranmış/resimli PDF'ler için OCR desteği (Tesseract)
- 🧩 Akıllı chunking (cümle sınırlarına duyarlı, örtüşmeli parçalama)
- 🌍 Çok dilli embedding (Türkçe soru — İngilizce doküman gibi diller arası aramaları destekler)
- ⚡ FAISS ile hızlı vektör arama
- 🤖 Groq (Llama 3.3) ile Türkçe cevap üretimi
- 📚 Birden fazla doküman üzerinden birleşik cevap üretme
- ✅ Kaynak gösterme (cevabın hangi dokümandan geldiği)
- 🎯 Dosya bazlı filtreleme (istediğin dokümanları seçip sadece onlarda arama yapabilirsin)

## Mimari

```
Doküman Yükleme → Metne Çevirme (+ OCR) → Chunking → Embedding
    → FAISS'e Kayıt → Soru Embedding → Retrieval (Top-K)
    → Groq LLM → Türkçe Cevap + Kaynaklar
```

## Teknoloji Yığını

- **Backend:** Python, FastAPI
- **LLM:** Groq (llama-3.3-70b-versatile)
- **Embedding:** sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2)
- **Vektör Veritabanı:** FAISS
- **Doküman İşleme:** pypdf, python-docx, pytesseract (OCR), PyMuPDF
- **Frontend:** Vanilla HTML/CSS/JS

## Kurulum

### 1. Gereksinimler

- Python 3.10+
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (taranmış PDF desteği için — kurulum sırasında Turkish dil paketini de işaretleyin)
- Ücretsiz bir [Groq API key](https://console.groq.com)

### 2. Depoyu klonla

```bash
git clone https://github.com/sengka/rag-document-chatbot.git
cd rag-document-chatbot
```

### 3. Sanal ortam oluştur ve aktive et

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 4. Bağımlılıkları kur

```bash
pip install -r requirements.txt
```

### 5. Ortam değişkenlerini ayarla

Proje kök dizininde `.env` adında bir dosya oluştur:

```
GROQ_API_KEY=senin_groq_api_keyin
```

### 6. Tesseract yolunu ayarla (Windows için)

`app/config.py` içinde `TESSERACT_CMD` değişkeninin Tesseract kurulum yolunla eşleştiğinden emin ol (varsayılan: `C:\Program Files\Tesseract-OCR\tesseract.exe`).

### 7. Uygulamayı çalıştır

```bash
uvicorn app.main:app --reload
```

Tarayıcıda `http://localhost:8000` adresine git.

## Kullanım

1. **Dosya Seç** ile bir doküman seç (TXT, PDF, DOC veya DOCX)
2. **Yükle** butonuna tıkla — doküman işlenip indekslenecek
3. Yüklenen dosyalar üstte rozet olarak görünecek; işaretli olanlarda arama yapılır (varsayılan: hepsi işaretli)
4. Alt kısımdaki kutuya sorunu yaz, **Gönder**'e tıkla (ya da Enter'a bas)
5. Cevap, ilgili kaynak dosya adıyla birlikte gösterilecek

## API Endpoint'leri

| Method | Endpoint  | Açıklama                               |
| ------ | --------- | -------------------------------------- |
| GET    | `/`       | Frontend arayüzü                       |
| POST   | `/upload` | Doküman yükler, işler, indeksler       |
| POST   | `/chat`   | Soru alır, RAG ile cevap üretir        |
| GET    | `/files`  | Yüklenen dosyaların listesini döndürür |

İnteraktif API dokümantasyonu için: `http://localhost:8000/docs`

## Proje Yapısı

```
app/
├── config.py              # Ayarlar (API key, chunk boyutu, yollar)
├── document_processor.py  # Dosya okuma, OCR, chunking
├── embeddings.py          # Metin → vektör dönüşümü
├── vector_store.py        # FAISS wrapper (ekleme, arama, dosya listesi)
├── rag.py                 # Retrieval + Groq ile cevap üretimi
├── main.py                # FastAPI endpoint'leri
└── static/                # Frontend (HTML/CSS/JS)
```

## Notlar

- `.doc` formatı doğrudan desteklenmez, `.docx`'e çevirmeniz gerekir (python-docx kısıtı).
- Aynı dosya adıyla tekrar yükleme yapılırsa, index'e ek olarak eklenir (üzerine yazmaz).

## Mindshire yan servisi

- Başlatma (Mindshire deposunda tek komut: `npm run dev:ari`) ya da elle:
  `ARI_GIZLI=... python -m uvicorn app.main:app --host 127.0.0.1 --port 8001`
- `ARI_GIZLI` (en az 32 karakter, Mindshire `.env`'iyle aynı) yoksa servis başlamaz.
- Ortam: `GROQ_API_KEY`, isteğe bağlı `GROQ_MODEL`, `TESSERACT_CMD` (Linux/macOS: ör. `/usr/bin/tesseract`), `ARI_VERI_DIZINI` (varsayılan `kovan_verisi/`).
- Her istek Express'in imzaladığı başlıkları taşır: `X-Ms-Kullanici` (userId), `X-Ms-Zaman`, `X-Ms-Imza = hex(HMAC-SHA256(ARI_GIZLI, "zaman\nMETOD\nyol?sorgu\nuserId"))`, 60 sn pencere.
- Her kullanıcının dosyaları, manifest'i ve FAISS indeksi ayrı: `ARI_VERI_DIZINI/<userId>/`. Dosyalar diskte `<uuid>.<uzantı>` adıyla saklanır.
- Sınırlar: TXT/PDF/DOCX (içerik imzası denetlenir), dosya başına 20 MB, PDF en fazla 150 sayfa, kullanıcı başına 30 dosya / 100 MB.
- Uçlar: `GET /saglik`, `GET /files[?ders=]`, `GET /files/{id}`, `DELETE /files/{id}`, `POST /upload?ders=` (ham gövde, `X-Dosya-Adi`), `POST /chat {soru, ders}`, `DELETE /dersler/{ders}`, `DELETE /kullanici`. Hatalar yalnız `{"kod": ...}` döner.
- Soru ve bulunan not parçaları cevap üretmek için Groq'a gönderilir; sistem mesajı belge içeriğinin talimat olmadığını söyler.
- Testler: `pip install -r requirements-dev.txt && pytest` (embedding modeli ve Groq sahte).
