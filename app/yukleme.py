"""Yükleme denetimleri: ad temizleme, içerik türü (sihirli bayt), PDF sayfa sınırı, kota."""
import os
import re
import unicodedata
import zipfile
from typing import Optional

import pypdf

from app.config import (
    ALLOWED_EXTENSIONS,
    MAKS_DOSYA_SAYISI,
    MAKS_PDF_SAYFA,
    MAKS_TOPLAM_BAYT,
)
from app.guvenlik import Hata

MAKS_AD = 100
_YASAK = re.compile(r'[\x00-\x1f\x7f<>:"|?*\\/]')


def temiz_ad(ham: str) -> str:
    """Görünen ad: NFC, yol parçaları ve kontrol/yasak karakterler atılır, 100 karaktere kısalır.
    Diskte bu ad hiç kullanılmaz (dosya <uuid>.<uzantı> olarak saklanır)."""
    ad = unicodedata.normalize("NFC", ham or "")
    ad = re.split(r"[\\/]", ad)[-1]
    ad = _YASAK.sub("", ad)
    ad = re.sub(r"\s+", " ", ad).strip().strip(".").strip()
    govde, uzanti = os.path.splitext(ad)
    uzanti = uzanti.lower()
    if uzanti not in ALLOWED_EXTENSIONS or not govde.strip(". "):
        raise Hata(400, "tur")
    return govde[: MAKS_AD - len(uzanti)].rstrip() + uzanti


def icerik_denetle(yol: str, uzanti: str) -> Optional[int]:
    """Uzantı ile içerik uyuşmalı. PDF ise sayfa sayısını döndürür."""
    with open(yol, "rb") as f:
        bas = f.read(8)
    if uzanti == ".pdf":
        if not bas.startswith(b"%PDF-"):
            raise Hata(400, "tur")
        try:
            sayfa = len(pypdf.PdfReader(yol).pages)
        except Exception:
            raise Hata(400, "tur")
        if sayfa > MAKS_PDF_SAYFA:
            raise Hata(400, "sayfa")
        return sayfa
    if uzanti == ".docx":
        if not bas.startswith(b"PK\x03\x04") or not zipfile.is_zipfile(yol):
            raise Hata(400, "tur")
        with zipfile.ZipFile(yol) as z:
            if "word/document.xml" not in z.namelist():
                raise Hata(400, "tur")
        return None
    if uzanti == ".txt":
        with open(yol, "rb") as f:
            veri = f.read()
        if b"\x00" in veri:
            raise Hata(400, "tur")
        try:
            veri.decode("utf-8")
        except UnicodeDecodeError:
            raise Hata(400, "tur")
        return None
    raise Hata(400, "tur")


def kota_denetle(sayi: int, toplam: int, yeni_bayt: int) -> None:
    if sayi >= MAKS_DOSYA_SAYISI or toplam + yeni_bayt > MAKS_TOPLAM_BAYT:
        raise Hata(409, "kota")
