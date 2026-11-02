"""Mindshire'dan gelen isteklerin doğrulanması.

Express her isteği paylaşılan ARI_GIZLI anahtarıyla imzalar:
    X-Ms-Kullanici: <userId>   X-Ms-Zaman: <unix saniye>
    X-Ms-Imza: hex(HMAC-SHA256(ARI_GIZLI, "zaman\\nMETOD\\nyol?sorgu\\nuserId"))
Kullanıcı kimliği yalnız buradan gelir; gövde ya da sorgudaki hiçbir alan kimlik sayılmaz.
"""
import hashlib
import hmac
import re
import time

from fastapi import HTTPException, Request

from app.config import ARI_GIZLI

ZAMAN_PENCERESI = 60  # saniye
KULLANICI_RE = re.compile(r"^[a-f0-9]{24}$")


class Hata(HTTPException):
    """İstemciye yalnız sabit bir kod döner; ayrıntı yok."""

    def __init__(self, status: int, kod: str):
        super().__init__(status_code=status, detail=kod)


def imza(gizli: str, zaman: str, metod: str, yol: str, kullanici: str) -> str:
    mesaj = f"{zaman}\n{metod}\n{yol}\n{kullanici}".encode("utf-8")
    return hmac.new(gizli.encode("utf-8"), mesaj, hashlib.sha256).hexdigest()


def istek_yolu(request: Request) -> str:
    sorgu = request.scope.get("query_string", b"").decode("latin-1")
    return request.url.path + ("?" + sorgu if sorgu else "")


def imzali_kullanici(request: Request) -> str:
    """FastAPI bağımlılığı: imzayı doğrular, userId'yi döndürür."""
    kullanici = request.headers.get("x-ms-kullanici", "")
    zaman = request.headers.get("x-ms-zaman", "")
    gelen = request.headers.get("x-ms-imza", "")
    if not (kullanici and zaman and gelen) or not zaman.isdigit():
        raise Hata(401, "imza")
    if abs(time.time() - int(zaman)) > ZAMAN_PENCERESI:
        raise Hata(401, "imza")
    beklenen = imza(ARI_GIZLI, zaman, request.method, istek_yolu(request), kullanici)
    if not hmac.compare_digest(beklenen, gelen):
        raise Hata(401, "imza")
    if not KULLANICI_RE.match(kullanici):
        raise Hata(400, "kullanici")
    return kullanici
