"""Claude Code köprüsü (HP tarafı): "X projesinde şunu yap" isteğinde hangi projenin klasörünü ve hangi konuşmasını kullanacağını
seçer, sahibi onaylarsa Mac ajanına gönderir (Claude Code Mac'te çalışır: projeler ve konuşmalar orada), sonucu sohbete yazar.
Proje: önce isimden (ASCII katlama), bulunamazsa model; konuşma: başlıkla örtüşen, yoksa en son; "yeni konuşma" denirse sıfırdan.
Mod: inceleme soruları 'plan' (dosya değiştirmez), diğerleri 'duzenle'. Push/silme/sudo ajan tarafında yasak."""
import json
import re
import time

import cihaz
from kuyruk import Is, log

_onbellek = {"zaman": 0, "veri": []}
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
YENI = re.compile(r"(?i)yeni (bir )?(konuşma|sohbet|oturum)|sıfırdan|baştan başla|temiz bir")
INCELEME = re.compile(r"(?i)incele|\boku\b|göster|listele|bak(ar mısın)?\b|kontrol et|neden|araştır|açıkla|review|durum|nedir|ne yapıyor|rapor|özetle|bul\b")
DEGISTIR = re.compile(r"(?i)düzelt(?!me)|ekle(?!me)|yap\b|değiştir(?!me)|yaz\b|kur\b|sil\b|güncelle|oluştur|geliştir|çöz|taşı|yeniden adlandır|refactor|implement|fix")


def _kat(s):
    return re.sub(r"[^a-z0-9 ]+", " ", (s or "").translate(_TR).lower())


def projeler(taze=False):
    """Mac'teki Claude Code projeleri: [{ad, klasor, aciklama, oturumlar}]; 2 dk önbellek. Mac kapalıysa []."""
    if not taze and time.time() - _onbellek["zaman"] < 120 and _onbellek["veri"]:
        return _onbellek["veri"]
    sonuc = cihaz._ajana_gonder("mac", "claude_projeler", None)
    try:
        _onbellek.update(zaman=time.time(), veri=json.loads(sonuc))
    except (TypeError, ValueError):
        return _onbellek["veri"]  # Mac cevap vermedi: eski liste
    return _onbellek["veri"]


def proje_sec(metin, ipucu, liste, model_sor=None):
    """(proje|None, sebep). Önce adın geçtiği proje; birden çoksa en uzun ad; hiç yoksa model."""
    t = " " + _kat(f"{ipucu or ''} {metin}") + " "
    eslesen = [p for p in liste if re.search(rf"\b{re.escape(_kat(p['ad']).strip())}", t)]
    if eslesen:
        en_uzun = max(len(p["ad"]) for p in eslesen)
        eslesen = [p for p in eslesen if len(p["ad"]) == en_uzun]
        return (eslesen[0], "adı geçti") if len(eslesen) == 1 else (None, "birden çok proje eşleşti")
    if model_sor and liste:
        ozet = "\n".join(f"- {p['ad']}: {p['aciklama']} (son konuşmalar: {'; '.join(o['baslik'][:50] for o in p['oturumlar'][:3])})" for p in liste)
        k = model_sor('Sahibinin iş isteği hangi projeyle ilgili? Projeler verilir. SADECE JSON: {"proje": "tam proje adı" veya null (emin değilsen null)}',
                      f"Projeler:\n{ozet}\n\nİstek: {metin}") or {}
        for p in liste:
            if p["ad"] == k.get("proje"):
                return p, "model seçti"
    return None, "proje belirlenemedi"


def oturum_sec(proje, metin):
    """Konuşma: 'yeni konuşma' dendiyse None; başlıkla en çok kelime örtüşen; örtüşme yoksa en son kullanılan."""
    if YENI.search(metin) or not proje["oturumlar"]:
        return None
    kelimeler = {k for k in _kat(metin).split() if len(k) >= 4}
    en = max(proje["oturumlar"], key=lambda o: (len(kelimeler & set(_kat(o["baslik"]).split())), o["zaman"]))
    return en


def mod_sec(metin):
    return "plan" if INCELEME.search(metin) and not DEGISTIR.search(metin) else "duzenle"


def hazirla(metin, ipucu=None, model_sor=None):
    """Onay kartı için: {proje, klasor, oturum, oturum_baslik, mod, gorev} ya da {hata}."""
    liste = projeler()
    if not liste:
        return {"hata": "Mac'teki Claude Code projelerine ulaşamadım (Mac kapalı ya da ajan çalışmıyor)."}
    p, sebep = proje_sec(metin, ipucu, liste, model_sor)
    if not p:
        return {"hata": f"Hangi projeyle ilgili olduğunu anlayamadım ({sebep}). Projeler: " + ", ".join(x["ad"] for x in liste) + ". Proje adını söyler misin?"}
    o = oturum_sec(p, metin)
    return {"proje": p["ad"], "klasor": p["klasor"], "oturum": o and o["id"], "oturum_baslik": o["baslik"] if o else None,
            "mod": mod_sec(metin), "gorev": metin.strip()[:1500]}


def baslat(veri, sohbet=None, onay=None):
    """Onaylanan işi Mac'te başlatır; metin sonuç döner ('baslatildi <id>' ya da hata)."""
    sonuc = cihaz._ajana_gonder("mac", "claude_kod", {**veri, "sohbet": sohbet, "onay": onay})
    log(f"CLAUDE CODE | {veri.get('proje')} | {veri.get('mod')} | oturum={str(veri.get('oturum'))[:8]} | {sonuc}")
    return sonuc or "Mac bağlı değil"
