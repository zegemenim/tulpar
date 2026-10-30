"""Tulpar ana servisi. Gelen her mesaj/bildirim: kaydet -> kod kuralları -> hızlı model elemesi ->
kurallarla düzelt -> gerekiyorsa (aynı sohbetten gelenler biraz beklenip toplanarak) taslak.
Sadece HP'nin kendisinden ve Tailscale ağından, anahtarla erişilir."""
import ipaddress
import json
import pathlib
import re
import secrets
import threading
import time
import urllib.request
from datetime import datetime

from fastapi import Body, Depends, FastAPI, HTTPException, Request

import db
import kurallar
import sahip
import ses
import uygulama
import taslak
from kuyruk import Is, Kuyruk, log

VERI = pathlib.Path.home() / "tulpar/veri"
ANAHTAR_YOL = VERI / "anahtar"
if not ANAHTAR_YOL.exists():
    ANAHTAR_YOL.write_text(secrets.token_urlsafe(32))
    ANAHTAR_YOL.chmod(0o600)
ANAHTAR = ANAHTAR_YOL.read_text().strip()
ISTEM = {k: sahip.doldur(v) for k, v in json.loads((pathlib.Path(__file__).parent / "istemler.json").read_text()).items()}
KOPRU = "http://127.0.0.1:8099"
TOPLAMA_SN = int(__import__("os").environ.get("TOPLAMA_SN", 90))  # aynı sohbetten art arda gelenleri tek taslakta topla
GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
# HP'nin kendisi, Tailscale ağı ve ev ağı (sahibi onayladı: evde Tailscale yoksa da bağlanılsın; anahtar yine şart)
IZINLI_AG = [ipaddress.ip_network(a) for a in ("127.0.0.0/8", "100.64.0.0/10", "192.168.1.0/24")]

kuyruk = Kuyruk()
app = FastAPI(title="Tulpar")
_sohbet = {}  # sohbet_id -> son mesaj zamanı, elemesi süren mesaj sayısı, taslak bekleyen mesajlar
_kilit = threading.Lock()


def bugun():
    s = datetime.now()
    return f"{s:%Y-%m-%d} {GUNLER[s.weekday()]} {s:%H:%M}"


def yetki(istek: Request):
    ip = ipaddress.ip_address(istek.client.host)
    if not any(ip in ag for ag in IZINLI_AG):
        raise HTTPException(403, "izinsiz ağ")
    if not secrets.compare_digest(istek.headers.get("x-tulpar-anahtar", ""), ANAHTAR):
        raise HTTPException(401, "anahtar yok veya yanlış")


def sohbet_modu(sohbet_id):
    """tam | onemli (taslak yok, sadece önemli bildirim). Kapalı sohbetler köprüden hiç gelmez."""
    try:
        return json.loads((VERI / "sohbet-modlari.json").read_text()).get(sohbet_id, "tam")
    except (FileNotFoundError, json.JSONDecodeError):
        return "tam"


app.include_router(uygulama.router, dependencies=[Depends(yetki)])
uygulama.bagla(kuyruk, ISTEM, bugun, lambda m: taslak.hazirla(kuyruk, m["sohbet_id"], m.get("sohbet_adi"), [m]))


def ele(m):
    """Bir mesajı değerlendir; sonucu kaydet ve gerekiyorsa taslak sırasına koy."""
    kaynak = m.get("sohbet_adi") or m.get("gonderen_adi") or "?"
    if m.get("grup"):
        kaynak = f"{kaynak} (grup), yazan: {m.get('gonderen_adi')}"
    sistem = ISTEM["system_triage"].replace("{bugun}", bugun())
    onceki = [x for x in db.son_mesajlar(m["sohbet_id"], 16) if x["id"] != m["id"]][-15:]
    baglam = "\n".join(f"{sahip.AD if x['benden'] else x.get('gonderen_adi') or '?'}: {x['metin'][:200]}" for x in onceki)
    istem = (f"Kaynak: {kaynak}\n" + (f"Önceki mesajlar (sadece bağlam, değerlendirme):\n{baglam}\n" if baglam else "")
             + f"Değerlendirilecek mesaj: {m['metin']}")
    is_ = kuyruk.ekle(Is("eleme", sistem, istem))
    is_.bekle()
    if is_.hata or not isinstance(is_.sonuc, dict) or "onem" not in is_.sonuc:
        # model ulaşılamadı veya bozuk cevap: karar kaydetme, mesaj yeniden denenmek üzere elenmemiş kalır
        log(f"eleme ertelendi ({is_.hata or 'gecersiz cevap'}): {kaynak[:40]}")
        with _kilit:
            _sohbet[m["sohbet_id"]]["eleme"] -= 1
        if not m.get("_deneme"):  # bir kez 2 dk sonra tekrar dene; olmazsa servis açılışında yeniden alınır
            m["_deneme"] = True
            with _kilit:
                _sohbet[m["sohbet_id"]]["eleme"] += 1
            threading.Timer(120, ele, args=(m,)).start()
        return
    sonuc = is_.sonuc
    sonuc = kurallar.uygula(sonuc, m["metin"], bool(m.get("grup")))
    db.eleme_kaydet(m["id"], sonuc)
    try:
        uygulama.elemeden_onay(m, sonuc)
    except Exception as e:
        log(f"HATA onay karti: {e}")
    log(f"eleme: {kaynak[:40]} -> onem={sonuc.get('onem')} aksiyon={sonuc.get('aksiyon')}"
        + (f" UYARI: {', '.join(sonuc['guvenlik'])}" if sonuc.get("guvenlik") else ""))
    if sonuc.get("onem") == "yuksek":
        log(f"BILDIRIM: {kaynak[:40]}: {sonuc.get('ozet') or m['metin'][:80]}")
    istiyor = sonuc.get("aksiyon") == "cevap_taslagi" or (
        sonuc.get("tur") == "soru" and not m.get("grup") and sonuc.get("aksiyon") != "yok")
    bana = m.get("grup") and (sonuc.get("kime") == "sahip" or "(sahibin mesajına cevap)" in m["metin"])
    if bana and sohbet_modu(m["sohbet_id"]) == "onemli" and not sonuc.get("guvenlik"):
        # ÖNEMLİ grupta doğrudan sahibe yazılan: haber ver ve "taslak hazırlayayım mı?" diye sor
        sonuc["onem"] = "yuksek"
        db.eleme_kaydet(m["id"], sonuc)
        log(f"BILDIRIM: {kaynak[:40]}: sana yazildi: {m['metin'][:80]}")
        uygulama.onay_ekle("taslak_teklif", f"{m.get('gonderen_adi') or '?'} sana yazdı ({m.get('sohbet_adi')}): taslak hazırlayayım mı?",
                           m["metin"][:300], m)
    # sadece görsel/çıkartma olan mesaja taslak yok: içeriğini göremiyoruz, körlemesine cevap uydurmayalım
    sadece_medya = bool(re.fullmatch(r"(\(sahibin mesajına cevap\) )?(@\S+ )*\[[^\]]+\]( @\S+)*", m["metin"].strip()))
    taslak_gerek = istiyor and not sadece_medya and sohbet_modu(m["sohbet_id"]) == "tam"  # taslak sadece TAM modda
    with _kilit:
        d = _sohbet.setdefault(m["sohbet_id"], {"son": 0, "eleme": 0, "gelenler": [], "zamanlayici": False})
        d["eleme"] -= 1
        if taslak_gerek and not sonuc.get("guvenlik"):
            d["gelenler"].append(m)
    if taslak_gerek and not sonuc.get("guvenlik"):
        zamanla(m["sohbet_id"], m.get("sohbet_adi"))


def zamanla(sohbet_id, sohbet_adi, sure=None):
    with _kilit:
        d = _sohbet[sohbet_id]
        if d["zamanlayici"] and sure is None:
            return
        d["zamanlayici"] = True
    threading.Timer(sure or TOPLAMA_SN, taslak_yap, args=(sohbet_id, sohbet_adi)).start()


def taslak_yap(sohbet_id, sohbet_adi):
    """Sohbet TOPLAMA_SN boyunca sustuysa ve tüm mesajlar elendiyse tek taslak hazırla."""
    with _kilit:
        d = _sohbet[sohbet_id]
        kalan = TOPLAMA_SN - (time.time() - d["son"])
        if d["eleme"] > 0 or kalan > 0:
            bekle = max(kalan, 3)
        else:
            gelenler, d["gelenler"], d["zamanlayici"] = d["gelenler"], [], False
            bekle = None
    if bekle:
        return zamanla(sohbet_id, sohbet_adi, bekle)
    if not gelenler:
        return
    try:
        tid = taslak.hazirla(kuyruk, sohbet_id, sohbet_adi, gelenler)
        log(f"taslak hazir #{tid}: {sohbet_adi} ({len(gelenler)} mesaja cevap)")
    except Exception as e:
        log(f"HATA taslak {sohbet_adi}: {e}")


def yarim_kalanlari_al():
    """Servis kapanırken kuyrukta kalan (elenmemiş) son 24 saatin mesajlarını yeniden kuyruğa al."""
    kalan = db.oku("SELECT * FROM mesajlar WHERE benden=0 AND eleme IS NULL AND zaman>? ORDER BY zaman",
                   time.time() - 86400)
    for m in kalan:
        m["grup"] = bool(m["grup"])
        m.pop("eleme", None)
        with _kilit:
            d = _sohbet.setdefault(m["sohbet_id"], {"son": 0, "eleme": 0, "gelenler": [], "zamanlayici": False})
            d["eleme"] += 1
        threading.Thread(target=ele, args=(m,), daemon=True).start()
    if kalan:
        log(f"yarim kalan {len(kalan)} mesaj yeniden kuyruga alindi")


@app.on_event("startup")
def baslangic():
    # eski geçmiş mesajları (bu işaret eklenmeden önce alınanlar) yeniden elenmesin
    db.yaz("UPDATE mesajlar SET eleme=? WHERE eleme IS NULL AND zaman<?", json.dumps({"gecmis": True}), 1793386800)
    # model hatası yüzünden boş kalan kararlar (onem yok) yeniden elensin
    db.yaz("UPDATE mesajlar SET eleme=NULL WHERE eleme NOT LIKE '%onem%' AND eleme NOT LIKE '%gecmis%' AND zaman>?",
           time.time() - 86400)
    threading.Thread(target=yarim_kalanlari_al, daemon=True).start()
    threading.Thread(target=uygulama.isit, daemon=True).start()


@app.post("/mesaj", dependencies=[Depends(yetki)])
def mesaj(m: dict = Body(...)):
    """Köprüden veya telefondan gelen mesaj. sahibin kendi mesajları sadece üslup için saklanır."""
    for alan in ("id", "sohbet_id", "metin"):
        if not m.get(alan):
            raise HTTPException(400, f"{alan} eksik")
    db.mesaj_kaydet(m)
    if m.get("gecmis"):  # ilk bağlantıda alınan eski mesajlar: sadece üslup ve hafıza için, elenmez
        db.eleme_kaydet(m["id"], {"gecmis": True})
        return {"tamam": True}
    with _kilit:
        d = _sohbet.setdefault(m["sohbet_id"], {"son": 0, "eleme": 0, "gelenler": [], "zamanlayici": False})
        if m.get("benden"):
            d["gelenler"] = []  # sahibi kendisi cevap verdi: bu sohbet için taslağa gerek kalmadı
        else:
            d["son"] = time.time()
            d["eleme"] += 1
    if not m.get("benden"):
        threading.Thread(target=sesliyse_dok_sonra_ele if m.get("ses_dosyasi") else ele, args=(m,), daemon=True).start()
    return {"tamam": True}


def sesliyse_dok_sonra_ele(m):
    dosya = pathlib.Path(m["ses_dosyasi"])
    try:
        yazi = ses.yaziya_dok(dosya)
        m["metin"] = f"[sesli mesaj] {yazi}" if yazi else "[sesli mesaj, anlaşılamadı]"
        db.yaz("UPDATE mesajlar SET metin=? WHERE id=?", m["metin"], m["id"])
    except Exception as e:
        log(f"HATA sesli mesaj: {e}")
    finally:
        dosya.unlink(missing_ok=True)
    ele(m)


@app.post("/komut", dependencies=[Depends(yetki)])
def komut(govde: dict = Body(...)):
    """sahibin doğrudan isteği (yazılı/sesli). Acil şeritten gider; araç kararı döner, uygulamaz."""
    sistem = ISTEM["system_tool"].replace("{bugun}", bugun())
    karar = kuyruk.ekle(Is("komut", sistem, govde["metin"])).bekle(120)
    log(f"komut: {govde['metin'][:60]} -> {karar and karar.get('arac')}")
    return karar or {"hata": "zaman aşımı"}


@app.get("/taslaklar", dependencies=[Depends(yetki)])
def taslak_listesi(durum: str = "bekliyor"):
    liste = db.taslaklar(durum)
    for t in liste:  # uygulamada göstermek için cevaplanan mesajların metni
        t["gelenler"] = db.oku(f"SELECT id, gonderen_adi, metin, zaman FROM mesajlar WHERE id IN "
                               f"({','.join('?' * len(t['mesaj_idler']))})", *t["mesaj_idler"]) if t["mesaj_idler"] else []
    return liste


@app.post("/taslak/{tid}/gonder", dependencies=[Depends(yetki)])
def taslak_gonder(tid: int, govde: dict = Body(default={})):
    """sahibi onayladı. İstersen düzenlenmiş mesajlarla. Mesajlar sırayla, alıntılı gönderilir."""
    t = next((x for x in db.taslaklar("bekliyor") if x["id"] == tid), None)
    if not t:
        raise HTTPException(404, "bekleyen taslak yok")
    secenekler = t["mesajlar"]
    mesajlar = govde.get("mesajlar") or (secenekler[govde.get("secenek", 0)]["mesajlar"] if secenekler else [])
    if not mesajlar:
        raise HTTPException(400, "gönderilecek mesaj yok")
    if any("[" in m["metin"] and "]" in m["metin"] for m in mesajlar):
        raise HTTPException(400, "taslakta doldurulmamış [boşluk] var")
    try:
        for m in mesajlar:
            alinti = None
            if m.get("yanit_id"):
                r = db.oku("SELECT id, gonderen_id, benden, metin FROM mesajlar WHERE id=?", m["yanit_id"])
                alinti = r[0] if r else None
            istek = urllib.request.Request(KOPRU + "/gonder", data=json.dumps(
                {"sohbet_id": t["sohbet_id"], "metin": m["metin"], "alinti": alinti}, ensure_ascii=False).encode(),
                headers={"Content-Type": "application/json", "x-tulpar-anahtar": ANAHTAR})
            urllib.request.urlopen(istek, timeout=60)
            time.sleep(1.5)
    except Exception as e:
        db.taslak_durum(tid, "hata")
        log(f"HATA gonderim #{tid}: {e}")
        raise HTTPException(502, f"gönderilemedi: {e}")
    if govde.get("mesajlar"):
        log(f"taslak #{tid} sahibi tarafindan duzeltildi (ogrenme icin saklandi)")
        db.yaz("UPDATE taslaklar SET uyarilar=? WHERE id=?", json.dumps(
            t["uyarilar"] + [{"orijinal": t["mesajlar"]}], ensure_ascii=False), tid)
    db.taslak_durum(tid, "gonderildi", mesajlar)
    log(f"gonderildi #{tid}: {t['sohbet_adi']} ({len(mesajlar)} mesaj)")
    return {"tamam": True}


@app.post("/taslak/{tid}/reddet", dependencies=[Depends(yetki)])
def taslak_reddet(tid: int):
    db.taslak_durum(tid, "reddedildi")
    return {"tamam": True}


@app.post("/kisi/{kid}", dependencies=[Depends(yetki)])
def kisi_duzelt(kid: str, alanlar: dict = Body(...)):
    """sahibi kişi kartını düzeltti: bu bilgi 'kesin' olur, Tulpar'ın tahmini ezemez."""
    izinli = {k: alanlar[k] for k in ("ad", "iliski", "hitap", "sen_siz", "notlar") if k in alanlar}
    return db.kisi_kaydet(kid, guven="kesin", **izinli)


@app.get("/onemli", dependencies=[Depends(yetki)])
def onemli(saat: int = 24):
    satirlar = db.oku("SELECT id, kaynak, sohbet_adi, gonderen_adi, metin, zaman, eleme FROM mesajlar "
                      "WHERE benden=0 AND zaman>? AND eleme LIKE '%\"onem\": \"yuksek\"%' ORDER BY zaman DESC",
                      time.time() - saat * 3600)
    for s in satirlar:
        s["eleme"] = json.loads(s["eleme"])
    return satirlar


@app.get("/durum", dependencies=[Depends(yetki)])
def durum():
    return {"zaman": bugun(), "bekleyen_taslak": len(db.taslaklar("bekliyor")),
            "mesaj_sayisi": db.oku("SELECT COUNT(*) n FROM mesajlar")[0]["n"],
            "hizli_kuyruk": kuyruk.hizli.qsize(), "buyuk_kuyruk": kuyruk.buyuk.qsize(),
            "acik_buyuk_model": kuyruk.acik_buyuk}
