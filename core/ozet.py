"""WhatsApp özeti: son saatlerde hangi sohbette ne konuşuldu, sahibinin cevaplaması gereken var mı. Arka planda, sohbet başına
tek model çağrısıyla hazırlanır (yavaş model: sırayla); sonuç veri/ozet.json'da durur, uygulama/menü oradan okur.
Kapalı (haric) sohbetler hiç işlenmez."""
import json
import pathlib
import threading
import time

import db
import sahip
from egitim_verisi import haric
from kuyruk import Is, log

DOSYA = pathlib.Path.home() / "tulpar/veri/ozet.json"
_durum = {"calisiyor": False}
_kilit = threading.Lock()

SISTEM = sahip.doldur(
    "Sen Tulpar'sın. {SAHIP_TAM} için bir WhatsApp sohbetini özetliyorsun. Verilen konuşmada neler konuşulduğunu 1-2 kısa cümleyle "
    "anlat (kim ne dedi/istedi). Konuşmada olmayan bir şeyi UYDURMA. Sahibinin cevap vermesi, bir şey yapması ya da karar vermesi "
    "gereken bir şey var mı? Selamlaşma, teşekkür, tepki, 'tamam' gibi karşılıksız mesajlar cevap gerektirmez.\n"
    'SADECE JSON: {"ozet": "...", "cevap_gerekli": true|false, "ne": "cevap/iş gerekiyorsa tek cümle, yoksa null"}'
)


def oku():
    try:
        return json.loads(DOSYA.read_text())
    except (FileNotFoundError, ValueError):
        return {"zaman": 0, "sohbetler": [], "hazirlaniyor": _durum["calisiyor"]}


def _sohbetler(saat):
    """Son `saat` saatte karşı taraftan mesaj gelen sohbetler (kapalılar hariç), mesaj sayısına göre."""
    kapali = haric()
    satirlar = db.oku("SELECT sohbet_id, sohbet_adi, grup, benden, gonderen_adi, metin, zaman FROM mesajlar "
                      "WHERE zaman > ? AND metin IS NOT NULL AND metin!='' ORDER BY zaman", time.time() - saat * 3600)
    gruplar = {}
    for s in satirlar:
        if s["sohbet_id"] in kapali or s["sohbet_id"].endswith(("@newsletter", "@broadcast")):
            continue
        g = gruplar.setdefault(s["sohbet_id"], {"ad": s["sohbet_adi"], "grup": s["grup"], "mesajlar": [], "gelen": 0})
        g["mesajlar"].append(s)
        g["gelen"] += 0 if s["benden"] else 1
    return sorted((g for g in gruplar.values() if g["gelen"]), key=lambda g: -len(g["mesajlar"]))


def hazirla(kuyruk, saat=24, en_cok=12):
    """Özeti baştan hazırlar (arka planda çağrılır). Her sohbet bitince dosyaya yazılır: uygulama ilerlemeyi görür."""
    with _kilit:
        if _durum["calisiyor"]:
            return
        _durum["calisiyor"] = True
    try:
        liste = _sohbetler(saat)[:en_cok]
        sonuc = {"zaman": time.time(), "saat": saat, "hazirlaniyor": True, "sohbetler": [], "toplam": len(liste)}
        for g in liste:
            metin = "\n".join(f"{sahip.AD if m['benden'] else m.get('gonderen_adi') or g['ad']}: {m['metin'][:300]}" for m in g["mesajlar"][-30:])
            k = kuyruk.ekle(Is("komut", SISTEM, f"Sohbet: {g['ad']}\n{metin}", aciklama=f"WhatsApp özeti: {g['ad']}")).bekle(600) or {}
            if not k.get("ozet"):
                continue
            sonuc["sohbetler"].append({"ad": g["ad"], "grup": bool(g["grup"]), "mesaj": len(g["mesajlar"]), "ozet": k["ozet"],
                                       "cevap_gerekli": bool(k.get("cevap_gerekli")), "ne": k.get("ne")})
            DOSYA.write_text(json.dumps(sonuc, ensure_ascii=False))
        sonuc["hazirlaniyor"] = False
        sonuc["sohbetler"].sort(key=lambda s: not s["cevap_gerekli"])  # cevap bekleyenler üstte
        DOSYA.write_text(json.dumps(sonuc, ensure_ascii=False))
        log(f"WhatsApp özeti hazır: {len(sonuc['sohbetler'])} sohbet")
    finally:
        _durum["calisiyor"] = False
