"""Testler gerçek embedding modelini ve Groq'u kullanmaz.

- sentence_transformers yerine kelime torbası (hash) ile 384 boyutlu sahte model
- Groq istemcisi yerine çağrıları kaydeden sahte istemci
"""
import hashlib
import os
import sys
import tempfile
import time
import types

import numpy as np
import pytest

GIZLI = "t" * 40
os.environ["ARI_GIZLI"] = GIZLI
os.environ["ARI_VERI_DIZINI"] = tempfile.mkdtemp(prefix="ari-test-")
os.environ["GROQ_API_KEY"] = "test"


class _SahteModel:
    def __init__(self, *_a, **_k):
        pass

    def encode(self, texts, **_k):
        out = np.zeros((len(texts), 384), dtype="float32")
        for i, t in enumerate(texts):
            for w in t.lower().split():
                h = int(hashlib.md5(w.strip(".,:;!?\"'").encode()).hexdigest(), 16)
                out[i, h % 384] += 1.0
            n = np.linalg.norm(out[i])
            if n:
                out[i] /= n
        return out


_st = types.ModuleType("sentence_transformers")
_st.SentenceTransformer = _SahteModel
sys.modules.setdefault("sentence_transformers", _st)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app import rag  # noqa: E402
from app.guvenlik import imza  # noqa: E402
from app.main import app  # noqa: E402

A = "a" * 24
B = "b" * 24
DERS_A = "1" * 24
DERS_B = "2" * 24


class SahteGroq:
    def __init__(self):
        self.cagrilar = []
        self.cevap = "Notuna göre cevap."
        self.hata = None
        self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.cagrilar.append(kw)
        if self.hata:
            raise self.hata
        msg = types.SimpleNamespace(content=self.cevap)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])


@pytest.fixture()
def groq(monkeypatch):
    sahte = SahteGroq()
    monkeypatch.setattr(rag, "get_client", lambda: sahte)
    return sahte


@pytest.fixture()
def client():
    return TestClient(app)


def basliklar(kullanici, metod, yol, zaman=None, gizli=GIZLI):
    zaman = str(int(time.time()) if zaman is None else zaman)
    return {
        "X-Ms-Kullanici": kullanici,
        "X-Ms-Zaman": zaman,
        "X-Ms-Imza": imza(gizli, zaman, metod, yol, kullanici),
    }


def yukle(client, kullanici, ders, ad, icerik: bytes):
    from urllib.parse import quote

    yol = f"/upload?ders={ders}"
    h = basliklar(kullanici, "POST", yol)
    h["X-Dosya-Adi"] = quote(ad)
    h["Content-Type"] = "application/octet-stream"
    return client.post(yol, content=icerik, headers=h)


def sor(client, kullanici, ders, soru):
    return client.post("/chat", json={"soru": soru, "ders": ders}, headers=basliklar(kullanici, "POST", "/chat"))


def listele(client, kullanici, ders=None):
    yol = "/files" + (f"?ders={ders}" if ders else "")
    return client.get(yol, headers=basliklar(kullanici, "GET", yol))
