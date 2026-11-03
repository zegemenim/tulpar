"""Taslak kalitesi için üç araç (model gerektirmez):
1) benzer_cevaplar: gelen mesaja BENZER geçmiş durumları bulur ("şunu yazdılar -> sahibi şöyle cevap verdi" çiftleri).
2) uslup_ozeti: sahibin bu kişiye yazış alışkanlıklarını sayılarla çıkarır (uzunluk, küçük harf, noktalama, emoji).
3) uydurma_var: taslakta bağlamda geçmeyen saat/sayı var mı kontrol eder."""
import math
import re
import statistics
import time
from collections import Counter

import db

_onbellek = {"zaman": 0.0, "ciftler": []}
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
_SAAT = re.compile(r"\b\d{1,2}[:.]\d{2}\b|\b\d{1,2}\s*(?:da|de|ta|te|'da|'de)\b")


def _ngram(metin):
    t = " " + re.sub(r"\s+", " ", metin.lower().strip()) + " "
    return Counter(t[i:i + 3] for i in range(len(t) - 2))  # harf 3'lüleri: Türkçe ekler için kelime eşleşmesinden sağlam


def _kosinus(a, b):
    ortak = sum(v * b[k] for k, v in a.items() if k in b)
    if not ortak:
        return 0.0
    return ortak / (math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values())))


def ciftler():
    """(gelen metin, sahibin cevabı, sohbet_id) çiftleri; sahibin mesajından hemen önceki karşı taraf mesajları. 10 dk önbellek."""
    if time.time() - _onbellek["zaman"] < 600 and _onbellek["ciftler"]:
        return _onbellek["ciftler"]
    satirlar = db.oku("SELECT sohbet_id, benden, metin, zaman FROM mesajlar WHERE metin IS NOT NULL AND metin!='' "
                      "ORDER BY sohbet_id, zaman")
    sonuc, gelen, onceki = [], [], None
    for s in satirlar:
        if s["sohbet_id"] != onceki:
            gelen, onceki = [], s["sohbet_id"]
        if not s["benden"]:
            gelen = gelen[-2:] + [s["metin"]]
        elif gelen and len(s["metin"]) < 300:
            g = " ".join(gelen)
            sonuc.append((g, s["metin"], s["sohbet_id"], _ngram(g)))
            gelen = []
    _onbellek.update(zaman=time.time(), ciftler=sonuc)
    return sonuc


def benzer_cevaplar(sohbet_id, gelen_metinler, n=8):
    """Gelen mesaja en benzer geçmiş çiftler; aynı kişiyle olanlara öncelik verilir."""
    sorgu = _ngram(" ".join(gelen_metinler))
    puanli = []
    for g, c, sid, ng in ciftler():
        p = _kosinus(sorgu, ng)
        if p > 0.25:
            puanli.append((p + (0.15 if sid == sohbet_id else 0.0), g, c))
    puanli.sort(key=lambda x: -x[0])
    goruldu, sonuc = set(), []
    for _, g, c in puanli:
        if (g, c) not in goruldu:
            goruldu.add((g, c))
            sonuc.append((g, c))
    return sonuc[:n]


def uslup_ozeti(sohbet_id):
    """Sahibin bu kişiye yazış biçimi (sayılarla). Yeterli veri yoksa boş döner."""
    ms = [m["metin"] for m in db.oku("SELECT metin FROM mesajlar WHERE benden=1 AND sohbet_id=? AND metin!='' ORDER BY zaman DESC LIMIT 80",
                                     sohbet_id)]
    if len(ms) < 10:
        return ""
    uz = statistics.median(len(m.split()) for m in ms)
    kucuk = sum(m[0].islower() for m in ms) / len(ms)
    nokta = sum(m.rstrip()[-1] in ".!" for m in ms) / len(ms)
    emoji = sum(bool(_EMOJI.search(m)) for m in ms) / len(ms)
    return (f"Sahibin bu kişiye yazış alışkanlığı: mesaj uzunluğu genelde {uz:.0f} kelime; %{kucuk * 100:.0f} küçük harfle başlıyor; "
            f"%{nokta * 100:.0f} nokta/ünlemle bitiyor; %{emoji * 100:.0f} emoji var. Buna uy.")


def uydurma_var(taslak_metinleri, baglam):
    """Taslakta, konuşmada geçmeyen saat/gün-saat ifadesi varsa o ifadeleri döner."""
    b = baglam.lower()
    bulunan = []
    for t in taslak_metinleri:
        for m in _SAAT.findall(t.lower()):
            if m not in b:
                bulunan.append(m)
    return bulunan
