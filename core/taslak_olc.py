"""Taslak yöntemlerini gerçek geçmişte ölçer: sahibin gerçek cevabı gizlenir, eski yöntem (son 15 mesaj) ve yeni yöntem
(+ benzer geçmiş durumlar + yazış alışkanlığı) aynı durumda taslak yazar. Çıktı: veri/eval/taslak-olc.json (hakem: Claude + benzerlik)."""
import json
import pathlib
import random
import sys
import time

import benzer
import db
import sahip
import taslak
import llm

N = int(sys.argv[1]) if len(sys.argv) > 1 else 24
SADECE_YENI = len(sys.argv) > 2 and sys.argv[2] == "yeni"
CIKTI = pathlib.Path.home() / ("tulpar/veri/eval/taslak-olc2.json" if SADECE_YENI else "tulpar/veri/eval/taslak-olc.json")


def vaka_sec():
    rastgele = random.Random(7)
    adaylar = db.oku("""SELECT m.id, m.sohbet_id, m.metin, m.zaman FROM mesajlar m WHERE m.benden=1 AND length(m.metin) BETWEEN 3 AND 150
                        AND m.zaman < strftime('%s','now') - 86400 AND m.grup=0 AND m.metin NOT LIKE '[%' AND m.metin NOT LIKE '%http%'""")
    rastgele.shuffle(adaylar)
    sonuc, sohbetler = [], set()
    for a in adaylar:
        if a["sohbet_id"] in sohbetler:
            continue
        onceki = db.oku("SELECT * FROM mesajlar WHERE sohbet_id=? AND zaman<? ORDER BY zaman DESC LIMIT 25", a["sohbet_id"], a["zaman"])[::-1]
        gelen = []
        for m in reversed(onceki):
            if m["benden"]:
                break
            gelen.insert(0, m)
        if gelen and len(onceki) >= 15 and sum(m["benden"] for m in onceki) >= 4:
            sonuc.append((a, onceki, gelen))
            sohbetler.add(a["sohbet_id"])
        if len(sonuc) >= N:
            break
    return sonuc


def yaz(istem):
    c = llm.sor("hizli", taslak.TASLAK_SISTEM, istem, slot=2)
    try:
        return " / ".join(m["metin"] for m in c["secenekler"][0]["mesajlar"])
    except Exception:  # noqa: BLE001
        return "(boş: " + str(c)[:80] + ")"


def main():
    sonuclar = []
    for a, onceki, gelen in vaka_sec():
        ad = gelen[0].get("sohbet_adi") or "kişi"
        sid = a["sohbet_id"]
        kendi = [m["metin"] for m in db.oku("SELECT metin FROM mesajlar WHERE benden=1 AND sohbet_id=? AND zaman<? ORDER BY zaman DESC LIMIT 15", sid, a["zaman"])
                 if len(m["metin"]) < 300]
        konusma = "\n".join(f"[{m['id']}] {sahip.AD if m['benden'] else m.get('gonderen_adi') or ad}: {m['metin']}" for m in onceki)
        gelen_txt = "\n".join(f"[{m['id']}] {m.get('gonderen_adi') or ad}: {m['metin']}" for m in gelen)
        temel = (f"{sahip.AD} adlı sahibin örnek mesajları:\n" + "\n".join(f"- {o}" for o in kendi) + "\n")
        son = f"\n\nSon konuşma (bağlam):\n{konusma}\n\nCEVAPLANACAK MESAJ(LAR) — SADECE bunlara cevap ver:\n{gelen_txt}\nBugün: {time.strftime('%Y-%m-%d %A %H:%M', time.localtime(a['zaman']))}"
        cift = benzer.benzer_cevaplar(sid, [m["metin"] for m in gelen], once=a["zaman"])
        ek = ("\n\nBENZER GEÇMİŞ DURUMLAR (karşı taraf ne yazdı -> sahibi nasıl cevap verdi; SADECE ÜSLUBU (kelime seçimi, uzunluk, hitap) buradan öğren; KARAR sahibine aittir, bilmediğin kararlar için yine ayrı SEÇENEKLER hazırla):\n"
              + "\n".join(f"- \"{g[:150]}\" -> \"{c}\"" for g, c in cift)) if cift else ""
        ek += "\n" + benzer.uslup_ozeti(sid)
        eski = "-" if SADECE_YENI else yaz(temel + son)
        yeni = yaz(temel + ek + son)
        gercek = a["metin"]
        puan = lambda x: round(benzer._kosinus(benzer._ngram(x), benzer._ngram(gercek)), 3)  # noqa: E731
        sonuclar.append({"gelen": [m["metin"] for m in gelen], "gercek": gercek, "eski": eski, "yeni": yeni,
                         "benzer_eski": puan(eski), "benzer_yeni": puan(yeni), "bulunan_ornek": len(cift)})
        CIKTI.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=1))
        print(len(sonuclar), "tamam", flush=True)


main()
