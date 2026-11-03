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
from fastapi.responses import FileResponse

import db
import ayarlar
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


def _toplama_sn(m):
    """Grupta/birebirde art arda gelenler bu kadar sessizlikten sonra tek seferde değerlendirilir (ayarlanabilir)."""
    return ayarlar.al("grup_toplama_sn" if m.get("grup") else "birebir_toplama_sn")

_grup = {}  # sohbet_id -> {"mesajlar": [...], "son": zaman, "zamanlayici": bool}


def grup_bekle(m):
    """Grup mesajını hemen değil, grup susunca toplu değerlendirmek üzere biriktir."""
    with _kilit:
        g = _grup.setdefault(m["sohbet_id"], {"mesajlar": [], "son": 0, "zamanlayici": False})
        g["mesajlar"].append(m)
        g["son"] = time.time()
        if g["zamanlayici"]:
            return
        g["zamanlayici"] = True
    threading.Timer(_toplama_sn(m), grup_ele, args=(m["sohbet_id"],)).start()


def grup_ele(sohbet_id):
    with _kilit:
        g = _grup[sohbet_id]
        kalan = (_toplama_sn(g["mesajlar"][-1]) if g["mesajlar"] else 0) - (time.time() - g["son"])
        if kalan > 0:
            threading.Timer(kalan + 1, grup_ele, args=(sohbet_id,)).start()
            return
        mesajlar, g["mesajlar"], g["zamanlayici"] = g["mesajlar"], [], False
    if not mesajlar:
        return
    temsilci = mesajlar[-1]
    for x in mesajlar[:-1]:  # tek tek model çalıştırma: hepsi temsilcinin değerlendirmesinde birlikte okunur
        db.eleme_kaydet(x["id"], kurallar.uygula({"onem": "dusuk", "aksiyon": "yok", "toplu": temsilci["id"]},
                                                  x["metin"], bool(x.get("grup"))))
        with _kilit:
            _sohbet[sohbet_id]["eleme"] -= 1
    if len(mesajlar) > 1:
        log(f"TOPLU DEĞERLENDİRME | {temsilci.get('sohbet_adi', '?')[:40]} | {len(mesajlar)} mesaj tek işte birleştirildi")
    ele(temsilci, toplu=mesajlar)


_emoji_onbellek = {"zaman": 0, "metin": ""}
EMOJI = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2764\u2B50]\uFE0F?")


def sahip_emojileri():
    """Sahibin mesajlarında ve verdiği tepkilerde en sık kullandığı emojiler (tepki seçimi için; 1 saat önbellek)."""
    if time.time() - _emoji_onbellek["zaman"] < 3600:
        return _emoji_onbellek["metin"]
    sayac = {}
    for r in db.oku("SELECT metin FROM mesajlar WHERE benden=1 ORDER BY zaman DESC LIMIT 20000"):
        for e in EMOJI.findall(r["metin"]):
            sayac[e] = sayac.get(e, 0) + 1
    try:
        for satir in (VERI / "tepkiler.jsonl").read_text().splitlines():
            e = json.loads(satir).get("emoji")
            if e:
                sayac[e] = sayac.get(e, 0) + 5  # bilinçli verilen tepki daha güçlü işaret
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    ilk = sorted(sayac, key=sayac.get, reverse=True)[:12]
    _emoji_onbellek.update(zaman=time.time(), metin=" ".join(ilk))
    return _emoji_onbellek["metin"]


def ele(m, toplu=None):
    """Bir mesajı değerlendir; sonucu kaydet ve gerekiyorsa taslak sırasına koy.
    toplu: grupta art arda gelen mesajlar; hepsi tek seferde okunur, sonuç son mesaja (m) yazılır."""
    kaynak = m.get("sohbet_adi") or m.get("gonderen_adi") or "?"
    if m.get("grup"):
        kaynak = f"{kaynak} (grup), yazan: {m.get('gonderen_adi')}"
    sistem = ISTEM["system_triage"].replace("{bugun}", bugun())
    if sahip_emojileri():
        sistem += f"\nSahibinin en sık kullandığı emojiler (tepki seçerken bunlardan seç): {sahip_emojileri()}"
    yeni = {x["id"] for x in (toplu or [m])}
    n = ayarlar.al("baglam_mesaj")
    onceki = [x for x in db.son_mesajlar(m["sohbet_id"], n + 1 + len(yeni)) if x["id"] not in yeni][-n:]
    baglam = "\n".join(f"{sahip.AD if x['benden'] else x.get('gonderen_adi') or '?'}: {x['metin'][:200]}" for x in onceki)
    if toplu and len(toplu) > 1:
        degerlendir = ("Değerlendirilecek mesajlar (art arda geldi; HEPSİNİ birlikte değerlendir, en önemli olana göre karar ver):\n"
                       + "\n".join(f"{x.get('gonderen_adi') or '?'}: {x['metin'][:300]}" for x in toplu))
    else:
        degerlendir = f"Değerlendirilecek mesaj: {m['metin']}"
    istem = (f"Kaynak: {kaynak}\n" + (f"Önceki mesajlar (sadece bağlam, değerlendirme):\n{baglam}\n" if baglam else "")
             + degerlendir)
    onizleme = " | ".join(f"{x.get('gonderen_adi') or '?'}: {x['metin'][:50]}" for x in (toplu or [m])[:3])
    is_ = kuyruk.ekle(Is("eleme", sistem, istem, aciklama=f"{kaynak[:45]} → {onizleme[:140]}"))
    is_.bekle()
    if is_.hata or not isinstance(is_.sonuc, dict) or "onem" not in is_.sonuc:
        # model ulaşılamadı veya bozuk cevap: karar kaydetme, mesaj yeniden denenmek üzere elenmemiş kalır
        log(f"DEĞERLENDİRME ERTELENDİ | {kaynak[:40]} | sebep: {is_.hata or 'model geçersiz cevap verdi'}; 2 dk sonra yeniden denenecek")
        with _kilit:
            _sohbet[m["sohbet_id"]]["eleme"] -= 1
        if not m.get("_deneme"):  # bir kez 2 dk sonra tekrar dene; olmazsa servis açılışında yeniden alınır
            m["_deneme"] = True
            with _kilit:
                _sohbet[m["sohbet_id"]]["eleme"] += 1
            threading.Timer(120, ele, args=(m,)).start()
        return
    sonuc = is_.sonuc
    sonuc = kurallar.uygula(sonuc, "\n".join(x["metin"] for x in (toplu or [m])), bool(m.get("grup")))
    db.eleme_kaydet(m["id"], sonuc)
    try:
        uygulama.elemeden_onay(m, sonuc)
    except Exception as e:
        log(f"HATA onay karti: {e}")
    log(f"SONUÇ | {kaynak[:45]} | önem: {sonuc.get('onem')}, aksiyon: {sonuc.get('aksiyon')}, ihtimal: {sonuc.get('cevap_ihtimali', '-')}"
        + (f" | ÖZET: {sonuc['ozet'][:90]}" if sonuc.get("ozet") else "")
        + (f" | UYARI: {', '.join(sonuc['guvenlik'])}" if sonuc.get("guvenlik") else ""))
    if sonuc.get("onem") == "yuksek":
        log(f"BİLDİRİM GİTTİ | {kaynak[:45]} | {sonuc.get('ozet') or m['metin'][:80]}")
    istiyor = sonuc.get("aksiyon") == "cevap_taslagi" or (
        sonuc.get("tur") == "soru" and not m.get("grup") and sonuc.get("aksiyon") != "yok")
    # cevap seviyesi: modelin "sahibi normalde cevaplar mı" puanı (0-10) eşiğe göre; sahibe doğrudan yazılanlar her seviyede geçer
    dogrudan = bool(sonuc.get("kime") == "sahip" or "(sahibin mesajına cevap)" in m["metin"] or not m.get("grup"))
    ihtimal = sonuc.get("cevap_ihtimali")
    ihtimal = ihtimal if isinstance(ihtimal, (int, float)) else (6 if istiyor else 0)
    istiyor = (istiyor and dogrudan) or ihtimal >= {1: 8, 2: 5, 3: 3}[ayarlar.al("cevap_seviyesi")]
    bana = m.get("grup") and (sonuc.get("kime") == "sahip" or "(sahibin mesajına cevap)" in m["metin"])
    if bana and sohbet_modu(m["sohbet_id"]) == "onemli" and not sonuc.get("guvenlik"):
        # ÖNEMLİ grupta doğrudan sahibe yazılan: haber ver ve "taslak hazırlayayım mı?" diye sor
        sonuc["onem"] = "yuksek"
        db.eleme_kaydet(m["id"], sonuc)
        log(f"BİLDİRİM GİTTİ | {kaynak[:45]} | doğrudan sana yazıldı: {m['metin'][:80]}")
        uygulama.onay_ekle("taslak_teklif", f"{m.get('gonderen_adi') or '?'} sana yazdı ({m.get('sohbet_adi')}): taslak hazırlayayım mı?",
                           m["metin"][:300], m)
    # sadece görsel/çıkartma olan mesaja taslak yok: içeriğini göremiyoruz, körlemesine cevap uydurmayalım
    sadece_medya = bool(re.fullmatch(r"(\(sahibin mesajına cevap\) )?(@\S+ )*\[[^\]]+\]( @\S+)*", m["metin"].strip()))
    taslak_gerek = istiyor and not sadece_medya and sohbet_modu(m["sohbet_id"]) == "tam"  # taslak sadece TAM modda
    tepki = (sonuc.get("tepki") or "").strip()
    if (not taslak_gerek and not sonuc.get("guvenlik") and tepki and len(tepki) <= 8 and ihtimal >= 2 and ayarlar.al("cevap_seviyesi") >= 3
            and sohbet_modu(m["sohbet_id"]) == "tam" and not db.oku("SELECT 1 FROM taslaklar WHERE durum='bekliyor' AND mesaj_idler LIKE ?", f'%"{m["id"]}"%')):
        try:  # yüksek seviyede cevap vermeye değmeyen ama karşılık beklenen mesaja emoji tepkisi önerilir (yine onayla gider)
            _tepki_taslagi_ac(m["id"], emoji=tepki)
        except Exception as e:
            log(f"otomatik tepki atlandi: {e}")
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
    threading.Timer(sure or ayarlar.al("taslak_bekleme_sn"), taslak_yap, args=(sohbet_id, sohbet_adi)).start()


def taslak_yap(sohbet_id, sohbet_adi):
    """Sohbet taslak bekleme süresi boyunca sustuysa ve tüm mesajlar elendiyse tek taslak hazırla."""
    with _kilit:
        d = _sohbet[sohbet_id]
        kalan = ayarlar.al("taslak_bekleme_sn") - (time.time() - d["son"])
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
        if m["sohbet_id"].endswith(("@newsletter", "@broadcast")):  # kanal/bülten değerlendirilmez
            db.eleme_kaydet(m["id"], {"atla": "kanal"})
            continue
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
    threading.Thread(target=uygulama.arastirma_toparla, daemon=True).start()


@app.get("/uygulama/vosk-tr.zip")
def vosk_modeli(istek: Request):
    """Uyandırma kelimesi için Türkçe ses modeli (herkese açık bir model; sadece ev ağı/Tailscale'den, anahtarsız:
    telefondaki arka plan servisi uygulamanın anahtarına erişemiyor)."""
    if not any(ipaddress.ip_address(istek.client.host) in ag for ag in IZINLI_AG):
        raise HTTPException(403, "izinsiz ağ")
    yol = VERI / "uygulama/vosk-tr.zip"
    if not yol.exists():
        raise HTTPException(404, "model henüz sunucuda yok")
    return FileResponse(yol, media_type="application/zip")


@app.post("/mesaj", dependencies=[Depends(yetki)])
def mesaj(m: dict = Body(...)):
    """Köprüden veya telefondan gelen mesaj. sahibin kendi mesajları sadece üslup için saklanır."""
    for alan in ("id", "sohbet_id", "metin"):
        if not m.get(alan):
            raise HTTPException(400, f"{alan} eksik")
    db.mesaj_kaydet(m)
    if not m.get("gecmis") and not m["sohbet_id"].endswith(("@newsletter", "@broadcast")):
        yon = "GİDEN (sen)" if m.get("benden") else "GELEN"
        log(f"{yon} | {'grup' if m.get('grup') else 'özel'}: {(m.get('sohbet_adi') or '?')[:40]} | {(m.get('gonderen_adi') or '?')[:25]}: {m['metin'][:70]}")
    if m.get("gecmis"):  # ilk bağlantıda alınan eski mesajlar: sadece üslup ve hafıza için, elenmez
        db.eleme_kaydet(m["id"], {"gecmis": True})
        return {"tamam": True}
    if m["sohbet_id"].endswith(("@newsletter", "@broadcast")):  # kanal/bülten/durum: model değerlendirmesine girmez (zaman ve bellek harcamasın)
        db.eleme_kaydet(m["id"], {"atla": "kanal"})
        return {"tamam": True}
    with _kilit:
        d = _sohbet.setdefault(m["sohbet_id"], {"son": 0, "eleme": 0, "gelenler": [], "zamanlayici": False})
        if m.get("benden"):
            d["gelenler"] = []  # sahibi kendisi cevap verdi: bu sohbet için taslağa gerek kalmadı
            for t in db.taslaklar("bekliyor"):  # bekleyen taslaklar da kendiliğinden kalkar (ders sayılmaz)
                if t["sohbet_id"] == m["sohbet_id"]:
                    db.taslak_durum(t["id"], "reddedildi")
                    log(f"taslak #{t['id']} sahibi kendisi yazdigi icin kaldirildi")
        else:
            d["son"] = time.time()
            d["eleme"] += 1
    if not m.get("benden"):
        if m.get("ses_dosyasi"):
            threading.Thread(target=sesliyse_dok_sonra_ele, args=(m,), daemon=True).start()
        elif not kurallar.guvenlik_kontrol(m["metin"]):
            grup_bekle(m)  # kişi/grup susunca toplu (güvenlik kuralına takılan mesaj beklemeden tek başına)
        else:
            threading.Thread(target=ele, args=(m,), daemon=True).start()
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
    for t in liste:  # uygulamada göstermek için cevaplanan mesajların metni ve öncesindeki konuşma
        t["gelenler"] = db.oku(f"SELECT id, gonderen_adi, metin, zaman FROM mesajlar WHERE id IN "
                               f"({','.join('?' * len(t['mesaj_idler']))})", *t["mesaj_idler"]) if t["mesaj_idler"] else []
        ilk = min((g["zaman"] for g in t["gelenler"]), default=None)
        t["onceki"] = list(reversed(db.oku(
            "SELECT id, gonderen_adi, benden, metin, zaman FROM mesajlar WHERE sohbet_id=? AND zaman<? ORDER BY zaman DESC LIMIT 6",
            t["sohbet_id"], ilk))) if ilk else []
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
    if any("[" in m["metin"] and "]" in m["metin"] for m in mesajlar if not m.get("cikartma")):
        raise HTTPException(400, "taslakta doldurulmamış [boşluk] var")
    try:
        for m in mesajlar:
            alinti = None
            if m.get("yanit_id"):
                r = db.oku("SELECT id, gonderen_id, benden, metin FROM mesajlar WHERE id=?", m["yanit_id"])
                alinti = r[0] if r else None
            istek = urllib.request.Request(KOPRU + "/gonder", data=json.dumps(
                {"sohbet_id": t["sohbet_id"], "metin": m["metin"], "alinti": alinti, "tepki": m.get("tepki"), "cikartma": m.get("cikartma")},
                ensure_ascii=False).encode(),
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
        db.geri_bildirim_ekle(t, "duzeltme", govde.get("neden"), mesajlar)
    db.taslak_durum(tid, "gonderildi", mesajlar)
    log(f"gonderildi #{tid}: {t['sohbet_adi']} ({len(mesajlar)} mesaj)")
    return {"tamam": True}


def _cikartmalar():
    out = []
    for f in sorted((VERI / "cikartmalar").glob("*.json")):
        try:
            out.append(json.loads(f.read_text()))
        except (OSError, json.JSONDecodeError):
            pass
    return out


@app.get("/cikartmalar", dependencies=[Depends(yetki)])
def cikartma_listesi():
    return _cikartmalar()


@app.get("/cikartma/{sha}", dependencies=[Depends(yetki)])
def cikartma_dosya(sha: str):
    if not re.fullmatch(r"[0-9a-f]{6,64}", sha) or not (VERI / "cikartmalar" / f"{sha}.webp").exists():
        raise HTTPException(404, "yok")
    return FileResponse(VERI / "cikartmalar" / f"{sha}.webp", media_type="image/webp")


def _tepki_taslagi_ac(mid, emoji=None, cikartma=None):
    r = db.oku("SELECT id, sohbet_id, sohbet_adi, gonderen_adi, metin FROM mesajlar WHERE id=?", mid)
    if not r:
        raise HTTPException(404, "mesaj yok")
    m = r[0]
    try:  # hariç tutulan (KAPALI) sohbete tepki de gitmez
        if m["sohbet_id"] in set(json.loads((VERI / "haric.json").read_text()).get("sohbetler", [])):
            raise HTTPException(403, "bu sohbet kapalı")
    except FileNotFoundError:
        pass
    if cikartma:
        etiket, oge = "Çıkartma", {"yanit_id": mid, "metin": "çıkartma", "cikartma": cikartma}
    else:
        etiket, oge = f"Tepki {emoji}", {"yanit_id": mid, "metin": emoji, "tepki": emoji}
    ozet = f"{etiket} → {m['gonderen_adi'] or m['sohbet_adi']}: {m['metin'][:60]}"
    tid = db.taslak_ekle(m["sohbet_id"], m["sohbet_adi"], [mid], ozet, [{"etiket": etiket, "mesajlar": [oge]}], [])
    log(f"{etiket.lower()} taslagi #{tid}: {m['sohbet_adi']}")
    return tid


@app.post("/mesaj/{mid}/cikartma", dependencies=[Depends(yetki)])
def cikartma_taslagi(mid: str, govde: dict = Body(...)):
    sha = (govde.get("sha") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{6,64}", sha) or not (VERI / "cikartmalar" / f"{sha}.webp").exists():
        raise HTTPException(400, "çıkartma yok")
    return {"taslak": _tepki_taslagi_ac(mid, cikartma=sha)}


@app.post("/mesaj/{mid}/tepki", dependencies=[Depends(yetki)])
def tepki_taslagi(mid: str, govde: dict = Body(...)):
    """Bir mesaja emoji tepkisi için taslak açar. Gönderim yine onayla olur (taslaklardan)."""
    emoji = (govde.get("emoji") or "").strip()
    if not emoji or len(emoji) > 8:
        raise HTTPException(400, "emoji gerekli")
    return {"taslak": _tepki_taslagi_ac(mid, emoji=emoji)}


@app.post("/taslak/{tid}/reddet", dependencies=[Depends(yetki)])
def taslak_reddet(tid: int, govde: dict = Body(default={})):
    """Reddedilen taslak ve (varsa) sebebi ders olarak saklanır; sonraki taslaklar bunu okur."""
    t = next((x for x in db.taslaklar("bekliyor") if x["id"] == tid), None)
    db.taslak_durum(tid, "reddedildi")
    if t and (govde.get("neden") or "").strip():  # sebep yazılmadıysa ders sayılmaz (kendi mesajını yazmış olabilir)
        db.geri_bildirim_ekle(t, "red", govde.get("neden"))
        log(f"taslak #{tid} reddedildi: {govde['neden'][:60]}")
    else:
        log(f"taslak #{tid} reddedildi (sebepsiz, ders degil)")
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
