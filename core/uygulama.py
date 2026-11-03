"""Android uygulamasının kullandığı uç noktalar: ana ekran, onaylar, görevler, sohbetler, konuşma, ses."""
import json
import pathlib
import re
import subprocess
import tempfile
import threading
import time

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

import ayarlar
import db
import llm
import ozet
import bildirim
import pano
import sahip
import cihaz
import ses
import taslak
import tarayici
import tts
from kuyruk import Is, log

VERI = pathlib.Path.home() / "tulpar/veri"
router = APIRouter()
_baglam = {}  # kuyruk ve istemler tulpar.py'den bağlanır


def bagla(kuyruk, istem, bugun, taslak_hazirla):
    _baglam.update(kuyruk=kuyruk, istem=istem, bugun=bugun, taslak_hazirla=taslak_hazirla)


def isit():
    """Servis açılınca sohbet istemini modele bir kez okut: ilk sesli soru da önbellekten hızlı başlasın."""
    try:
        sistem = _sistem(_baglam["bugun"]())
        for _ in llm.akis("hizli", sistem, "merhaba"):
            break
        log("sohbet onbellegi isitildi")
    except Exception as e:
        log(f"HATA isitma: {e}")


# ---------- onaylar: modelin önerdiği, sahibinin izniyle yapılacak işler ----------

def onay_ekle(tur, baslik, aciklama, m=None, veri=None):
    oid = db.yaz("""INSERT INTO onaylar (tur,baslik,aciklama,sohbet_id,sohbet_adi,mesaj_id,veri,olusturma)
                    VALUES (?,?,?,?,?,?,?,?)""", tur, baslik, aciklama, m and m.get("sohbet_id"),
                 m and m.get("sohbet_adi"), m and m.get("id"), json.dumps(veri or {}, ensure_ascii=False), time.time())
    log(f"onay bekliyor #{oid}: {tur}: {baslik[:60]}")
    return oid


def _takvim_guncelle(m, kim, ozet, veri):
    """Aynı sohbette bekleyen takvim kartı aynı konuysa yenisini açmaz, mevcut kartı yeni bilgiyle günceller."""
    bekleyen = db.oku("SELECT * FROM onaylar WHERE tur='takvim' AND durum='bekliyor' AND sohbet_id=? ORDER BY olusturma DESC LIMIT 5",
                      m.get("sohbet_id"))
    if not bekleyen:
        return False
    liste = "\n".join(f"{i}: {o['baslik']} | {json.dumps(json.loads(o['veri'] or '{}'), ensure_ascii=False)}" for i, o in enumerate(bekleyen))
    sistem = ('Bekleyen takvim kartları ve yeni bir mesajdan çıkan etkinlik verilir. Yeni etkinlik kartlardan biriyle AYNI etkinlikse '
              '(aynı konu/buluşma; saat veya yer güncellenmiş olabilir) {"ayni": kart_numarası, "baslik": "güncel kısa başlık", '
              '"tarih": "...", "saat": "..."} döndür (bilinmeyen alanı eski karttan al). Farklı bir etkinlikse {"ayni": null} döndür.')
    icerik = f"Kartlar:\n{liste}\n\nYeni mesaj ({kim}): {m['metin'][:300]}\nÇıkan özet: {ozet} | {json.dumps(veri, ensure_ascii=False)}"
    try:
        k = _baglam["kuyruk"].ekle(Is("komut", sistem, icerik, aciklama=f"Takvim tekrar kontrolü: {kim}")).bekle(180) or {}
        i = k.get("ayni")
        if not isinstance(i, int) or not 0 <= i < len(bekleyen):
            return False
        o = bekleyen[i]
        yeni = {"tarih": k.get("tarih") or veri.get("tarih"), "saat": k.get("saat") or veri.get("saat")}
        baslik = f"Takvime ekle: {k.get('baslik') or ozet}"
        db.yaz("UPDATE onaylar SET baslik=?, aciklama=?, veri=?, olusturma=? WHERE id=?", baslik,
               f"{kim} yazdı (güncellendi): {m['metin'][:300]}\n— Önceki: {o['aciklama'][:200]}", json.dumps(yeni, ensure_ascii=False),
               time.time(), o["id"])
        log(f"takvim karti #{o['id']} yeni bilgiyle guncellendi")
        return True
    except Exception as e:
        log(f"takvim tekrar kontrolu hatasi: {type(e).__name__}: {e}")
        return False


def elemeden_onay(m, sonuc):
    """Eleme sonucuna göre onay kartı açar (takvim, Claude işi, güvenlik uyarısı)."""
    kim = m.get("sohbet_adi") or "?"
    ozet = sonuc.get("ozet") or m["metin"][:120]
    if sonuc.get("aksiyon") == "uyar":
        onay_ekle("uyari", f"Şüpheli mesaj: {kim}", " ".join(sonuc.get("kural_notlari") or [ozet]), m)
    elif sonuc.get("aksiyon") == "takvim" and sonuc.get("onem") == "yuksek":
        veri = {"tarih": sonuc.get("tarih"), "saat": sonuc.get("saat")}
        if not _takvim_guncelle(m, kim, ozet, veri):
            onay_ekle("takvim", f"Takvime ekle: {ozet}", f"{kim} yazdı: {m['metin'][:300]}", m, veri)
    elif sonuc.get("aksiyon") == "claude_gorev" and sonuc.get("kime") != "baskasi":
        onay_ekle("claude_gorev", f"İş isteği: {ozet}", f"{kim} yazdı: {m['metin'][:500]}", m)


@router.get("/ana")
def ana():
    db.yaz("DELETE FROM onaylar WHERE durum='reddedildi' AND karar<?", time.time() - ayarlar.al("reddedilen_sakla_gun") * 86400)
    onemli = db.oku("""SELECT id, sohbet_id, sohbet_adi, gonderen_adi, metin, zaman, eleme FROM mesajlar
                       WHERE benden=0 AND zaman>? AND eleme LIKE '%"onem": "yuksek"%' ORDER BY zaman DESC LIMIT 30""",
                    time.time() - 86400)
    for o in onemli:
        o["eleme"] = json.loads(o["eleme"])
    return {
        "onaylar": onaylar("bekliyor"),
        "taslak_sayisi": len(db.taslaklar("bekliyor")),
        "gorevler": db.oku("SELECT * FROM gorevler WHERE durum='acik' ORDER BY zaman IS NULL, zaman LIMIT 20"),
        "onemli": onemli,
    }


@router.get("/onaylar")
def onaylar(durum: str = "bekliyor"):
    r = db.oku("SELECT * FROM onaylar WHERE durum=? ORDER BY olusturma DESC LIMIT 100", durum)
    for o in r:
        o["veri"] = json.loads(o["veri"] or "{}")
    return r


@router.post("/onay/{oid}")
def onay_karar(oid: int, govde: dict = Body(...)):
    karar = govde.get("karar")
    if karar not in ("onay", "red", "geri"):
        raise HTTPException(400, "karar: onay | red | geri")
    o = db.oku("SELECT * FROM onaylar WHERE id=?", oid)
    if not o:
        raise HTTPException(404, "yok")
    o = o[0]
    if karar == "geri":  # reddedilenler listesinden geri al
        db.yaz("UPDATE onaylar SET durum='bekliyor', karar=NULL WHERE id=?", oid)
        return {"tamam": True}
    durum = "onaylandi" if karar == "onay" else "reddedildi"
    db.yaz("UPDATE onaylar SET durum=?, karar=? WHERE id=?", durum, time.time(), oid)
    if karar == "onay" and o["tur"] == "takvim":
        v = json.loads(o["veri"] or "{}")
        zaman = " ".join(x for x in (v.get("tarih"), v.get("saat")) if x) or None
        db.yaz("INSERT INTO gorevler (metin,zaman,kaynak,olusturma) VALUES (?,?,?,?)",
               o["baslik"].removeprefix("Takvime ekle: "), zaman, f"onay #{oid}", time.time())
    if karar == "onay" and o["tur"] == "claude_gorev":
        log(f"Claude gorevi onaylandi #{oid} (Claude Code kopru henuz yok, gorev listesine eklendi)")
        db.yaz("INSERT INTO gorevler (metin,zaman,kaynak,olusturma) VALUES (?,?,?,?)",
               o["baslik"].removeprefix("İş isteği: "), None, f"onay #{oid}", time.time())
    if karar == "onay" and o["tur"] == "taslak_teklif":
        mesaj = db.oku("SELECT * FROM mesajlar WHERE id=?", o["mesaj_id"])
        if mesaj:
            threading.Thread(target=_baglam["taslak_hazirla"], args=(mesaj[0],), daemon=True).start()
            log(f"taslak isteniyor (onay #{oid}): {o['sohbet_adi']}")
    log(f"onay #{oid} {durum}")
    return {"tamam": True}


# ---------- görevler ----------

@router.get("/cihaz/liste")
def cihaz_liste():
    return cihaz.liste()


@router.post("/cihaz/komut")
def cihaz_komut(govde: dict = Body(...)):
    return {"durum": cihaz.komut(str(govde.get("hedef")), str(govde.get("islem")), govde.get("deger"))}


@router.get("/cihaz/bekleyen/{hedef}")
def cihaz_bekleyen(hedef: str):
    return cihaz.bekleyen(hedef)


@router.get("/pano")
def pano_oku():
    return pano.oku()


@router.get("/ozet")
def ozet_oku():
    o = ozet.oku()
    o["hazirlaniyor"] = o.get("hazirlaniyor") and ozet._durum["calisiyor"]
    return o


@router.post("/ozet/yenile")
def ozet_yenile(govde: dict = Body(default={})):
    if ozet._durum["calisiyor"]:
        return {"durum": "zaten hazırlanıyor"}
    threading.Thread(target=ozet.hazirla, args=(_baglam["kuyruk"], int(govde.get("saat", 24))), daemon=True).start()
    return {"durum": "başladı"}


@router.get("/pano/gecmis")
def pano_gecmis(n: int = 50):
    return pano.gecmis(min(n, 500))


@router.post("/pano")
def pano_yaz(govde: dict = Body(...)):
    return {"kabul": pano.yaz(str(govde.get("metin", "")), str(govde.get("kaynak", "?")))}


@router.post("/bildirim")
def bildirim_yaz(govde: dict = Body(...)):
    """Telefondan gelen bildirim/SMS toplu listesi: [{paket, baslik, metin, tur, zaman}]; OTP süzülür."""
    kabul = sum(bildirim.yaz(str(x.get("paket", "?")), x.get("baslik"), x.get("metin"), str(x.get("tur", "bildirim")), x.get("zaman"))
                for x in (govde.get("liste") or [])[:200])
    return {"kabul": kabul}


@router.get("/bildirim")
def bildirim_liste(n: int = 100, tur: str = "", paket: str = ""):
    return bildirim.liste(min(n, 1000), tur or None, paket or None)


@router.get("/gorevler")
def gorevler(durum: str = "acik"):
    return db.oku("SELECT * FROM gorevler WHERE durum=? ORDER BY zaman IS NULL, zaman, olusturma DESC", durum)


@router.post("/gorevler")
def gorev_ekle(govde: dict = Body(...)):
    if not (govde.get("metin") or "").strip():
        raise HTTPException(400, "metin boş")
    gid = db.yaz("INSERT INTO gorevler (metin,zaman,kaynak,olusturma) VALUES (?,?,?,?)",
                 govde["metin"].strip(), govde.get("zaman"), govde.get("kaynak", "uygulama"), time.time())
    return {"id": gid}


@router.post("/gorev/{gid}")
def gorev_guncelle(gid: int, govde: dict = Body(...)):
    for alan in ("metin", "zaman", "durum"):
        if alan in govde:
            db.yaz(f"UPDATE gorevler SET {alan}=? WHERE id=?", govde[alan], gid)
    return {"tamam": True}


# ---------- WhatsApp sohbetleri ----------

def _modlar():
    try:
        modlar = json.loads((VERI / "sohbet-modlari.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        modlar = {}
    try:  # kapalı sohbetler haric.json'da tutulur; uygulamaya "kapali" olarak görünmeli (yoksa varsayılan moda dönmüş gibi görünür)
        for sid in json.loads((VERI / "haric.json").read_text()).get("sohbetler", []):
            modlar[sid] = "kapali"
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return modlar


@router.get("/sohbetler")
def sohbetler():
    r = db.oku("""SELECT m.sohbet_id, m.sohbet_adi, m.grup, m.metin son_metin, m.gonderen_adi son_gonderen, m.zaman son_zaman,
                         (SELECT COUNT(*) FROM taslaklar t WHERE t.sohbet_id=m.sohbet_id AND t.durum='bekliyor') taslak
                  FROM mesajlar m JOIN (SELECT sohbet_id, MAX(zaman) z FROM mesajlar GROUP BY sohbet_id) s
                  ON s.sohbet_id=m.sohbet_id AND s.z=m.zaman GROUP BY m.sohbet_id ORDER BY m.zaman DESC LIMIT 300""")
    modlar = _modlar()
    for x in r:
        x["mod"] = modlar.get(x["sohbet_id"], "onemli" if x["grup"] else "tam")
    return r


@router.get("/sohbet/{sid}")
def sohbet(sid: str, limit: int = 80):
    mesajlar = db.son_mesajlar(sid, limit)
    metinler = {m["id"]: m for m in mesajlar}
    for m in mesajlar:
        m["eleme"] = json.loads(m["eleme"]) if m.get("eleme") else None
        a = metinler.get(m.get("alinti_id"))
        m["alinti"] = {"gonderen": a["gonderen_adi"], "metin": a["metin"][:120]} if a else None
    taslaklar = [t for t in db.taslaklar("bekliyor") if t["sohbet_id"] == sid]
    return {"mesajlar": mesajlar, "taslaklar": taslaklar, "mod": _modlar().get(sid), "kisi": db.kisi(sid)}


@router.post("/sohbet/{sid}/mod")
def sohbet_mod(sid: str, govde: dict = Body(...)):
    mod = govde.get("mod")
    if mod not in ("tam", "onemli", "kapali"):
        raise HTTPException(400, "mod: tam | onemli | kapali")
    modlar = {k: v for k, v in _modlar().items() if v != "kapali"}
    haric_yol = VERI / "haric.json"
    haric = set(json.loads(haric_yol.read_text()).get("sohbetler", [])) if haric_yol.exists() else set()
    if mod == "kapali":
        haric.add(sid)
        modlar.pop(sid, None)
    else:
        haric.discard(sid)
        modlar[sid] = mod
    haric_yol.write_text(json.dumps({"sohbetler": sorted(haric)}, ensure_ascii=False))
    (VERI / "sohbet-modlari.json").write_text(json.dumps(modlar, ensure_ascii=False))
    log(f"sohbet modu degisti: {sid.split('@')[0][:6]}… -> {mod}")
    return {"tamam": True}


# ---------- konuşma (yazılı veya sesli) ----------

# Değişmeyen kısım başta, değişenler (durum, saat) sonda: model baştaki kısmı önbellekten tekrar kullanır,
# her soruda bütün metni baştan okumaz (bu işlemcide okuma saniyede ~12 kelime, asıl gecikme buydu).
SOHBET_SISTEM = sahip.doldur(
    "Sen Tulpar'sın (diğer adın Kâhya): {SAHIP_TAM} adlı kişinin (sahibinin) kişisel asistanı. Türkçe, kısa ve samimi konuş; "
    "sesli okunacağı için 1-3 cümleyi geçme, liste ve emoji kullanma. Bilmediğini uydurma.\n"
    "Sahibi hakkında bildiklerin:\n{hafiza}\n"
    "Sahibinin güncel durumu:\n{durum}\nŞu an: {bugun}"
)


def _sistem(bugun):
    """Sohbet istemi: hafıza nadiren değiştiği için durumdan önce (önbellek dostu)."""
    bilgiler = db.oku("SELECT bilgi FROM hafiza ORDER BY (guven='kesin') DESC, guncel DESC LIMIT 40")
    return (SOHBET_SISTEM.replace("{hafiza}", "\n".join(f"- {b['bilgi']}" for b in bilgiler) or "- (henüz yok)")
            .replace("{bugun}", bugun).replace("{durum}", _durum_ozeti()))


def _durum_ozeti():
    a = ana()
    satir = [f"Bekleyen taslak: {a['taslak_sayisi']}, onay bekleyen: {len(a['onaylar'])}"]
    satir += [f"- onay: {o['baslik'][:70]}" for o in a["onaylar"][:3]]
    satir += [f"- görev: {g['metin'][:60]} ({g['zaman'] or 'zamansız'})" for g in a["gorevler"][:5]]
    satir += [f"- önemli: {o['sohbet_adi']}: {(o['eleme'].get('ozet') or o['metin'])[:70]}" for o in a["onemli"][:4]]
    return "\n".join(satir)


# Bu kelimeler geçiyorsa bir iş isteniyor olabilir; geçmiyorsa sohbet sayılır ve araç kararı atlanır (hız için)
ISTEK_IPUCU = re.compile(r"(?i)\b(ekle|kaydet|hatırlat|hatirlat|takvim|randevu|alarm|kur|aç|ac|kapat|başlat|durdur|araştır|arastir|"
                         r"bul|ara\b|özetle|ozetle|yaz|gönder|gonder|taslak|söyle|soyle|kod|site|proje|düzelt|duzelt|ekran|görev|gorev)")


# Araç kararına eklenen kurallar: eksik bilgiyi sor, eklemeden önce özetleyip onay al (çok adımlı konuşma)
ADIM_KURALI = (
    "\nÇOK ADIMLI KONUŞMA: Önceki mesajlar aynı konuşmanın parçası; sahibinin son mesajı önceki soruna cevap olabilir "
    "(örn. sen 'saat kaçta?' dedin, o 'akşam 7' dedi). takvim_ekle için baslik, tarih ve saat GEREKLİ; yer bilinmiyorsa bir kez sor. "
    "Gerekli bilgi eksikse arac='sor' ve parametreler={\"soru\": \"tek kısa soru\"}. "
    "Hepsi tamamsa ama sahibi henüz onaylamadıysa arac='onay_iste' ve parametreler={\"ozet\": \"... ekleyeyim mi?\"}. "
    "Sahibi son mesajında özeti onayladıysa (evet, ekle, tamam, olur) gerçek aracı (takvim_ekle) tüm parametrelerle döndür. "
    "Sahibi 'boş ver', 'iptal' dediyse arac='yok'."
)


def _arastir(soru, sid):
    """Araştırmayı arka planda yapar; sonucu sohbete Tulpar mesajı olarak yazar (bildirim /bildirimler'den gider)."""
    def model_sor(sistem, icerik):
        return _baglam["kuyruk"].ekle(Is("komut", sistem, icerik, json_cevap=False, aciklama=f"Araştırma özeti: {soru[:60]}")).bekle(900)  # sahibi istedi: acil
    try:
        sayfalar = tarayici.ara(soru)
        metin = tarayici.ozetle(soru, sayfalar, model_sor) if sayfalar else ""
        metin = metin or "Araştırdım ama soruya cevap veren okunabilir bir kaynak bulamadım."
    except tarayici.BotKorumasi:
        metin = "Arama sitesi bot koruması (CAPTCHA) çıkardı, şimdilik araştıramadım. Biraz sonra tekrar deneyebilirim."
    except Exception as e:
        log(f"arastirma hatasi: {type(e).__name__}: {e}")
        metin = "Araştırma yarıda kaldı, bir hata oldu. Tekrar denememi istersen söyle."
    if not sid or not db.oku("SELECT id FROM asistan_sohbet WHERE id=?", sid):
        sid = db.yaz("INSERT INTO asistan_sohbet (baslik, olusturma, guncel) VALUES (?,?,?)",
                     f"Araştırma: {soru[:50]}", time.time(), time.time())
    db.yaz("INSERT INTO asistan_mesaj (sohbet_id, rol, metin, eylem, zaman) VALUES (?,?,?,?,?)", sid, "tulpar", metin,
           json.dumps({"tur": "arastirma_sonuc", "id": sid}), time.time())
    db.yaz("UPDATE asistan_sohbet SET guncel=? WHERE id=?", time.time(), sid)
    log(f"arastirma bitti #{sid}: {soru[:50]}")


def _taslak_yaz(kisi, talimat):
    """Sahibinin sözlü talimatından bir sohbete taslak yazar. O sohbette bekleyen taslak varsa onun yerine geçer (düzeltme).
    Kapalı (hariç) sohbete yazılmaz. Gönderim yine uygulamadan onayla olur."""
    kisi = (kisi or "").strip()
    if not kisi:
        return {"hata": "kimin için yazılacağı anlaşılmadı"}
    # Kişi adı rehberdeki ad olmayabilir (WhatsApp'ta "@UzayGezgini" görünen kişi sahibin "Burak" dediği kişi olabilir): sohbeti modele seçtir
    haric = set()
    try:
        haric = set(json.loads((VERI / "haric.json").read_text()).get("sohbetler", []))
    except FileNotFoundError:
        pass
    adaylar = []
    for c in db.oku("""SELECT sohbet_id, sohbet_adi, grup, MAX(zaman) z FROM mesajlar WHERE benden=0 AND zaman>? AND sohbet_id NOT LIKE '%newsletter%'
                       AND sohbet_id NOT LIKE '%broadcast%' GROUP BY sohbet_id ORDER BY z DESC LIMIT 12""", time.time() - 3 * 86400):
        if c["sohbet_id"] in haric:
            continue
        son = [m for m in db.son_mesajlar(c["sohbet_id"], 12) if not m["benden"]][-3:]
        adaylar.append((c, son))
    if not adaylar:
        return {"hata": "son günlerde cevaplanacak mesaj yok"}
    liste = "\n".join(f"[{i}] {c['sohbet_adi']} ({'grup' if c['grup'] else 'özel'}) — son mesajlar: "
                      + " | ".join(f"{m.get('gonderen_adi')}: {m['metin'][:70]}" for m in son) for i, (c, son) in enumerate(adaylar))
    sistem = ('Sahibi bir kişiye mesaj yazdırmak istiyor. Sohbet adı rehberdeki ad olmayabilir (kişinin WhatsApp adı farklı olabilir). '
              'Sahibinin sözündeki ipuçlarından (kişinin adı, o kişinin yazdığı mesajların içeriği, özel mi grup mu) hangi sohbetin kastedildiğini seç. '
              'SADECE JSON: {"secim": sohbet_numarası, "emin": true|false}. Hiçbiri uymuyorsa {"secim": null}. Özel sohbeti, sahibi grup demedikçe tercih et.')
    k = _baglam["kuyruk"].ekle(Is("komut", sistem, f"Kişi: {kisi}\nSahibinin sözü: {talimat}\n\nSohbetler:\n{liste}", aciklama=f"Taslak için sohbet seçimi: {kisi}")).bekle(180) or {}
    i = k.get("secim")
    if not isinstance(i, int) or not 0 <= i < len(adaylar):
        return {"hata": f"'{kisi}' hangi sohbet anlaşılamadı; sohbetin adını söyler misin?"}
    c, kayitlar = adaylar[i]
    sid, ad = c["sohbet_id"], c["sohbet_adi"]
    kimden = None
    if c["grup"]:  # grupta: adı geçen kişinin mesajlarına cevap
        kimden = next((m["gonderen_adi"] for m in reversed(kayitlar) if kisi.lower() in (m.get("gonderen_adi") or "").lower()), None)
        ad = f"{ad} (grup)"
    try:
        if sid in set(json.loads((VERI / "haric.json").read_text()).get("sohbetler", [])):
            return {"hata": "bu sohbet kapalı, yazamam"}
    except FileNotFoundError:
        pass
    gelen = [m for m in db.son_mesajlar(sid, 40) if not m["benden"] and (not kimden or m["gonderen_adi"] == kimden)][-3:] or db.son_mesajlar(sid, 1)
    for t in db.taslaklar("bekliyor"):
        if t["sohbet_id"] == sid:
            db.taslak_durum(t["id"], "reddedildi")  # eski taslak yerine yenisi (ders sayılmaz)
    tid = taslak.hazirla(_baglam["kuyruk"], sid, ad, gelen, talimat=talimat)
    yeni = next((t for t in db.taslaklar("bekliyor") if t["id"] == tid), None)
    if not yeni or not yeni["mesajlar"]:
        return {"hata": "taslak üretilemedi"}
    metin = " / ".join(m["metin"] for m in yeni["mesajlar"][0]["mesajlar"])
    log(f"sesli talimatla taslak #{tid}: {ad}")
    return {"tid": tid, "ad": ad, "metin": metin}


def arastirma_toparla():
    """Servis yeniden başlayınca yarım kalan araştırmaları (başlatıldı ama sonucu yazılmadı) soruyla yeniden başlatır."""
    for satir in db.oku("""SELECT DISTINCT sohbet_id FROM asistan_mesaj WHERE eylem LIKE '%"arastirma"%' AND zaman>?""", time.time() - 6 * 3600):
        sid = satir["sohbet_id"]
        bekleyen = db.oku("""SELECT m.id, m.zaman FROM asistan_mesaj m WHERE m.sohbet_id=? AND m.eylem LIKE '%"arastirma"%'
                             AND NOT EXISTS (SELECT 1 FROM asistan_mesaj r WHERE r.sohbet_id=m.sohbet_id AND r.zaman>m.zaman
                                             AND r.eylem LIKE '%arastirma_sonuc%') ORDER BY m.id DESC LIMIT 1""", sid)
        if not bekleyen:
            continue
        soru = db.oku("SELECT metin FROM asistan_mesaj WHERE sohbet_id=? AND rol='ben' AND id<? ORDER BY id DESC LIMIT 1", sid, bekleyen[0]["id"])
        if soru:
            log(f"yarim kalan arastirma yeniden baslatildi #{sid}")
            threading.Thread(target=_arastir, args=(soru[0]["metin"].strip(), sid), daemon=True).start()


def _arac_uygula(metin, dogrudan=False, gecmis=None, sid=None):
    """Önce hangi aracın gerektiğine karar verir ve uygular; cevap için sistem istemini hazırlar.
    dogrudan: kuyruğu beklemeden modele sor (anlık sesli konuşma için; model paralel istek işleyebiliyor).
    gecmis: sohbetin önceki mesajları; çok adımlı işlerde (eksik bilgiyi sorma, onay) bağlam.
    sid: konuşmanın sohbeti; arka plan işlerinin (araştırma) sonucu buraya yazılır."""
    k, bugun = _baglam["kuyruk"], _baglam["bugun"]()
    istem = _baglam["istem"]["system_tool"].replace("{bugun}", bugun) + ADIM_KURALI
    if dogrudan:
        karar = llm.sor("hizli", istem, metin, gecmis=gecmis, slot=2)
    else:
        karar = k.ekle(Is("komut", istem, metin, aciklama=f"Hangi araç gerekli: {metin[:60]}")).bekle(180)
    karar = karar or {}
    arac, p = karar.get("arac", "yok"), karar.get("parametreler") or {}
    eylem, ek = None, ""
    if arac in ("takvim_ekle", "hatirlatici"):
        zaman = " ".join(x for x in (p.get("tarih"), p.get("saat")) if x) or p.get("zaman")
        baslik = p.get("baslik") or p.get("metin") or metin
        if p.get("yer"):
            baslik += f" ({p['yer']})"
        gid = gorev_ekle({"metin": baslik, "zaman": zaman, "kaynak": "konuşma"})["id"]
        eylem = {"tur": "gorev", "id": gid}
    elif arac == "ikinci_ekran":
        islem = "kapat" if str(p.get("durum", "")).lower().startswith("kap") else "ac"
        sonuc = subprocess.run(["/usr/local/bin/tulpar-ekran", islem], capture_output=True, text=True, timeout=60)
        eylem = {"tur": "ekran", "id": 0}
        log(f"ikinci ekran {islem}: {sonuc.returncode}")
    elif arac == "claude_code":
        oid = onay_ekle("claude_gorev", f"İş: {p.get('gorev_tanimi') or metin}"[:200], metin)
        eylem = {"tur": "onay", "id": oid}
    elif arac == "arastirma":
        soru = (p.get("soru") or metin).strip()
        threading.Thread(target=_arastir, args=(soru, sid), daemon=True).start()
        sistem = _sistem(bugun) + ("\nAz önce web'de araştırma başlattın: " + soru + ". Sonuç birkaç dakika içinde bu sohbete "
                                   "yazılacak ve bildirim gelecek. Bunu tek cümleyle söyle; cevabı tahmin etme, uydurma.")
        return arac, {"tur": "arastirma", "id": sid or 0}, sistem
    elif arac == "whatsapp_taslak":
        sonuc = _taslak_yaz(p.get("kisi"), metin)  # sahibin tüm sözü: araç parametresi bilgiyi kısaltabiliyor
        if sonuc.get("tid"):
            eylem = {"tur": "taslak", "id": sonuc["tid"],
                     "sabit": f"Taslağı hazırladım, onayını bekliyor ({sonuc['ad']}): {sonuc['metin']}"}  # model 'gönderdim' diyebiliyor: sabit cevap
            ek = (f"\nAz önce \"{sonuc['ad']}\" için WhatsApp taslağı hazırladın (henüz GÖNDERİLMEDİ): \"{sonuc['metin']}\". "
                  "Cevabına şu cümleyle başla: 'Taslağı hazırladım, onayını bekliyor:' ve ardından taslağı kısaca tekrar et. "
                  "'Gönderdim' veya 'iletildi' DEME.")
        else:
            ek = f"\nTaslak hazırlanamadı: {sonuc['hata']}. Bunu sahibine kısaca söyle."
    elif arac == "sor" and p.get("soru"):
        ek = f"\nİşi yapmak için eksik bilgi var. Sahibine SADECE şunu sor: {p['soru']}"
    elif arac == "onay_iste" and p.get("ozet"):
        ek = f"\nBilgiler tamam. Sahibine kısaca özetleyip onay iste: {p['ozet']}"
    sistem = _sistem(bugun)
    if eylem:
        ek = f"\nAz önce şunu yaptın: {arac} {json.dumps(p, ensure_ascii=False)}. Bunu kısaca söyle."
    return arac, eylem, sistem + ek


@router.post("/konus")
def konus(govde: dict = Body(...)):
    metin = (govde.get("metin") or "").strip()
    if not metin:
        raise HTTPException(400, "metin boş")
    hizli = cihaz.uygula(metin)  # basit cihaz komutu: model hiç çalışmaz
    if hizli:
        return {"cevap": hizli[0], "eylem": hizli[1], "arac": "cihaz"}
    arac, eylem, sistem = _arac_uygula(metin)
    sabit = eylem.pop("sabit", None) if eylem else None
    cevap = sabit or _baglam["kuyruk"].ekle(Is("komut", sistem, metin, json_cevap=False, aciklama=f"Sohbet cevabı: {metin[:60]}")).bekle(180) or "Şu an cevap veremedim."
    log(f"konusma: {metin[:50]} -> {arac}")
    return {"cevap": cevap.strip(), "eylem": eylem, "arac": arac}


# ---------- sohbetler (Claude/Gemini'deki gibi; geri dönülebilir) ----------



def _sohbet_gecmisi(sid):
    satirlar = db.oku("SELECT rol, metin FROM asistan_mesaj WHERE sohbet_id=? ORDER BY id DESC LIMIT ?", sid, ayarlar.al("sohbet_gecmis_mesaj"))
    ozet = (db.oku("SELECT ozet FROM asistan_sohbet WHERE id=?", sid) or [{}])[0].get("ozet")
    gecmis = [("user" if r["rol"] == "ben" else "assistant", r["metin"]) for r in reversed(satirlar)]
    if ozet:
        gecmis = [("user", f"(Bu sohbetin önceki kısmının özeti: {ozet})"), ("assistant", "Tamam, hatırlıyorum.")] + gecmis
    return gecmis


def _ozetle_gerekirse(sid):
    """Sohbet uzayınca eski mesajları kısa bir özete çevirir (model yavaşlamasın, konu kaybolmasın)."""
    n = db.oku("SELECT COUNT(*) n FROM asistan_mesaj WHERE sohbet_id=?", sid)[0]["n"]
    sinir = ayarlar.al("sohbet_gecmis_mesaj")
    if n <= sinir + 8 or n % 8:
        return
    eski = db.oku("SELECT rol, metin FROM asistan_mesaj WHERE sohbet_id=? ORDER BY id LIMIT ?", sid, n - sinir)
    onceki = (db.oku("SELECT ozet FROM asistan_sohbet WHERE id=?", sid) or [{}])[0].get("ozet") or ""
    metin = (f"Önceki özet: {onceki}\n" if onceki else "") + "\n".join(
        f"{'Sahibi' if m['rol'] == 'ben' else 'Tulpar'}: {m['metin']}" for m in eski)
    ozet = llm.sor("hizli", "Bu sohbeti 3-5 cümlede özetle; kararları, tarihleri, isimleri ve yarım kalan işleri koru.",
                   metin[-12000:], json_cevap=False)
    db.yaz("UPDATE asistan_sohbet SET ozet=? WHERE id=?", ozet.strip(), sid)


@router.get("/asistan/sohbetler")
def asistan_sohbetler():
    return db.oku("""SELECT s.id, s.baslik, s.guncel,
                       (SELECT metin FROM asistan_mesaj m WHERE m.sohbet_id=s.id ORDER BY id DESC LIMIT 1) son
                     FROM asistan_sohbet s ORDER BY s.guncel DESC LIMIT 100""")


@router.get("/asistan/sohbet/{sid}")
def asistan_sohbet(sid: int):
    mesajlar = db.oku("SELECT id, rol, metin, eylem, zaman FROM asistan_mesaj WHERE sohbet_id=? ORDER BY id", sid)
    for m in mesajlar:
        m["eylem"] = json.loads(m["eylem"]) if m["eylem"] else None
    return {"sohbet": (db.oku("SELECT * FROM asistan_sohbet WHERE id=?", sid) or [None])[0], "mesajlar": mesajlar}


@router.post("/asistan/sohbet/{sid}/sil")
def asistan_sohbet_sil(sid: int):
    db.yaz("DELETE FROM asistan_mesaj WHERE sohbet_id=?", sid)
    db.yaz("DELETE FROM asistan_sohbet WHERE id=?", sid)
    return {"tamam": True}


@router.post("/konus-akis")
def konus_akis(govde: dict = Body(...)):
    """Anlık konuşma: cevap üretildikçe satır satır JSON olarak akar (uygulama hemen göstermeye/okumaya başlar).
    sohbet_id verilirse o sohbete devam eder (geçmişi hatırlar), verilmezse yeni sohbet açılır."""
    metin = (govde.get("metin") or "").strip()
    if not metin:
        raise HTTPException(400, "metin boş")
    sid = govde.get("sohbet_id")
    simdi = time.time()
    if not sid or not db.oku("SELECT id FROM asistan_sohbet WHERE id=?", sid):
        sid = db.yaz("INSERT INTO asistan_sohbet (baslik, olusturma, guncel) VALUES (?,?,?)", metin[:60], simdi, simdi)
    gecmis = _sohbet_gecmisi(sid)
    db.yaz("INSERT INTO asistan_mesaj (sohbet_id, rol, metin, zaman) VALUES (?,?,?,?)", sid, "ben", metin, simdi)
    # Tulpar son mesajında bir şey sorduysa bu mesaj o işin devamıdır: araç kararını atlama
    devam = bool(gecmis) and gecmis[-1][0] == "assistant" and gecmis[-1][1].rstrip().endswith("?")

    def uret():
        yield json.dumps({"tur": "basladi", "sohbet_id": sid}) + "\n"
        cevap, arac, eylem = [], "yok", None
        hizli = None if devam else cihaz.uygula(metin)
        if hizli:  # basit cihaz komutu (ses, parlaklık, müzik...): model çalışmadan anında yapılır
            tum = hizli[0]
            yield json.dumps({"tur": "eylem", "eylem": hizli[1], "arac": "cihaz"}, ensure_ascii=False) + "\n"
            yield json.dumps({"tur": "parca", "metin": tum}, ensure_ascii=False) + "\n"
            db.yaz("INSERT INTO asistan_mesaj (sohbet_id, rol, metin, eylem, zaman) VALUES (?,?,?,?,?)", sid, "tulpar", tum,
                   json.dumps(hizli[1]) if hizli[1] else None, time.time())
            db.yaz("UPDATE asistan_sohbet SET guncel=? WHERE id=?", time.time(), sid)
            yield json.dumps({"tur": "son", "soru": False}) + "\n"
            return
        with _baglam["kuyruk"].canli():
            if devam or ISTEK_IPUCU.search(metin):  # bir iş isteniyor veya süren iş: önce araç kararı
                arac, eylem, sistem = _arac_uygula(metin, dogrudan=True, gecmis=gecmis[-8:], sid=sid)
            else:  # sohbet/soru: araç kararını atla, hemen cevaba geç
                sistem = _sistem(_baglam["bugun"]())
            sabit = eylem.pop("sabit", None) if eylem else None
            yield json.dumps({"tur": "eylem", "eylem": eylem, "arac": arac}, ensure_ascii=False) + "\n"
            try:
                for parca in ([sabit] if sabit else llm.akis("hizli", sistem, metin, gecmis=gecmis, slot=2)):
                    cevap.append(parca)
                    yield json.dumps({"tur": "parca", "metin": parca}, ensure_ascii=False) + "\n"
            except Exception as e:
                yield json.dumps({"tur": "hata", "metin": str(e)}, ensure_ascii=False) + "\n"
        tum = "".join(cevap).strip()
        db.yaz("INSERT INTO asistan_mesaj (sohbet_id, rol, metin, eylem, zaman) VALUES (?,?,?,?,?)", sid, "tulpar",
               tum, json.dumps(eylem) if eylem else None, time.time())
        db.yaz("UPDATE asistan_sohbet SET guncel=? WHERE id=?", time.time(), sid)
        threading.Thread(target=_ozetle_gerekirse, args=(sid,), daemon=True).start()
        threading.Thread(target=_hafizaya_yaz, args=(sid, metin, tum), daemon=True).start()
        log(f"konusma (akis) #{sid}: {metin[:50]} -> {arac}")
        yield json.dumps({"tur": "son", "soru": tum.endswith("?")}) + "\n"

    return StreamingResponse(uret(), media_type="application/x-ndjson")


@router.post("/ses/isit")
def ses_isit():
    """Uygulama mikrofona basınca çağırır: Whisper'ı konuşma bitmeden belleğe al (açılış süresi beklenmesin)."""
    ses.hazirla()
    return {"tamam": True}


@router.post("/ses")
async def ses_yaziya(istek: Request):
    """Uygulamadan gelen ses kaydı (m4a/ogg/wav) -> metin. Kayıt yazıya dökülünce silinir."""
    veri = await istek.body()
    if not veri or len(veri) > 25 * 1024 * 1024:
        raise HTTPException(400, "ses boş veya çok büyük")
    with tempfile.NamedTemporaryFile(suffix=".m4a", dir=VERI, delete=True) as f:
        f.write(veri)
        f.flush()
        metin = ses.yaziya_dok(f.name)
    return {"metin": metin}


@router.get("/bildirimler")
def bildirimler(sonra: float = 0):
    """Uygulamanın yoklayıp telefon bildirimi göstereceği yeni önemli şeyler."""
    yeni = db.oku("""SELECT id, sohbet_adi, metin, zaman, eleme FROM mesajlar WHERE benden=0 AND zaman>?
                     AND eleme LIKE '%"onem": "yuksek"%' ORDER BY zaman LIMIT 20""", sonra)
    for y in yeni:
        y["eleme"] = json.loads(y["eleme"])
    taslak = db.oku("SELECT id, sohbet_adi, ozet, olusturma FROM taslaklar WHERE durum='bekliyor' AND olusturma>?", sonra)
    onay = db.oku("SELECT id, baslik, olusturma FROM onaylar WHERE durum='bekliyor' AND olusturma>?", sonra)
    arastirma = db.oku("""SELECT m.sohbet_id, s.baslik, m.metin FROM asistan_mesaj m JOIN asistan_sohbet s ON s.id=m.sohbet_id
                          WHERE m.rol='tulpar' AND m.eylem LIKE '%arastirma_sonuc%' AND m.zaman>? ORDER BY m.zaman""", sonra)
    return {"zaman": time.time(), "onemli": yeni, "taslaklar": taslak, "onaylar": onay, "arastirmalar": arastirma}


# ---------- telefondan terminal ----------

@router.get("/terminal")
def terminal_bilgi():
    """Uygulamanın HP terminaline (ttyd, 7681) bağlanması için parola. Sadece Tulpar anahtarıyla verilir."""
    yol = VERI / "terminal-parola"
    if not yol.exists():
        raise HTTPException(503, "terminal servisi kurulu değil")
    return {"port": 7681, "kullanici": "tulpar", "parola": yol.read_text().strip()}


# ---------- uygulama güncelleme (APK HP'den, Tulpar anahtarıyla) ----------

GUNCELLEME = VERI / "uygulama"


@router.get("/uygulama/surum")
def uygulama_surum():
    """En son APK'nın sürüm numarası (Android versionCode) ve boyutu; uygulama kendi sürümüyle karşılaştırır."""
    try:
        bilgi = json.loads((GUNCELLEME / "surum.json").read_text())
    except FileNotFoundError:
        return {"surum": 0}
    bilgi["boyut"] = (GUNCELLEME / "Tulpar.apk").stat().st_size
    return bilgi


@router.get("/uygulama/apk")
def uygulama_apk():
    yol = GUNCELLEME / "Tulpar.apk"
    if not yol.exists():
        raise HTTPException(404, "güncelleme yok")
    return FileResponse(yol, media_type="application/vnd.android.package-archive", filename="Tulpar.apk")



# ---------- kalıcı hafıza ("hakkımda") ----------

HAFIZA_SISTEM = sahip.doldur(
    "Sahibi ({SAHIP}) ile asistanı arasındaki son konuşmadan, sahibi hakkında KALICI ve işe yarar bilgileri çıkar: "
    "kim olduğu, ailesi ve yakınları, okulu/işi, alışkanlıkları, sevdikleri/sevmedikleri, önemli tarihler, tercihleri. "
    "Geçici şeyleri (bugünkü ruh hali, tek seferlik istek) ve zaten bilinenleri ALMA. Emin değilsen alma. "
    'SADECE JSON: {"bilgiler": ["kısa, tek cümlelik bilgi"]} (yoksa boş liste)'
)


def _hafizaya_yaz(sid, ben, tulpar):
    """Konuşmanın son turundan kalıcı bilgi çıkarır (arka plan işi, sahibini bekletmez)."""
    if len(ben) < 12:
        return
    bilinen = "\n".join(f"- {b['bilgi']}" for b in db.oku("SELECT bilgi FROM hafiza ORDER BY guncel DESC LIMIT 60"))
    try:
        cevap = _baglam["kuyruk"].ekle(Is("ozet", HAFIZA_SISTEM,
                                          f"Zaten bilinenler:\n{bilinen or '- yok'}\n\nSahibi: {ben}\nAsistan: {tulpar}")).bekle(900) or {}
    except Exception:
        return
    simdi = time.time()
    for b in (cevap.get("bilgiler") or [])[:3]:
        b = str(b).strip()
        if 8 <= len(b) <= 200 and not db.oku("SELECT id FROM hafiza WHERE lower(bilgi)=lower(?)", b):
            db.yaz("INSERT INTO hafiza (bilgi, kaynak, olusturma, guncel) VALUES (?,?,?,?)", b, f"sohbet #{sid}", simdi, simdi)
            log(f"hafizaya eklendi: {b[:60]}")


@router.get("/hafiza")
def hafiza_listesi():
    return db.oku("SELECT * FROM hafiza ORDER BY guncel DESC")


@router.post("/hafiza")
def hafiza_ekle(govde: dict = Body(...)):
    """Sahibi elle ekler ya da düzeltir (id verilirse günceller). Elle girilen bilgi 'kesin' sayılır."""
    bilgi = (govde.get("bilgi") or "").strip()
    if not bilgi:
        raise HTTPException(400, "bilgi boş")
    if govde.get("id"):
        db.yaz("UPDATE hafiza SET bilgi=?, guven='kesin', guncel=? WHERE id=?", bilgi, time.time(), govde["id"])
        return {"id": govde["id"]}
    return {"id": db.yaz("INSERT INTO hafiza (bilgi, kaynak, guven, olusturma, guncel) VALUES (?,?,?,?,?)",
                         bilgi, "elle", "kesin", time.time(), time.time())}


@router.post("/hafiza/{hid}/sil")
def hafiza_sil(hid: int):
    db.yaz("DELETE FROM hafiza WHERE id=?", hid)
    return {"tamam": True}



# ---------- ayarlar (uygulamadan değiştirmek için) ----------

@router.get("/ayarlar")
def ayar_listesi():
    return ayarlar.liste()


@router.post("/ayarlar")
def ayar_degistir(govde: dict = Body(...)):
    try:
        deger = ayarlar.yaz(govde["anahtar"], govde["deger"])
    except (KeyError, ValueError) as e:
        raise HTTPException(400, str(e))
    log(f"ayar degisti: {govde['anahtar']} = {deger}")
    return {"deger": deger}


@router.get("/uygulama/vosk")
def uygulama_vosk():
    """Uyandırma kelimesi için Türkçe ses modeli (telefon dış siteye bağımlı kalmasın diye HP'den verilir)."""
    yol = GUNCELLEME / "vosk-tr.zip"
    if not yol.exists():
        raise HTTPException(404, "ses modeli HP'de yok")
    return FileResponse(yol, media_type="application/zip", filename="vosk-tr.zip")


@router.get("/uygulama/vosk-spk")
def uygulama_vosk_spk():
    """Konuşmacı (ses parmak izi) modeli: uyandırmayı sadece sahibinin sesine açmak için."""
    yol = GUNCELLEME / "vosk-spk.zip"
    if not yol.exists():
        raise HTTPException(404, "konuşmacı modeli HP'de yok")
    return FileResponse(yol, media_type="application/zip", filename="vosk-spk.zip")


@router.post("/tts")
def konus_sentez(govde: dict = Body(...)):
    """Metni HP'de Türkçe sesle okur ve WAV döndürür (uygulama cümle cümle çalar)."""
    metin = (govde.get("metin") or "").strip()
    if not metin or len(metin) > 600:
        raise HTTPException(400, "metin boş veya çok uzun")
    wav = tts.uret(metin)
    return Response(wav, media_type="audio/wav")
