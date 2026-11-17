"""Yükleme güvenliği: ad, tür, boyut, sayfa, kota."""
import io
import os

import docx
import fitz

from app import kovan, yukleme
from app.config import MAKS_DOSYA_BAYT, VERI_DIZINI
from conftest import DERS_A, listele, yukle


def pdf(sayfa=1, metin="Turev carpim kurali"):
    d = fitz.open()
    for _ in range(sayfa):
        d.new_page().insert_text((72, 72), metin)
    return d.tobytes()


def test_yol_gecisi_adi_diske_yansimaz(client, groq):
    k = "1" * 24
    r = yukle(client, k, DERS_A, "../../../etc/passwd.txt", b"Merhaba not.")
    assert r.status_code == 202
    assert r.json()["dosya"]["ad"] == "passwd.txt"
    dosyalar = os.listdir(kovan.dosya_dizini(k))
    assert len(dosyalar) == 1 and dosyalar[0].endswith(".txt") and "passwd" not in dosyalar[0]
    assert not os.path.exists(os.path.join(VERI_DIZINI, "..", "etc"))


def test_ad_temizleme():
    assert yukleme.temiz_ad('a<b>:"c|?*.TXT') == "abc.txt"
    assert yukleme.temiz_ad("C:\\Users\\x\\notlar.pdf") == "notlar.pdf"
    assert len(yukleme.temiz_ad("ç" * 300 + ".docx")) == 100
    for kotu in ("", ".txt", "sunum.pptx", "notlar.md", "eski.doc", "..", "notlar.txt/.."):
        try:
            yukleme.temiz_ad(kotu)
            raise AssertionError(kotu)
        except Exception as e:
            assert getattr(e, "detail", None) == "tur", kotu


def test_tur_icerikle_uyusmali(client, groq):
    k = "2" * 24
    assert yukle(client, k, DERS_A, "sunum.pptx", b"PK\x03\x04").json() == {"kod": "tur"}
    assert yukle(client, k, DERS_A, "sahte.pdf", b"bu bir pdf degil").json() == {"kod": "tur"}
    assert yukle(client, k, DERS_A, "sahte.docx", b"PK\x03\x04 bozuk").json() == {"kod": "tur"}
    assert yukle(client, k, DERS_A, "ikili.txt", b"\x00\x01\x02").json() == {"kod": "tur"}
    assert yukle(client, k, DERS_A, "bos.txt", b"").json() == {"kod": "bos"}
    assert listele(client, k).json()["dosyalar"] == []


def test_boyut_siniri_413(client, groq):
    k = "3" * 24
    r = yukle(client, k, DERS_A, "buyuk.txt", b"a" * (MAKS_DOSYA_BAYT + 1))
    assert r.status_code == 413 and r.json() == {"kod": "boyut"}
    assert listele(client, k).json()["dosyalar"] == []


def test_pdf_ve_docx_islenir_sayfa_siniri(client, groq):
    k = "4" * 24
    r = yukle(client, k, DERS_A, "turev.pdf", pdf(3))
    assert r.status_code == 202
    belge = docx.Document()
    belge.add_paragraph("Zincir kurali notu.")
    tampon = io.BytesIO()
    belge.save(tampon)
    assert yukle(client, k, DERS_A, "zincir.docx", tampon.getvalue()).status_code == 202
    dosyalar = {d["ad"]: d for d in listele(client, k).json()["dosyalar"]}
    assert dosyalar["turev.pdf"]["sayfa"] == 3 and dosyalar["turev.pdf"]["durum"] == "hazir"
    assert dosyalar["zincir.docx"]["durum"] == "hazir" and dosyalar["zincir.docx"]["parca"] == 1

    r = yukle(client, k, DERS_A, "uzun.pdf", pdf(151, "x"))
    assert r.status_code == 400 and r.json() == {"kod": "sayfa"}


def test_kota_409(client, groq, monkeypatch):
    k = "5" * 24
    monkeypatch.setattr(yukleme, "MAKS_DOSYA_SAYISI", 2)
    assert yukle(client, k, DERS_A, "a.txt", b"bir").status_code == 202
    assert yukle(client, k, DERS_A, "b.txt", b"iki").status_code == 202
    r = yukle(client, k, DERS_A, "c.txt", b"uc")
    assert r.status_code == 409 and r.json() == {"kod": "kota"}
    monkeypatch.setattr(yukleme, "MAKS_DOSYA_SAYISI", 30)
    monkeypatch.setattr(yukleme, "MAKS_TOPLAM_BAYT", 10)
    assert yukle(client, k, DERS_A, "d.txt", b"0123456789").json() == {"kod": "kota"}
