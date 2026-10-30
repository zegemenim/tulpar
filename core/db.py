"""Tulpar hafızası: SQLite. Mesajlar, kişi kartları ve taslaklar burada; hepsi HP'de kalır."""
import json
import pathlib
import sqlite3
import threading
import time

YOL = pathlib.Path.home() / "tulpar/veri/tulpar.db"
_kilit = threading.Lock()

SEMA = """
CREATE TABLE IF NOT EXISTS kisiler (
  id TEXT PRIMARY KEY,           -- WhatsApp kimliği (905xx@c.us) veya sms:+905xx
  ad TEXT,
  iliski TEXT DEFAULT 'bilinmiyor', -- aile | yakin | arkadas | hoca | ogrenci | resmi | is | bilinmiyor
  hitap TEXT,                    -- sahibi ona nasıl hitap ediyor: "anne", "Murat Bey", "kanka"
  sen_siz TEXT,                  -- sen | siz | null
  notlar TEXT,
  guven TEXT DEFAULT 'tahmin',   -- kesin (sahibi söyledi/düzeltti) | tahmin (Tulpar çıkardı)
  guncel REAL
);
CREATE TABLE IF NOT EXISTS mesajlar (
  id TEXT PRIMARY KEY,
  kaynak TEXT,                   -- whatsapp | sms | bildirim
  sohbet_id TEXT, sohbet_adi TEXT, grup INTEGER,
  gonderen_id TEXT, gonderen_adi TEXT,
  benden INTEGER,                -- 1 = sahibi yazdı (üslup öğrenmek için)
  metin TEXT, alinti_id TEXT, zaman REAL,
  eleme TEXT                     -- model + kural sonucu (JSON)
);
CREATE INDEX IF NOT EXISTS mesaj_sohbet ON mesajlar(sohbet_id, zaman);
CREATE TABLE IF NOT EXISTS onaylar (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tur TEXT,                      -- claude_gorev | takvim | uyari
  baslik TEXT, aciklama TEXT,
  sohbet_id TEXT, sohbet_adi TEXT, mesaj_id TEXT,
  veri TEXT,                     -- tarih/saat vb. (JSON)
  durum TEXT DEFAULT 'bekliyor', -- bekliyor | onaylandi | reddedildi (reddedilenler 7 gün sonra silinir)
  olusturma REAL, karar REAL
);
CREATE TABLE IF NOT EXISTS gorevler (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  metin TEXT, zaman TEXT,        -- zaman: 'YYYY-MM-DD HH:MM' veya null
  durum TEXT DEFAULT 'acik',     -- acik | bitti
  kaynak TEXT, olusturma REAL
);
CREATE TABLE IF NOT EXISTS taslaklar (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sohbet_id TEXT, sohbet_adi TEXT,
  mesaj_idler TEXT,              -- cevaplanan gelen mesajlar (JSON)
  ozet TEXT,
  mesajlar TEXT,                 -- seçenekler: [{"etiket":..,"mesajlar":[{"yanit_id":..,"metin":..}]}] (JSON); gönderilince gönderilen mesajlar
  uyarilar TEXT,                 -- kural/üslup uyarıları (JSON)
  durum TEXT DEFAULT 'bekliyor', -- bekliyor | gonderildi | reddedildi | hata
  olusturma REAL, guncel REAL
);
"""


def baglan():
    YOL.parent.mkdir(parents=True, exist_ok=True)
    b = sqlite3.connect(YOL, check_same_thread=False)
    b.row_factory = sqlite3.Row
    b.executescript(SEMA)
    return b


_b = baglan()


def yaz(sql, *p):
    with _kilit:
        c = _b.execute(sql, p)
        _b.commit()
        return c.lastrowid


def oku(sql, *p):
    with _kilit:
        return [dict(r) for r in _b.execute(sql, p).fetchall()]


def mesaj_kaydet(m):
    yaz("""INSERT OR IGNORE INTO mesajlar (id,kaynak,sohbet_id,sohbet_adi,grup,gonderen_id,gonderen_adi,benden,metin,alinti_id,zaman)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        m["id"], m.get("kaynak", "whatsapp"), m["sohbet_id"], m.get("sohbet_adi"), int(m.get("grup", False)),
        m.get("gonderen_id"), m.get("gonderen_adi"), int(m.get("benden", False)), m.get("metin", ""),
        m.get("alinti_id"), m.get("zaman", time.time()))


def eleme_kaydet(mesaj_id, sonuc):
    yaz("UPDATE mesajlar SET eleme=? WHERE id=?", json.dumps(sonuc, ensure_ascii=False), mesaj_id)


def son_mesajlar(sohbet_id, n=30):
    return list(reversed(oku("SELECT * FROM mesajlar WHERE sohbet_id=? ORDER BY zaman DESC LIMIT ?", sohbet_id, n)))


def benim_mesajlarim(sohbet_id=None, n=20):
    """sahibin yazdığı son mesajlar: üslup örneği. sohbet_id yoksa tüm sohbetlerden."""
    if sohbet_id:
        return oku("SELECT metin FROM mesajlar WHERE benden=1 AND sohbet_id=? ORDER BY zaman DESC LIMIT ?", sohbet_id, n)
    return oku("SELECT metin FROM mesajlar WHERE benden=1 ORDER BY zaman DESC LIMIT ?", n)


def kisi(id_):
    r = oku("SELECT * FROM kisiler WHERE id=?", id_)
    return r[0] if r else None


def kisi_kaydet(id_, **alanlar):
    eski = kisi(id_) or {"id": id_}
    if eski.get("guven") == "kesin" and alanlar.get("guven") != "kesin":
        alanlar = {k: v for k, v in alanlar.items() if k == "ad" or not eski.get(k)}  # sahibin bilgisini ezme
    eski.update({k: v for k, v in alanlar.items() if v is not None}, guncel=time.time())
    kolonlar = ["id", "ad", "iliski", "hitap", "sen_siz", "notlar", "guven", "guncel"]
    yaz(f"INSERT OR REPLACE INTO kisiler ({','.join(kolonlar)}) VALUES ({','.join('?' * len(kolonlar))})",
        *[eski.get(k) for k in kolonlar])
    return kisi(id_)


def taslak_ekle(sohbet_id, sohbet_adi, mesaj_idler, ozet, mesajlar, uyarilar):
    t = time.time()
    return yaz("""INSERT INTO taslaklar (sohbet_id,sohbet_adi,mesaj_idler,ozet,mesajlar,uyarilar,olusturma,guncel)
                  VALUES (?,?,?,?,?,?,?,?)""", sohbet_id, sohbet_adi, json.dumps(mesaj_idler),
               ozet, json.dumps(mesajlar, ensure_ascii=False), json.dumps(uyarilar, ensure_ascii=False), t, t)


def taslaklar(durum="bekliyor"):
    rows = oku("SELECT * FROM taslaklar WHERE durum=? ORDER BY olusturma DESC", durum)
    for r in rows:
        for k in ("mesaj_idler", "mesajlar", "uyarilar"):
            r[k] = json.loads(r[k] or "[]")
    return rows


def taslak_durum(id_, durum, mesajlar=None):
    if mesajlar is not None:
        yaz("UPDATE taslaklar SET durum=?, mesajlar=?, guncel=? WHERE id=?", durum,
            json.dumps(mesajlar, ensure_ascii=False), time.time(), id_)
    else:
        yaz("UPDATE taslaklar SET durum=?, guncel=? WHERE id=?", durum, time.time(), id_)
