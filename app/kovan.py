"""Kullanıcı başına kovan: dosyalar, manifest ve FAISS indeksi VERI_DIZINI/<userId>/ altında.

Bir kullanıcının verisine yalnız kendi userId'siyle (imzalı başlıktan) erişilir; başka
kullanıcının dizini hiçbir uçtan açılmaz.
"""
import json
import logging
import os
import re
import shutil
import threading
import time
from typing import List, Optional

from app.config import VERI_DIZINI
from app.document_processor import chunk_text, extract_text
from app.embeddings import embed_texts
from app.guvenlik import KULLANICI_RE, Hata
from app.vector_store import drop_vector_store, get_vector_store

log = logging.getLogger("ari.kovan")

DERS_RE = re.compile(r"^[a-f0-9]{24}$")
ADIMLAR = ("Metin çıkarılıyor", "Parçalara ayrılıyor", "Dizinleniyor")

_kilitler: dict = {}
_kilitler_kilit = threading.Lock()
_islenen: set = set()  # şu an bu süreçte işlenen dosya kimlikleri


def kilit(kullanici: str) -> threading.RLock:
    with _kilitler_kilit:
        return _kilitler.setdefault(kullanici, threading.RLock())


def kullanici_dizini(kullanici: str) -> str:
    if not KULLANICI_RE.match(kullanici or ""):
        raise Hata(400, "kullanici")
    yol = os.path.realpath(os.path.join(VERI_DIZINI, kullanici))
    if os.path.dirname(yol) != VERI_DIZINI:
        raise Hata(400, "kullanici")
    return yol


def dosya_dizini(kullanici: str) -> str:
    return os.path.join(kullanici_dizini(kullanici), "dosyalar")


def ders_gecerli(ders: str) -> str:
    if not DERS_RE.match(ders or ""):
        raise Hata(400, "ders")
    return ders


def store(kullanici: str):
    return get_vector_store(kullanici_dizini(kullanici))


# --- manifest ---

def _manifest_yolu(kullanici: str) -> str:
    return os.path.join(kullanici_dizini(kullanici), "manifest.json")


def _oku(kullanici: str) -> List[dict]:
    yol = _manifest_yolu(kullanici)
    if not os.path.exists(yol):
        return []
    with open(yol, "r", encoding="utf-8") as f:
        return json.load(f)


def _yaz(kullanici: str, kayitlar: List[dict]) -> None:
    dizin = kullanici_dizini(kullanici)
    os.makedirs(dizin, exist_ok=True)
    yol = _manifest_yolu(kullanici)
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(kayitlar, f, ensure_ascii=False)
    os.replace(gecici, yol)


def _durum(kayit: dict) -> dict:
    # Servis yeniden başladıysa yarıda kalan işleme "hata" sayılır
    if kayit["durum"] == "isleniyor" and kayit["id"] not in _islenen:
        return {**kayit, "durum": "hata", "hata": "yarim", "adim": None}
    return kayit


def gorunum(kayit: dict) -> dict:
    """Dışarı dönen alanlar (diskteki ad ve yol dönmez)."""
    k = _durum(kayit)
    return {
        "id": k["id"],
        "ad": k["ad"],
        "ders": k["ders"],
        "boyut": k["boyut"],
        "sayfa": k.get("sayfa"),
        "parca": k.get("parca"),
        "durum": k["durum"],
        "adim": k.get("adim"),
        "hata": k.get("hata"),
    }


def listele(kullanici: str, ders: Optional[str] = None) -> List[dict]:
    with kilit(kullanici):
        return [_durum(k) for k in _oku(kullanici) if ders is None or k["ders"] == ders]


def bul(kullanici: str, dosya_id: str) -> Optional[dict]:
    with kilit(kullanici):
        return next((_durum(k) for k in _oku(kullanici) if k["id"] == dosya_id), None)


def ekle(kullanici: str, kayit: dict) -> None:
    with kilit(kullanici):
        kayitlar = _oku(kullanici)
        kayitlar.append(kayit)
        _yaz(kullanici, kayitlar)


def guncelle(kullanici: str, dosya_id: str, **alanlar) -> bool:
    with kilit(kullanici):
        if not os.path.isdir(kullanici_dizini(kullanici)):
            return False
        kayitlar = _oku(kullanici)
        for k in kayitlar:
            if k["id"] == dosya_id:
                k.update(alanlar)
                _yaz(kullanici, kayitlar)
                return True
        return False


def kullanim(kullanici: str) -> tuple:
    """(dosya sayısı, toplam bayt)"""
    kayitlar = listele(kullanici)
    return len(kayitlar), sum(k["boyut"] for k in kayitlar)


# --- işleme (arka planda, kullanıcı başına sırayla) ---

_isleme_kilitleri: dict = {}


def _isleme_kilidi(kullanici: str) -> threading.Lock:
    with _kilitler_kilit:
        return _isleme_kilitleri.setdefault(kullanici, threading.Lock())


def kuyruga_al(dosya_id: str) -> None:
    """Yükleme kaydedilir kaydedilmez çağrılır; işleme başlayana kadar "işleniyor" görünür."""
    _islenen.add(dosya_id)


def isle(kullanici: str, dosya_id: str) -> None:
    """Çekirdek adımları sırayla çağırır: metin çıkarma → parçalama → embedding + indeks."""
    _islenen.add(dosya_id)
    try:
        with _isleme_kilidi(kullanici):
            kayit = bul(kullanici, dosya_id)
            if not kayit:
                return
            yol = os.path.join(dosya_dizini(kullanici), kayit["saklanan"])
            try:
                guncelle(kullanici, dosya_id, adim=0)
                metin = extract_text(yol)
                if not guncelle(kullanici, dosya_id, adim=1):
                    return
                parcalar = chunk_text(metin, source=kayit["saklanan"])
                if not parcalar:
                    guncelle(kullanici, dosya_id, durum="hata", hata="bos", adim=None)
                    return
                if not guncelle(kullanici, dosya_id, adim=2):
                    return
                vektorler = embed_texts([p.text for p in parcalar])
                with kilit(kullanici):
                    # bu arada silindiyse indekse eklenmez
                    if not bul(kullanici, dosya_id):
                        return
                    store(kullanici).add_chunks(parcalar, vektorler)
                    guncelle(kullanici, dosya_id, durum="hazir", parca=len(parcalar), adim=None)
            except Exception as e:  # içerik ya da ayrıntı loglanmaz
                log.warning("işleme hatası: %s", type(e).__name__)
                guncelle(kullanici, dosya_id, durum="hata", hata="isleme", adim=None)
    finally:
        _islenen.discard(dosya_id)


# --- silme ---

def _dosya_sil(kullanici: str, kayit: dict) -> None:
    store(kullanici).remove_source(kayit["saklanan"])
    yol = os.path.join(dosya_dizini(kullanici), kayit["saklanan"])
    if os.path.exists(yol):
        os.remove(yol)


def sil(kullanici: str, dosya_id: str) -> bool:
    with kilit(kullanici):
        kayitlar = _oku(kullanici)
        kayit = next((k for k in kayitlar if k["id"] == dosya_id), None)
        if not kayit:
            return False
        _yaz(kullanici, [k for k in kayitlar if k["id"] != dosya_id])
        _dosya_sil(kullanici, kayit)
        return True


def ders_sil(kullanici: str, ders: str) -> int:
    with kilit(kullanici):
        kayitlar = _oku(kullanici)
        silinecek = [k for k in kayitlar if k["ders"] == ders]
        if not silinecek:
            return 0
        _yaz(kullanici, [k for k in kayitlar if k["ders"] != ders])
        for k in silinecek:
            _dosya_sil(kullanici, k)
        return len(silinecek)


def kullanici_sil(kullanici: str) -> None:
    dizin = kullanici_dizini(kullanici)
    with kilit(kullanici):
        drop_vector_store(dizin)
        if os.path.isdir(dizin):
            shutil.rmtree(dizin)


def yeni_kayit(dosya_id: str, ad: str, ders: str, saklanan: str, boyut: int, sayfa: Optional[int]) -> dict:
    return {
        "id": dosya_id,
        "ad": ad,
        "ders": ders,
        "saklanan": saklanan,
        "boyut": boyut,
        "sayfa": sayfa,
        "parca": None,
        "durum": "isleniyor",
        "adim": 0,
        "hata": None,
        "olusturma": int(time.time()),
    }
