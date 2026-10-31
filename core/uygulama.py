"""Android uygulamasının kullandığı uç noktalar: ana ekran, onaylar, görevler, sohbetler, konuşma, ses."""
import json
import pathlib
import re
import subprocess
import tempfile
import threading
import time

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

import db
import llm
import sahip
import ses
from kuyruk import Is, log

VERI = pathlib.Path.home() / "tulpar/veri"
REDDEDILEN_SAKLA_SN = 7 * 86400
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


def elemeden_onay(m, sonuc):
    """Eleme sonucuna göre onay kartı açar (takvim, Claude işi, güvenlik uyarısı)."""
    kim = m.get("sohbet_adi") or "?"
    ozet = sonuc.get("ozet") or m["metin"][:120]
    if sonuc.get("aksiyon") == "uyar":
        onay_ekle("uyari", f"Şüpheli mesaj: {kim}", " ".join(sonuc.get("kural_notlari") or [ozet]), m)
    elif sonuc.get("aksiyon") == "takvim" and sonuc.get("onem") == "yuksek":
        onay_ekle("takvim", f"Takvime ekle: {ozet}", f"{kim} yazdı: {m['metin'][:300]}", m,
                  {"tarih": sonuc.get("tarih"), "saat": sonuc.get("saat")})
    elif sonuc.get("aksiyon") == "claude_gorev" and sonuc.get("kime") != "baskasi":
        onay_ekle("claude_gorev", f"İş isteği: {ozet}", f"{kim} yazdı: {m['metin'][:500]}", m)


@router.get("/ana")
def ana():
    db.yaz("DELETE FROM onaylar WHERE durum='reddedildi' AND karar<?", time.time() - REDDEDILEN_SAKLA_SN)
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
        return json.loads((VERI / "sohbet-modlari.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


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
    modlar = _modlar()
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
                         r"bul|ara\b|özetle|ozetle|yaz|gönder|gonder|taslak|kod|site|proje|düzelt|duzelt|ekran|görev|gorev)")


# Araç kararına eklenen kurallar: eksik bilgiyi sor, eklemeden önce özetleyip onay al (çok adımlı konuşma)
ADIM_KURALI = (
    "\nÇOK ADIMLI KONUŞMA: Önceki mesajlar aynı konuşmanın parçası; sahibinin son mesajı önceki soruna cevap olabilir "
    "(örn. sen 'saat kaçta?' dedin, o 'akşam 7' dedi). takvim_ekle için baslik, tarih ve saat GEREKLİ; yer bilinmiyorsa bir kez sor. "
    "Gerekli bilgi eksikse arac='sor' ve parametreler={\"soru\": \"tek kısa soru\"}. "
    "Hepsi tamamsa ama sahibi henüz onaylamadıysa arac='onay_iste' ve parametreler={\"ozet\": \"... ekleyeyim mi?\"}. "
    "Sahibi son mesajında özeti onayladıysa (evet, ekle, tamam, olur) gerçek aracı (takvim_ekle) tüm parametrelerle döndür. "
    "Sahibi 'boş ver', 'iptal' dediyse arac='yok'."
)


def _arac_uygula(metin, dogrudan=False, gecmis=None):
    """Önce hangi aracın gerektiğine karar verir ve uygular; cevap için sistem istemini hazırlar.
    dogrudan: kuyruğu beklemeden modele sor (anlık sesli konuşma için; model paralel istek işleyebiliyor).
    gecmis: sohbetin önceki mesajları; çok adımlı işlerde (eksik bilgiyi sorma, onay) bağlam."""
    k, bugun = _baglam["kuyruk"], _baglam["bugun"]()
    istem = _baglam["istem"]["system_tool"].replace("{bugun}", bugun) + ADIM_KURALI
    if dogrudan:
        karar = llm.sor("hizli", istem, metin, gecmis=gecmis)
    else:
        karar = k.ekle(Is("komut", istem, metin)).bekle(180)
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
    arac, eylem, sistem = _arac_uygula(metin)
    cevap = _baglam["kuyruk"].ekle(Is("komut", sistem, metin, json_cevap=False)).bekle(180) or "Şu an cevap veremedim."
    log(f"konusma: {metin[:50]} -> {arac}")
    return {"cevap": cevap.strip(), "eylem": eylem, "arac": arac}


# ---------- sohbetler (Claude/Gemini'deki gibi; geri dönülebilir) ----------

GECMIS_MESAJ = 16  # modele verilen son mesaj sayısı; daha eskisi özetle temsil edilir


def _sohbet_gecmisi(sid):
    satirlar = db.oku("SELECT rol, metin FROM asistan_mesaj WHERE sohbet_id=? ORDER BY id DESC LIMIT ?", sid, GECMIS_MESAJ)
    ozet = (db.oku("SELECT ozet FROM asistan_sohbet WHERE id=?", sid) or [{}])[0].get("ozet")
    gecmis = [("user" if r["rol"] == "ben" else "assistant", r["metin"]) for r in reversed(satirlar)]
    if ozet:
        gecmis = [("user", f"(Bu sohbetin önceki kısmının özeti: {ozet})"), ("assistant", "Tamam, hatırlıyorum.")] + gecmis
    return gecmis


def _ozetle_gerekirse(sid):
    """Sohbet uzayınca eski mesajları kısa bir özete çevirir (model yavaşlamasın, konu kaybolmasın)."""
    n = db.oku("SELECT COUNT(*) n FROM asistan_mesaj WHERE sohbet_id=?", sid)[0]["n"]
    if n <= GECMIS_MESAJ + 8 or n % 8:
        return
    eski = db.oku("SELECT rol, metin FROM asistan_mesaj WHERE sohbet_id=? ORDER BY id LIMIT ?", sid, n - GECMIS_MESAJ)
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
        with _baglam["kuyruk"].canli():
            if devam or ISTEK_IPUCU.search(metin):  # bir iş isteniyor veya süren iş: önce araç kararı
                arac, eylem, sistem = _arac_uygula(metin, dogrudan=True, gecmis=gecmis[-8:])
            else:  # sohbet/soru: araç kararını atla, hemen cevaba geç
                sistem = _sistem(_baglam["bugun"]())
            yield json.dumps({"tur": "eylem", "eylem": eylem, "arac": arac}, ensure_ascii=False) + "\n"
            try:
                for parca in llm.akis("hizli", sistem, metin, gecmis=gecmis):
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
    return {"zaman": time.time(), "onemli": yeni, "taslaklar": taslak, "onaylar": onay}


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
