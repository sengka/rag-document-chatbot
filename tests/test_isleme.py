"""İşleme hataları: günlükte mesaj + traceback, istemciye sabit kod; metinsiz belge; Unicode yollu indeks."""
import io
import logging
import os

import docx
import faiss
import numpy as np

from app import kovan
from app.document_processor import Chunk
from app.vector_store import VectorStore
from conftest import DERS_A, listele, yukle


def bos_docx() -> bytes:
    b = io.BytesIO()
    docx.Document().save(b)
    return b.getvalue()


def test_metinsiz_docx_ayri_hata_kodu(client, groq):
    k = "6" * 24
    assert yukle(client, k, DERS_A, "bos.docx", bos_docx()).status_code == 202
    d = listele(client, k).json()["dosyalar"][0]
    assert d["durum"] == "hata" and d["hata"] == "metin"


def test_isleme_hatasi_gunluge_traceback_istemciye_sabit_kod(client, groq, monkeypatch, caplog):
    k = "7" * 24

    def patla(_metinler):
        raise RuntimeError("Error in faiss::FileIOWriter could not open C:\\Masaüstü\\x")

    monkeypatch.setattr(kovan, "embed_texts", patla)
    with caplog.at_level(logging.ERROR, logger="ari.kovan"):
        assert yukle(client, k, DERS_A, "n.docx", _docx("Türev notu.")).status_code == 202
    d = listele(client, k).json()["dosyalar"][0]
    assert d["hata"] == "isleme"
    assert "Masaüstü" not in str(d)  # ayrıntı istemciye gitmez
    kayit = next(r for r in caplog.records if "işleme hatası" in r.getMessage())
    assert kayit.exc_info and kayit.exc_info[0] is RuntimeError
    assert "could not open" in caplog.text and "Traceback" in caplog.text


def _docx(metin: str) -> bytes:
    belge = docx.Document()
    belge.add_paragraph(metin)
    b = io.BytesIO()
    belge.save(b)
    return b.getvalue()


def test_indeks_turkce_yolda_faiss_dosya_islevleri_olmadan(tmp_path, monkeypatch):
    # Windows'ta faiss'e dosya yolu verilirse Türkçe karakterli yolda RuntimeError olur; yol verilmemeli
    # (serialize/deserialize içeride bellek yazıcısıyla aynı işlevleri çağırır, onlara izin var)
    asil_yaz, asil_oku = faiss.write_index, faiss.read_index

    def yaz(index, hedef, *a):
        assert not isinstance(hedef, str), "faiss.write_index dosya yoluyla çağrıldı"
        return asil_yaz(index, hedef, *a)

    def oku(kaynak, *a):
        assert not isinstance(kaynak, str), "faiss.read_index dosya yoluyla çağrıldı"
        return asil_oku(kaynak, *a)

    monkeypatch.setattr(faiss, "write_index", yaz)
    monkeypatch.setattr(faiss, "read_index", oku)
    dizin = os.path.join(tmp_path, "Masaüstü", "kovan_ğüşİ")
    store = VectorStore(dizin)
    vek = np.zeros((1, 384), dtype="float32")
    vek[0, 0] = 1
    store.add_chunks([Chunk(id="1", text="Çarpım kuralı", source="a.txt", chunk_index=0)], vek)
    yeniden = VectorStore(dizin)
    assert yeniden.index.ntotal == 1
    assert yeniden.search(vek[0])[0]["chunk"].text == "Çarpım kuralı"
