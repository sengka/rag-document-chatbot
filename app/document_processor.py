import os
import re
import uuid
from dataclasses import dataclass, field
from typing import List

import pypdf
import pytesseract
from PIL import Image
import fitz  # PyMuPDF
import io
import docx  # python-docx

from app.config import (
    ALLOWED_EXTENSIONS,
    TESSERACT_CMD,
    TESSERACT_LANG,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
)

pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


@dataclass
class Chunk:
    id: str
    text: str
    source: str  # hangi dosyadan geldiği
    chunk_index: int
    metadata: dict = field(default_factory=dict)


# dosya istenen formatta mı
def is_supported(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


# doğru okuyucuya dosyayı yönlendirir
def extract_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".txt":
        return _extract_txt(file_path)
    elif ext == ".pdf":
        return _extract_pdf(file_path)
    elif ext in (".docx", ".doc"):
        return _extract_docx(file_path)
    else:
        raise ValueError(f"Desteklenmeyen dosya formatı: {ext}")


def _extract_pdf(file_path: str) -> str:
    text_parts = []
    reader = pypdf.PdfReader(file_path)
    doc = fitz.open(file_path)  # OCR gerekirse kullanacağız

    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""

        if page_text.strip():
            # Normal metin katmanı var, direkt kullan
            text_parts.append(page_text)
        else:
            # Metin katmanı yok -> muhtemelen taranmış/resimli sayfa -> OCR yap
            ocr_text = _ocr_page(doc, page_num)
            if ocr_text.strip():
                text_parts.append(ocr_text)

    doc.close()
    return "\n\n".join(text_parts)


def _ocr_page(doc, page_num: int) -> str:
    """Bir PDF sayfasını resme çevirip Tesseract ile OCR yapar."""
    page = doc[page_num]
    pix = page.get_pixmap(dpi=300)  # yüksek çözünürlük -> daha iyi OCR sonucu
    img_bytes = pix.tobytes("png")
    image = Image.open(io.BytesIO(img_bytes))
    return pytesseract.image_to_string(image, lang=TESSERACT_LANG)


# utf-8 olarak dosyayı okur
def _extract_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _extract_docx(file_path: str) -> str:
    document = docx.Document(file_path)
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]

    # Tablolardaki metni de dahil edelim
    for table in document.tables:
        for row in table.rows:
            row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
            if row_text:
                paragraphs.append(row_text)

    return "\n\n".join(paragraphs)


def clean_text(text: str) -> str:
    """Fazla boşlukları, satır sonlarını sadeleştirir."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, source: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Chunk]:
    """
    Metni karakter bazlı, örtüşmeli (overlap) parçalara ayırır.
    Cümle sınırlarına yakın kesmeye çalışır ki anlam bütünlüğü bozulmasın.
    """
    text = clean_text(text)
    if not text:
        return []

    chunks: List[Chunk] = []
    start = 0
    text_len = len(text)
    idx = 0

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Mümkünse en yakın cümle/paragraf sonuna kadar uzat (kelime ortasında kesmemek için)
        if end < text_len:
            threshold = start + (chunk_size * 0.5)
            boundary = -1

            period_boundary = text.rfind(". ", start, end)
            if period_boundary != -1 and period_boundary > threshold:
                boundary = period_boundary
            else:
                newline_boundary = text.rfind("\n", start, end)
                if newline_boundary != -1 and newline_boundary > threshold:
                    boundary = newline_boundary
                else:
                    space_boundary = text.rfind(" ", start, end)
                    if space_boundary != -1 and space_boundary > threshold:
                        boundary = space_boundary

            if boundary != -1:
                end = boundary + 1

        chunk_str = text[start:end].strip()
        if chunk_str:
            chunks.append(
                Chunk(
                    id=str(uuid.uuid4()),
                    text=chunk_str,
                    source=source,
                    chunk_index=idx,
                )
            )
            idx += 1

        if end >= text_len:
            break

        start = max(end - overlap, start + 1)

    return chunks


def process_file(file_path: str) -> List[Chunk]:
    """Tek bir dosyayı uçtan uca işler: oku -> temizle -> chunkla."""
    filename = os.path.basename(file_path)
    raw_text = extract_text(file_path)
    return chunk_text(raw_text, source=filename)