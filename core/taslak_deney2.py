"""İkinci tur deney: 30 vaka. Gece birinci turun kazananlarını (A1 benzer durumlar, A4 üslup kılavuzu) birleştirir ve kötü kalıpları
(yer tutucu, klavye ezmesi, yersiz hitap, tekrar) süzen kuralı dener. Çıktı: veri/eval/deney2.json. Kullanım: taslak_deney2.py [vaka] [azami_saat]"""
import json
import re
import sys
import time

import benzer
import db
import sahip
import taslak
import taslak_deney as d

N = int(sys.argv[1]) if len(sys.argv) > 1 else 30
AZAMI_SN = float(sys.argv[2]) * 3600 if len(sys.argv) > 2 else 14 * 3600
CIKTI = d.KLASOR / "deney2.json"
YER = re.compile(r"\[(video|fotoğraf|fotograf|çıkartma|sticker|ses|belge|konum|görsel|gif)[^\]]*\]", re.I)
EZME = re.compile(r"[bcçdfgğhjklmnprsştvyz]{6,}", re.I)  # 6+ ünsüz arka arkaya: klavye ezmesi (Türkçe'de yok)
SAMIMI_DISI = {"hoca", "resmi", "is", "aile"}


def suz(secenekler, kart):
    """Kötü kalıpları ayıklar; hepsi giderse özgün listeyi bırakır. Tekrarları kaldırır, en çok 3 seçenek."""
    temiz = []
    for s in secenekler:
        k = s.lower()
        if YER.search(s) or EZME.search(k):
            continue
        if re.search(r"\bhocam\b", k) and (kart or {}).get("iliski") not in {"hoca", "resmi", "is"}:
            continue
        if s not in temiz:
            temiz.append(s)
    return (temiz or list(dict.fromkeys(secenekler)))[:3]


def uret(a, onceki, gelen):
    sid, t = a["sohbet_id"], a["zaman"]
    ad = gelen[0].get("sohbet_adi") or "kişi"
    gelen_metin = [m["metin"] for m in gelen]
    gelen_txt = "\n".join(f"[{m['id']}] {m.get('gonderen_adi') or ad}: {m['metin']}" for m in gelen)
    konusma = "\n".join(f"[{m['id']}] {sahip.AD if m['benden'] else m.get('gonderen_adi') or ad}: {m['metin']}" for m in onceki)
    son = (f"\n\nSon konuşma (bağlam):\n{konusma}\n\nCEVAPLANACAK MESAJ(LAR) — SADECE bunlara cevap ver:\n{gelen_txt}\n"
           f"Bugün: {time.strftime('%Y-%m-%d %A %H:%M', time.localtime(t))}")
    kendi = [m["metin"] for m in db.oku("SELECT metin FROM mesajlar WHERE benden=1 AND sohbet_id=? AND zaman<? ORDER BY zaman DESC LIMIT 40", sid, t)
             if len(m["metin"]) < 300]
    c8 = benzer.benzer_cevaplar(sid, gelen_metin, n=8, once=t)
    c20 = benzer.benzer_cevaplar(sid, gelen_metin, n=20, once=t)
    uslup = benzer.uslup_ozeti(sid)
    kart = db.kisi(sid) or {}
    ct = lambda cs: ("\n\nBENZER GEÇMİŞ DURUMLAR (karşı taraf ne yazdı -> sahibi nasıl cevap verdi; SADECE ÜSLUBU öğren, karar sahibine aittir):\n"  # noqa: E731
                     + "\n".join(f"- \"{g[:150]}\" -> \"{c}\"" for g, c in cs)) if cs else ""
    temel = lambda n: f"{sahip.AD} adlı sahibin örnek mesajları:\n" + "\n".join(f"- {o}" for o in kendi[:n]) + "\n"  # noqa: E731
    kilavuz = "SAHİBİNİN ÜSLUP KILAVUZU (buna uy):\n" + d.PROFIL_METNI + "\n\n"
    sis = taslak.sistem()
    sonuc = {}

    def dene(ad_, f):
        t0 = time.time()
        try:
            s = f()
        except Exception as e:  # noqa: BLE001
            s = [f"(hata: {type(e).__name__}: {str(e)[:60]})"]
        sonuc[ad_] = {"secenekler": s, "sn": round(time.time() - t0)}

    dene("B0_temel", lambda: d.secenekler_json(d.sor(sis, temel(15) + son)))
    dene("B1_benzer", lambda: d.secenekler_json(d.sor(sis, temel(15) + ct(c8) + "\n" + uslup + son)))
    sonuc["B1s_benzer_suzgec"] = {"secenekler": suz(sonuc["B1_benzer"]["secenekler"], kart), "sn": 0}
    dene("B4_profil", lambda: d.secenekler_json(d.sor(sis, kilavuz + temel(8) + ct(c8) + son)))
    dene("B8_birlesik", lambda: d.secenekler_json(d.sor(sis, kilavuz + temel(15) + ct(c8) + "\n" + uslup + son)))
    sonuc["B8s_birlesik_suzgec"] = {"secenekler": suz(sonuc["B8_birlesik"]["secenekler"], kart), "sn": 0}
    dene("B10_birlesik_cok", lambda: d.secenekler_json(d.sor(sis, kilavuz + temel(30) + ct(c20) + "\n" + uslup + son)))
    sonuc["B10s_birlesik_cok_suzgec"] = {"secenekler": suz(sonuc["B10_birlesik_cok"]["secenekler"], kart), "sn": 0}
    return sonuc


def main():
    vakalar = d.vaka_sec_n(N)
    d.PROFIL_METNI = d.profil_hazirla({a["id"] for a, _, _ in vakalar})
    print("profil hazir,", len(vakalar), "vaka", flush=True)
    sonuclar, bas = [], time.time()
    for a, onceki, gelen in vakalar:
        if time.time() - bas > AZAMI_SN:
            print("sure doldu", flush=True)
            break
        adaylar = uret(a, onceki, gelen)
        for v in adaylar.values():
            v.update(d.metrik(v["secenekler"], a["metin"]))
        sonuclar.append({"gelen": [m["metin"] for m in gelen], "gercek": a["metin"], "adaylar": adaylar})
        CIKTI.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=1))
        print(len(sonuclar), "vaka tamam", round((time.time() - bas) / 60), "dk", flush=True)


main()
