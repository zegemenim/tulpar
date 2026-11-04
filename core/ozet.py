"""WhatsApp özeti: son saatlerde hangi sohbette ne konuşuldu, sahibinin cevaplaması gereken var mı. Arka planda, sohbet başına
tek model çağrısıyla hazırlanır (yavaş model: sırayla); sonuç veri/ozet.json'da durur, uygulama/menü oradan okur.
Kapalı (haric) sohbetler hiç işlenmez."""
import datetime
import json
import pathlib
import re
import threading
import time
import zoneinfo

import db
import sahip
from egitim_verisi import haric
from kuyruk import Is, log

DOSYA = pathlib.Path.home() / "tulpar/veri/ozet.json"
_durum = {"calisiyor": False}
_kilit = threading.Lock()

SISTEM = sahip.doldur(
    "Sen Tulpar'sın. {SAHIP_TAM} (\"sen\") için bir WhatsApp sohbetini özetliyorsun. Çıktıyı sahibi okuyacak; ona 'sen' diye hitap et "
    "('Ahmet senden rapor istedi', 'sen yarın gelebileceğini söyledin').\n"
    "ÖZET KURALLARI:\n"
    "- 1-2 kısa cümle. SOMUT ol: kim, ne istedi/karar verdi, hangi tarih/saat/yer/rakam. Ad ve sayıları konuşmadan aynen al.\n"
    "- YASAK boş kalıplar: 'şakalaşıyorlar', 'sohbet ediyorlar', 'tartışıyor(lar)', 'konuşuyorlar', 'muhabbet'; grupta konu varsa çıkan bilgiyi yaz ('Vizede flowchart ve syntax hatası soruları çıkacakmış'). Önemli bir şey yoksa tam olarak şunu yaz: "
    "'Gündelik sohbet, önemli bir şey yok.' (istersen konuyu 2-3 kelimeyle ekle: 'Gündelik sohbet (maç, yemek), önemli bir şey yok.')\n"
    "- Saat, tarih, yer ve buluşma ANCAK mesajda aynen yazıyorsa geçer; mesaj başındaki [SS:DD] gönderim saatidir, buluşma saati değildir, özete yazma.\n"
    "- Konuşmada olmayanı UYDURMA, yorum katma, tahmin yürütme. Mesaj yoksa/anlaşılmıyorsa özetleme, ozet=null yaz.\n"
    "- Duyuru, tarih, son gün, toplantı, ödev, ödeme, karar varsa mutlaka belirt.\n"
    "CEVAP_GEREKLI = sahibinin cevap vermesi, bir şey yapması ya da karar vermesi gerekiyorsa true. Selamlaşma, teşekkür, 'tamam', tepki, "
    "çıkartma, herkese giden genel duyuru, sahibinin zaten cevapladığı soru → false. Gruplarda yalnızca sahibe doğrudan hitap/soru/görev "
    "varsa true. 'bu sohbetin bilgileri' bölümündeki ipuçlarını kullan.\n"
    "ONEM: yuksek = sahibin işi/sorumluluğu, para, tarih, acil; orta = bilmesi iyi olur; dusuk = gündelik.\n"
    'SADECE JSON: {"ozet": "...", "cevap_gerekli": true|false, "ne": "sahibin yapacağı şey tek cümle, yoksa null", "onem": "yuksek|orta|dusuk"}'
)

_YER = re.compile(r"^\[(çıkartma|video|fotoğraf|ses|belge|konum|kişi|gif|anket)[^\]]*\]$", re.I)
_BILGI = re.compile(r"\?|\d|https?://|toplant|ödev|sınav|son gün|lütfen|rica|yarın|bugün|akşam|saat|duyuru|önemli|gelecek|gelir misin|yapar mısın|atar mısın", re.I)
TZ = zoneinfo.ZoneInfo("Europe/Istanbul")
SAYAC = {"ozet_en_cok_mesaj": 60}


def oku():
    try:
        return json.loads(DOSYA.read_text())
    except (FileNotFoundError, ValueError):
        return {"zaman": 0, "sohbetler": [], "hazirlaniyor": _durum["calisiyor"]}


def _anma(metin):
    t = metin.lower()
    return any(re.search(rf"\b{re.escape(a)}", t) for a in sahip.ADLAR)


def _sohbetler(saat):
    """Son `saat` saatte karşı taraftan mesaj gelen sohbetler (kapalılar hariç) + sahibe ait ipuçları, öncelik sırasıyla."""
    kapali = haric()
    simdi = time.time()
    satirlar = db.oku("SELECT id, sohbet_id, sohbet_adi, grup, benden, gonderen_adi, metin, alinti_id, zaman FROM mesajlar "
                      "WHERE zaman > ? AND metin IS NOT NULL AND metin!='' ORDER BY zaman", simdi - saat * 3600)
    benim = {s["id"] for s in satirlar if s["benden"]}
    gruplar = {}
    for s in satirlar:
        if s["sohbet_id"] in kapali or s["sohbet_id"].endswith(("@newsletter", "@broadcast")):
            continue
        g = gruplar.setdefault(s["sohbet_id"], {"ad": s["sohbet_adi"], "grup": s["grup"], "mesajlar": [], "gelen": 0, "anma": 0, "alinti": 0})
        g["mesajlar"].append(s)
        if not s["benden"]:
            g["gelen"] += 1
            g["anma"] += _anma(s["metin"])
            g["alinti"] += s["alinti_id"] in benim
    liste = []
    for g in gruplar.values():
        if not g["gelen"]:
            continue
        son = g["mesajlar"][-1]
        g["bekliyor"] = not son["benden"]  # son söz karşı tarafta
        g["sinyal"] = (g["anma"] + g["alinti"] > 0) or (not g["grup"] and g["bekliyor"])
        g["oncelik"] = (0 if g["sinyal"] else 1 if not g["grup"] else 2 if len(g["mesajlar"]) <= 15 else 3, -son["zaman"])
        liste.append(g)
    return sorted(liste, key=lambda g: g["oncelik"])


def _secili(mesajlar, en_cok):
    """Gürültüyü (çıkartma, tek harf, yer tutucu) at; fazla uzunsa bilgi taşıyanları ve son mesajları tut, sırayı koru."""
    temiz = [m for m in mesajlar if not _YER.match(m["metin"].strip()) and len(m["metin"].strip()) > 2]
    if len(temiz) <= en_cok:
        return temiz
    son = temiz[-10:]
    kalan = sorted(temiz[:-10], key=lambda m: -(len(m["metin"]) // 25 + 3 * bool(_BILGI.search(m["metin"])) + 2 * _anma(m["metin"])))
    tut = {id(m) for m in son + kalan[:en_cok - 10]}
    return [m for m in temiz if id(m) in tut]


def _metin(g):
    secili = _secili(g["mesajlar"], SAYAC["ozet_en_cok_mesaj"] if g["sinyal"] or not g["grup"] else 35)
    satirlar = [f"[{datetime.datetime.fromtimestamp(m['zaman'], TZ):%H:%M}] {sahip.AD + ' (sen)' if m['benden'] else m.get('gonderen_adi') or g['ad']}: {m['metin'][:300]}"
                for m in secili]
    ipucu = [f"{'Grup' if g['grup'] else 'Birebir sohbet'}, son 24 saatte {len(g['mesajlar'])} mesaj" + (f" (aşağıda {len(secili)} tanesi var)" if len(secili) < len(g["mesajlar"]) else ""),
             "Sana adınla hitap eden/alıntılayan mesaj var" if g["anma"] + g["alinti"] else "Sana doğrudan hitap eden mesaj yok",
             "Son mesaj karşı taraftan, sen henüz cevap vermedin" if g["bekliyor"] else "Son mesajı sen yazdın"]
    return f"Sohbet: {g['ad']}\nBu sohbetin bilgileri: " + "; ".join(ipucu) + "\n\n" + "\n".join(satirlar)


def hazirla(kuyruk, saat=24, en_cok=20):
    """Özeti baştan hazırlar (arka planda çağrılır). Her sohbet bitince dosyaya yazılır: uygulama ilerlemeyi görür."""
    with _kilit:
        if _durum["calisiyor"]:
            return
        _durum["calisiyor"] = True
    try:
        liste = _sohbetler(saat)[:en_cok]
        sonuc = {"zaman": time.time(), "saat": saat, "hazirlaniyor": True, "sohbetler": [], "toplam": len(liste)}
        for g in liste:
            k = kuyruk.ekle(Is("komut", SISTEM, _metin(g), aciklama=f"WhatsApp özeti: {g['ad']}")).bekle(900) or {}
            if not k.get("ozet"):
                continue
            gerekli = bool(k.get("cevap_gerekli"))
            if g["grup"] and not g["sinyal"]:
                gerekli = False  # gruplarda sahibe hitap yoksa cevap beklenmez
            if not g["bekliyor"]:
                gerekli = False  # son sözü sen söylediysen bekleyen bir şey yok
            sonuc["sohbetler"].append({"ad": g["ad"], "grup": bool(g["grup"]), "mesaj": len(g["mesajlar"]), "ozet": k["ozet"],
                                       "cevap_gerekli": gerekli, "ne": k.get("ne") if gerekli else None,
                                       "onem": k.get("onem") if k.get("onem") in ("yuksek", "orta", "dusuk") else "orta"})
            DOSYA.write_text(json.dumps(sonuc, ensure_ascii=False))
        sonuc["hazirlaniyor"] = False
        sira = {"yuksek": 0, "orta": 1, "dusuk": 2}
        sonuc["sohbetler"].sort(key=lambda s: (not s["cevap_gerekli"], sira[s["onem"]]))  # cevap bekleyenler, sonra önem
        DOSYA.write_text(json.dumps(sonuc, ensure_ascii=False))
        log(f"WhatsApp özeti hazır: {len(sonuc['sohbetler'])} sohbet")
    finally:
        _durum["calisiyor"] = False
