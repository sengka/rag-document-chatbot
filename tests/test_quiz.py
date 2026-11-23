"""Dede'nin Quiz/Fırtına soruları (/quiz): imza, kullanıcı ve ders izolasyonu, doğrulama, karıştırma."""
import json
import random
import secrets
import time

import pytest

from app import quiz
from conftest import DERS_A, DERS_B, basliklar, yukle


def yeni():
    """Testler veri dizinini paylaşır: her testte yeni kullanıcı kimliği."""
    return secrets.token_hex(12)


def iste(client, kullanici, ders):
    return client.post("/quiz", json={"ders": ders}, headers=basliklar(kullanici, "POST", "/quiz"))


def soru(i, parca="P1", dogru=1):
    return {
        "soru": f"Soru {i}?",
        "siklar": [f"S{i}-a", f"S{i}-b", f"S{i}-c", f"S{i}-d"],
        "dogru": dogru,
        "neden": f"Neden {i}",
        "parca": parca,
    }


def hazir_bekle(client, kullanici):
    for _ in range(50):
        from conftest import listele

        d = listele(client, kullanici).json()["dosyalar"]
        if d and all(x["durum"] == "hazir" for x in d):
            return
        time.sleep(0.05)


def test_imzasiz_401(client):
    assert client.post("/quiz", json={"ders": DERS_A}).status_code == 401


def test_not_yoksa_yok(client, groq):
    r = iste(client, yeni(), DERS_A)
    assert r.json() == {"yok": True}
    assert groq.cagrilar == []


def test_yalniz_kendi_ve_dersin_notlari(client, groq):
    A, B = yeni(), yeni()
    yukle(client, A, DERS_A, "a-mat.txt", "Türev anlık değişim hızıdır ALANOTU.".encode())
    yukle(client, A, DERS_B, "a-fiz.txt", "Kuvvet kütle çarpı ivme ABASKADERS.".encode())
    yukle(client, B, DERS_A, "b-mat.txt", "İntegral alan hesabıdır BNOTU.".encode())
    hazir_bekle(client, A)
    hazir_bekle(client, B)
    groq.cevap = json.dumps({"sorular": [soru(i) for i in range(5)]})
    r = iste(client, A, DERS_A)
    assert r.status_code == 200
    sorular = r.json()["sorular"]
    assert len(sorular) == 5
    giden = json.dumps(groq.cagrilar[-1]["messages"], ensure_ascii=False)
    assert "ALANOTU" in giden
    assert "ABASKADERS" not in giden and "BNOTU" not in giden
    msgs = groq.cagrilar[-1]["messages"]
    assert msgs[0]["role"] == "system" and "talimat" in msgs[0]["content"]
    assert groq.cagrilar[-1]["response_format"] == {"type": "json_object"}
    k = sorular[0]["kaynak"]
    assert k["etiket"] == "a-mat.txt · parça 1" and "ALANOTU" in k["alinti"]
    for s in sorular:
        assert set(s) == {"soru", "siklar", "dogru", "neden", "kaynak"}


def test_az_gecerli_soru_502(client, groq):
    A = yeni()
    yukle(client, A, DERS_A, "x.txt", "Fotosentez ışık enerjisi.".encode())
    hazir_bekle(client, A)
    bozuk = [soru(0), soru(1), soru(2), {**soru(3), "siklar": ["a", "a", "b", "c"]}, {**soru(4), "parca": "P9"}]
    groq.cevap = json.dumps({"sorular": bozuk})
    r = iste(client, A, DERS_A)
    assert r.status_code == 502 and r.json() == {"kod": "cevap"}
    groq.cevap = "JSON değil"
    assert iste(client, A, DERS_A).status_code == 502


@pytest.mark.parametrize(
    "bozuk",
    [
        {"siklar": ["a", "b", "c"]},
        {"dogru": 4},
        {"dogru": True},
        {"dogru": "1"},
        {"soru": ""},
        {"soru": "x" * 201},
        {"neden": None},
        {"siklar": ["a", "b", "c", "x" * 81]},
        {"parca": "P7"},
    ],
)
def test_dogrulama_gecersiz_soruyu_atar(bozuk):
    assert quiz.dogrula(json.dumps({"sorular": [{**soru(0), **bozuk}]}), ["P1"]) == []


def test_karistirma_dogru_sikki_korur():
    rnd = random.Random(3)
    for d in range(4):
        s = quiz.dogrula(json.dumps({"sorular": [soru(0, dogru=d)]}), ["P1"], rnd)[0]
        assert s["siklar"][s["dogru"]] == f"S0-{'abcd'[d]}"
        assert sorted(s["siklar"]) == [f"S0-{c}" for c in "abcd"]


def test_parca_secimi_yalniz_verilen_kaynaklar():
    class P:
        def __init__(self, s, i):
            self.source, self.chunk_index, self.text = s, i, f"{s}-{i}"

    class St:
        chunks = [P("x", i) for i in range(10)] + [P("y", i) for i in range(2)] + [P("z", 0)]

    sec = quiz.parcalari_sec(St(), ["x", "y"], random.Random(1))
    assert len(sec) == 6
    assert {p.source for p in sec} == {"x", "y"}
