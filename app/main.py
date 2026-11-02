"""Mindshire Arı yan servisi.

Yalnız 127.0.0.1'de çalışır; bütün uçlar (/saglik hariç) Express'in imzaladığı userId ister.
ARI_GIZLI yoksa servis başlamaz. Eski bağımsız arayüz (/, /static, /docs) bu modda kapalıdır.
"""
import logging
import os
import uuid
from typing import Optional
from urllib.parse import unquote

from fastapi import BackgroundTasks, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import kovan, yukleme
from app.config import ARI_GIZLI, MAKS_DOSYA_BAYT, MAKS_SORU
from app.guvenlik import Hata, imzali_kullanici
from app.rag import BULUNAMADI, ask

if len(ARI_GIZLI) < 32:
    raise RuntimeError("ARI_GIZLI ayarlı değil (en az 32 karakter); Arı servisi başlatılmadı.")

log = logging.getLogger("ari")
if not log.handlers:
    # "ari.*" günlükleri (ör. işleme hatasının traceback'i) stderr'e; Windows'ta UTF-8 için
    # PYTHONUTF8=1 (scripts/ikiServis.js çocuk sürece verir).
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)

app = FastAPI(title="Mindshire Arı", docs_url=None, redoc_url=None, openapi_url=None)

ALINTI = 400  # kaynak alıntısı en fazla bu kadar karakter


@app.exception_handler(StarletteHTTPException)
async def _http_hatasi(request: Request, exc: StarletteHTTPException):
    kod = exc.detail if isinstance(exc.detail, str) and exc.detail.isidentifier() else "istek"
    return JSONResponse({"kod": kod}, status_code=exc.status_code)


@app.exception_handler(RequestValidationError)
async def _gecersiz(request: Request, exc: RequestValidationError):
    return JSONResponse({"kod": "istek"}, status_code=400)


@app.exception_handler(Exception)
async def _beklenmeyen(request: Request, exc: Exception):
    log.error("beklenmeyen hata: %s", type(exc).__name__)
    return JSONResponse({"kod": "ic"}, status_code=500)


@app.get("/saglik")
def saglik():
    return {"durum": "iyi"}


@app.get("/files")
def list_files(ders: Optional[str] = None, kullanici: str = Depends(imzali_kullanici)):
    if ders is not None:
        kovan.ders_gecerli(ders)
    return {"dosyalar": [kovan.gorunum(k) for k in kovan.listele(kullanici, ders)]}


@app.get("/files/{dosya_id}")
def file_status(dosya_id: str, kullanici: str = Depends(imzali_kullanici)):
    kayit = kovan.bul(kullanici, dosya_id)
    if not kayit:
        raise Hata(404, "bulunamadi")
    return {"dosya": kovan.gorunum(kayit)}


@app.delete("/files/{dosya_id}")
def delete_file(dosya_id: str, kullanici: str = Depends(imzali_kullanici)):
    if not kovan.sil(kullanici, dosya_id):
        raise Hata(404, "bulunamadi")
    return {"silindi": True}


@app.delete("/dersler/{ders}")
def delete_course(ders: str, kullanici: str = Depends(imzali_kullanici)):
    kovan.ders_gecerli(ders)
    return {"silinen": kovan.ders_sil(kullanici, ders)}


@app.delete("/kullanici")
def delete_user(kullanici: str = Depends(imzali_kullanici)):
    kovan.kullanici_sil(kullanici)
    return {"silindi": True}


@app.post("/upload", status_code=202)
async def upload_file(
    request: Request,
    background: BackgroundTasks,
    ders: str = "",
    kullanici: str = Depends(imzali_kullanici),
):
    kovan.ders_gecerli(ders)
    ad = yukleme.temiz_ad(unquote(request.headers.get("x-dosya-adi", "")))
    uzunluk = request.headers.get("content-length", "")
    if uzunluk.isdigit() and int(uzunluk) > MAKS_DOSYA_BAYT:
        raise Hata(413, "boyut")
    yukleme.kota_denetle(*kovan.kullanim(kullanici), int(uzunluk) if uzunluk.isdigit() else 0)

    dizin = kovan.dosya_dizini(kullanici)
    os.makedirs(dizin, exist_ok=True)
    dosya_id = uuid.uuid4().hex
    uzanti = os.path.splitext(ad)[1].lower()
    saklanan = dosya_id + uzanti  # diskte kullanıcının verdiği ad hiç kullanılmaz
    gecici = os.path.join(dizin, saklanan + ".yukleniyor")
    toplam = 0
    try:
        with open(gecici, "wb") as f:
            async for parca in request.stream():
                toplam += len(parca)
                if toplam > MAKS_DOSYA_BAYT:
                    raise Hata(413, "boyut")
                f.write(parca)
        if toplam == 0:
            raise Hata(400, "bos")
        sayfa = yukleme.icerik_denetle(gecici, uzanti)
        with kovan.kilit(kullanici):
            yukleme.kota_denetle(*kovan.kullanim(kullanici), toplam)  # aynı anda iki yükleme
            os.replace(gecici, os.path.join(dizin, saklanan))
            kayit = kovan.yeni_kayit(dosya_id, ad, ders, saklanan, toplam, sayfa)
            kovan.ekle(kullanici, kayit)
    finally:
        if os.path.exists(gecici):
            os.remove(gecici)

    kovan.kuyruga_al(dosya_id)
    background.add_task(kovan.isle, kullanici, dosya_id)
    return {"dosya": kovan.gorunum(kayit)}


class SoruIstegi(BaseModel):
    soru: str
    ders: str


@app.post("/chat")
def chat(istek: SoruIstegi, kullanici: str = Depends(imzali_kullanici)):
    soru = istek.soru.strip()
    if not soru or len(soru) > MAKS_SORU:
        raise Hata(400, "soru")
    kovan.ders_gecerli(istek.ders)

    hazir = [k for k in kovan.listele(kullanici, istek.ders) if k["durum"] == "hazir"]
    if not hazir:
        return {"bulundu": False, "cevap": "", "kaynaklar": []}
    adlar = {k["saklanan"]: k["ad"] for k in hazir}

    try:
        sonuc = ask(soru, kovan.store(kullanici), sources=list(adlar))
    except Exception as e:  # Groq ya da model hatası; ayrıntı istemciye gitmez
        log.warning("cevap üretilemedi: %s", type(e).__name__)
        raise Hata(502, "cevap")

    cevap = (sonuc.get("answer") or "").strip()
    parcalar = [p for p in sonuc.get("chunks", []) if p["source"] in adlar]
    if not parcalar or cevap.startswith(BULUNAMADI):
        return {"bulundu": False, "cevap": "", "kaynaklar": []}

    kaynaklar, gorulen = [], set()
    for p in parcalar:
        anahtar = (p["source"], p["chunk_index"])
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        metin = p["text"]
        kaynaklar.append({
            "etiket": f"{adlar[p['source']]} · parça {p['chunk_index'] + 1}",
            "alinti": metin[:ALINTI] + ("…" if len(metin) > ALINTI else ""),
        })
    return {"bulundu": True, "cevap": cevap, "kaynaklar": kaynaklar}
