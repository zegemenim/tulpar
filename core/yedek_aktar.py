"""Açılmış WhatsApp yedeğinden (msgstore.db) eski mesajları Tulpar hafızasına aktarır.

- Hariç tutulan sohbetler hem telefon kimliğiyle hem gizli kimlikle (LID) eşleştirilip tamamen atlanır.
- Sadece metin; medya yer tutucuyla ([fotoğraf] vb.) geçer. Sistem mesajları, aramalar, silinenler alınmaz.
- Zaten olan mesajlar (aynı kimlik) tekrar eklenmez; aynı sohbet mevcut kimliğiyle birleştirilir.
- Aktarılan mesajlar "geçmiş" işaretlidir: elenmez, bildirim üretmez; üslup ve eğitim içindir.
- Bitince açılmış veritabanı ve şifreli yedek silinir.
Kullanım: python3 yedek_aktar.py
"""
import json
import pathlib
import sqlite3

import sahip

VERI = pathlib.Path.home() / "tulpar/veri"
YEDEK = VERI / "yedek/msgstore.db"
SIFRELI = VERI / "yedek/msgstore.db.crypt15"
YER_TUTUCU = {1: "[fotoğraf]", 2: "[sesli mesaj]", 3: "[video]", 9: "[belge]", 13: "[gif]", 20: "[çıkartma]",
              4: "[kişi kartı]", 5: "[konum]", 42: "[tek seferlik fotoğraf]", 43: "[tek seferlik video]", 66: "[anket]"}
METIN_TURLERI = {0} | set(YER_TUTUCU)
GECMIS = json.dumps({"gecmis": True})


def main():
    y = sqlite3.connect(YEDEK)
    t = sqlite3.connect(VERI / "tulpar.db", timeout=120)
    haric = set(json.loads((VERI / "haric.json").read_text()).get("sohbetler", []))
    try:
        adlar = json.loads((VERI / "wa-adlar.json").read_text())
    except FileNotFoundError:
        adlar = {}
    haric_adlar = {k.lower() for k in haric if "@" not in k}

    jid = dict(y.execute("SELECT _id, raw_string FROM jid"))
    lid_pn = {jid[l]: jid[p] for l, p in y.execute("SELECT lid_row_id, jid_row_id FROM jid_map") if l in jid and p in jid}
    pn_lid = {p: l for l, p in lid_pn.items()}
    mevcut_id = {}  # key_id -> mevcut sohbet_id (bu sohbet Tulpar'da hangi kimlikle duruyor)
    for k, s in t.execute("SELECT id, sohbet_id FROM mesajlar"):
        mevcut_id[k] = s

    def ad(j):
        for x in (j, lid_pn.get(j), pn_lid.get(j)):
            if x and adlar.get(x, {}).get("ad"):
                return adlar[x]["ad"]
        return None

    istat = {"sohbet": 0, "haric_sohbet": 0, "eklenen": 0, "zaten_var": 0}
    for chat_id, jid_row, konu in y.execute("SELECT _id, jid_row_id, subject FROM chat").fetchall():
        ham = jid.get(jid_row, "")
        if not ham or ham.split("@")[-1] not in ("s.whatsapp.net", "lid", "g.us"):
            continue
        kimlikler = {ham, lid_pn.get(ham), pn_lid.get(ham)} - {None}
        sohbet_adi = konu or ad(ham) or ham.split("@")[0]
        if kimlikler & haric or sohbet_adi.lower() in haric_adlar:
            istat["haric_sohbet"] += 1
            continue
        satirlar = y.execute("""SELECT m.key_id, m.from_me, m.sender_jid_row_id, m.timestamp, m.message_type, m.text_data,
                                       mm.media_caption, q.key_id
                                FROM message m LEFT JOIN message_media mm ON mm.message_row_id=m._id
                                LEFT JOIN message_quoted q ON q.message_row_id=m._id
                                WHERE m.chat_row_id=? ORDER BY m.timestamp""", (chat_id,)).fetchall()
        if not satirlar:
            continue
        # sohbet Tulpar'da zaten varsa onun kimliğini kullan, yoksa telefon kimliğini tercih et
        sohbet_id = next((mevcut_id[k] for k, *_ in satirlar if k in mevcut_id), None) or lid_pn.get(ham, ham)
        grup = ham.endswith("@g.us")
        istat["sohbet"] += 1
        ekle = []
        for key_id, benden, gonderen_row, zaman, tur, metin, altyazi, alinti in satirlar:
            if tur not in METIN_TURLERI or not key_id:
                continue
            if key_id in mevcut_id:
                istat["zaten_var"] += 1
                continue
            yazi = metin or ""
            if tur != 0:
                yazi = YER_TUTUCU[tur] + (f" {altyazi or metin}" if (altyazi or metin) else "")
            if not yazi.strip():
                continue
            gonderen = jid.get(gonderen_row) if grup and gonderen_row else ham
            ekle.append((key_id, "whatsapp", sohbet_id, sohbet_adi, int(grup), "ben" if benden else gonderen,
                         sahip.AD if benden else (ad(gonderen) or (sohbet_adi if not grup else "~" + gonderen.split("@")[0][-4:])),
                         int(bool(benden)), yazi, alinti, zaman / 1000, GECMIS))
        t.executemany("""INSERT OR IGNORE INTO mesajlar (id,kaynak,sohbet_id,sohbet_adi,grup,gonderen_id,gonderen_adi,benden,
                         metin,alinti_id,zaman,eleme) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", ekle)
        t.commit()
        istat["eklenen"] += len(ekle)
    y.close()
    YEDEK.unlink()
    SIFRELI.unlink(missing_ok=True)
    print(json.dumps(istat, ensure_ascii=False), "— açılmış yedek ve şifreli dosya silindi")


if __name__ == "__main__":
    main()
