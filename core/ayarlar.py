"""Sunucu ayarları: tek yerde, açıklamalı. ~/tulpar/veri/ayarlar.json'da saklanır; değişiklik anında geçerli olur.
Değiştirme: izleme ekranında 's' (tulpar-izle) veya uygulamadan (/ayarlar). Kodda: ayarlar.al("anahtar")."""
import json
import os
import pathlib
import threading

YOL = pathlib.Path.home() / "tulpar/veri/ayarlar.json"

# anahtar: (bölüm, kısa ad, açıklama, varsayılan, en az, en çok)
SEMA = {
    "grup_toplama_sn": ("WhatsApp", "Grup toplama süresi (sn)",
                        "Grupta art arda gelen mesajlar, grup bu kadar susunca tek seferde değerlendirilir.", 60, 5, 600),
    "birebir_toplama_sn": ("WhatsApp", "Birebir toplama süresi (sn)",
                           "Birebir sohbette art arda gelenler bu kadar sessizlikten sonra birlikte değerlendirilir.", 20, 0, 300),
    "taslak_bekleme_sn": ("WhatsApp", "Taslak bekleme süresi (sn)",
                          "Kişi bu kadar susunca cevap taslağı hazırlanır (art arda mesajlar tek taslakta).", 90, 10, 900),
    "baglam_mesaj": ("WhatsApp", "Değerlendirmede bağlam (mesaj)",
                     "Bir mesaj değerlendirilirken o sohbetin son kaç mesajı bağlam olarak okunur.", 15, 3, 60),
    "sohbet_gecmis_mesaj": ("Konuşma", "Sohbette hatırlanan mesaj",
                            "Tulpar'la sohbette modele verilen son mesaj sayısı; daha eskisi özetlenir.", 16, 4, 60),
    "whisper_bosta_sn": ("Ses", "Whisper bellekte kalma (sn)",
                         "Mikrofona basılınca Whisper hemen belleğe alınır; son kullanımdan bu kadar sn sonra atılır (RAM Gemma'ya kalsın).", 3, 0, 3600),
    "reddedilen_sakla_gun": ("Uygulama", "Reddedilenleri saklama (gün)",
                             "Reddettiğin onaylar bu kadar gün 'Reddedilenler'de durur, sonra silinir.", 7, 1, 90),
    "ekran_bosta_dk": ("İkinci ekran", "Kapanma süresi (dk)",
                       "İkinci ekranda görüntü bu kadar dakika değişmezse ekran kapanır.", 30, 1, 240),
}

_onbellek, _zaman, _kilit = {}, 0.0, threading.Lock()


def hepsi():
    global _onbellek, _zaman
    with _kilit:
        try:
            z = os.path.getmtime(YOL)
            if z != _zaman:
                _onbellek, _zaman = json.loads(YOL.read_text()), z
        except (FileNotFoundError, json.JSONDecodeError):
            _onbellek = {}
        return {k: _onbellek.get(k, v[3]) for k, v in SEMA.items()}


def al(anahtar):
    return hepsi()[anahtar]


def yaz(anahtar, deger):
    if anahtar not in SEMA:
        raise KeyError(anahtar)
    _, _, _, vars_, en_az, en_cok = SEMA[anahtar]
    deger = type(vars_)(deger)
    if not en_az <= deger <= en_cok:
        raise ValueError(f"{en_az} ile {en_cok} arasında olmalı")
    with _kilit:
        try:
            mevcut = json.loads(YOL.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            mevcut = {}
        mevcut[anahtar] = deger
        YOL.write_text(json.dumps(mevcut, ensure_ascii=False, indent=1))
    return deger


def liste():
    d = hepsi()
    return [{"anahtar": k, "bolum": b, "ad": a, "aciklama": ac, "deger": d[k], "varsayilan": v, "en_az": mn, "en_cok": mx}
            for k, (b, a, ac, v, mn, mx) in SEMA.items()]
