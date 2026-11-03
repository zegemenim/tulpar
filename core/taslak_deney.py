"""Gece deneyi: sahibin dilini yakalamak için 8 farklı taslak stratejisini aynı gerçek vakalarda dener.
Her vakada sahibin gerçek cevabı gizlenir; her strateji taslak yazar; sonuçlar veri/eval/deney.json'a vaka vaka yazılır.
Vakalar sırayla işlenir (yarım kalsa bile bitmiş vakalarda tüm stratejiler vardır). Kullanım: taslak_deney.py [vaka] [azami_saat]
Hakem: taslak_rapor.py (kör: strateji adları karıştırılır) + otomatik benzerlik."""
import json
import math
import pathlib
import random
import re
import sys
import time

import benzer
import db
import llm
import sahip
import taslak

N = int(sys.argv[1]) if len(sys.argv) > 1 else 14
AZAMI_SN = float(sys.argv[2]) * 3600 if len(sys.argv) > 2 else 7.5 * 3600  # (içe aktarılınca da okunur; ikinci tur kendi argümanlarını kullanır)
KLASOR = pathlib.Path.home() / "tulpar/veri/eval"
CIKTI = KLASOR / "deney.json"
PROFIL = KLASOR / "uslup-profil.txt"
SLOT = 2
BASLA = time.time()


def vaka_sec():
    return vaka_sec_n(N)


def vaka_sec_n(n_):
    r = random.Random(7)
    adaylar = db.oku("""SELECT m.id, m.sohbet_id, m.metin, m.zaman FROM mesajlar m WHERE m.benden=1 AND length(m.metin) BETWEEN 3 AND 150
                        AND m.zaman < strftime('%s','now') - 86400 AND m.grup=0 AND m.metin NOT LIKE '[%' AND m.metin NOT LIKE '%http%'""")
    r.shuffle(adaylar)
    sonuc, gorulen = [], set()
    for a in adaylar:
        if a["sohbet_id"] in gorulen:
            continue
        onceki = db.oku("SELECT * FROM mesajlar WHERE sohbet_id=? AND zaman<? ORDER BY zaman DESC LIMIT 25", a["sohbet_id"], a["zaman"])[::-1]
        gelen = []
        for m in reversed(onceki):
            if m["benden"]:
                break
            gelen.insert(0, m)
        if gelen and len(onceki) >= 15 and sum(m["benden"] for m in onceki) >= 4:
            sonuc.append((a, onceki, gelen))
            gorulen.add(a["sohbet_id"])
        if len(sonuc) >= n_:
            break
    return sonuc


def sor(sistem, kullanici, json_cevap=True, gecmis=None, sicaklik=None):
    return llm.sor("hizli", sistem, kullanici, json_cevap=json_cevap, gecmis=gecmis, slot=SLOT, sicaklik=sicaklik)


def secenekler_json(c):
    try:
        return [" / ".join(m["metin"] for m in sc["mesajlar"]) for sc in c["secenekler"] if sc.get("mesajlar")]
    except Exception:  # noqa: BLE001
        return []


def duz(metin):
    """Düz metin cevabı mesaj satırlarına çevirir."""
    satirlar = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+|^[\"']+|[\"']+$", "", s).strip() for s in str(metin).strip().split("\n")]
    return " / ".join(s for s in satirlar if s)[:300]


def profil_hazirla(hariç_idler):
    if PROFIL.exists():
        return PROFIL.read_text()
    r = random.Random(11)
    ms = [m["metin"] for m in db.oku("SELECT id, metin FROM mesajlar WHERE benden=1 AND length(metin) BETWEEN 3 AND 140 AND metin NOT LIKE '[%' "
                                     "AND metin NOT LIKE '%http%'") if m["id"] not in hariç_idler]
    r.shuffle(ms)
    ornek = "\n".join("- " + m for m in ms[:150])
    p = sor("Bir kişinin WhatsApp yazış üslubunu analiz eden bir dilbilimcisin.",
            f"Aşağıdaki mesajları {sahip.AD} yazdı. Üslubunu en fazla 12 madde halinde tarif et: kelime seçimi ve sık kalıplar (örnekleriyle), "
            "kısaltmalar/argo, harf büyüklüğü, noktalama, emoji kullanımı, mesaj uzunluğu, esprili/ciddi ton, yazım hataları. "
            "Sonra 'KAÇINILACAKLAR' başlığıyla onun asla yazmayacağı şeyleri say. Sadece düz metin.\n\n" + ornek, json_cevap=False)
    PROFIL.write_text(p)
    return p


KISA_SISTEM = sahip.doldur(
    "Sen {SAHIP_TAM}'sın ve WhatsApp'ta cevap yazıyorsun. Aşağıdaki örnek konuşmalardaki gibi, KENDİ üslubunla, kısa ve doğal yaz. "
    "Sadece göndereceğin mesajı yaz (birden çok kısa mesaj gerekiyorsa her biri ayrı satırda). Bilmediğin kişisel bir kararı (gelirim, "
    "müsaitim, yaptım) UYDURMA: bu durumda en olası kararı kısa ve nötr yaz. Konuşmada olmayan saat, isim, plan uydurma."
)


def kart_satiri(sid):
    k = db.kisi(sid) or {}
    return f"Kişi: ilişki={k.get('iliski') or 'bilinmiyor'}, hitap={k.get('hitap')}, sen/siz={k.get('sen_siz')}"


def cift_gecmisi(ciftler):
    """Benzer durumları sohbet biçiminde (gelen -> sahibin cevabı) few-shot olarak verir; en benzer EN SONDA."""
    g = []
    for gelen, cevap in reversed(ciftler):
        g += [("user", gelen[:200]), ("assistant", cevap)]
    return g


def uret_vaka(a, onceki, gelen):
    sid, t = a["sohbet_id"], a["zaman"]
    ad = gelen[0].get("sohbet_adi") or "kişi"
    gelen_metin = [m["metin"] for m in gelen]
    gelen_txt = "\n".join(f"[{m['id']}] {m.get('gonderen_adi') or ad}: {m['metin']}" for m in gelen)
    konusma = "\n".join(f"[{m['id']}] {sahip.AD if m['benden'] else m.get('gonderen_adi') or ad}: {m['metin']}" for m in onceki)
    kisa_konusma = "\n".join(f"{sahip.AD if m['benden'] else ad}: {m['metin']}" for m in onceki[-8:])
    son = (f"\n\nSon konuşma (bağlam):\n{konusma}\n\nCEVAPLANACAK MESAJ(LAR) — SADECE bunlara cevap ver:\n{gelen_txt}\n"
           f"Bugün: {time.strftime('%Y-%m-%d %A %H:%M', time.localtime(t))}")
    kendi = [m["metin"] for m in db.oku("SELECT metin FROM mesajlar WHERE benden=1 AND sohbet_id=? AND zaman<? ORDER BY zaman DESC LIMIT 40", sid, t)
             if len(m["metin"]) < 300]
    c12 = benzer.benzer_cevaplar(sid, gelen_metin, n=12, once=t)
    c8, c20 = c12[:8], benzer.benzer_cevaplar(sid, gelen_metin, n=20, once=t)
    uslup = benzer.uslup_ozeti(sid)
    ciftler_txt = lambda cs: "\n\nBENZER GEÇMİŞ DURUMLAR (karşı taraf ne yazdı -> sahibi nasıl cevap verdi; SADECE ÜSLUBU öğren, karar sahibine aittir):\n" + "\n".join(f"- \"{g[:150]}\" -> \"{c}\"" for g, c in cs) if cs else ""  # noqa: E731
    temel = lambda n: f"{sahip.AD} adlı sahibin örnek mesajları:\n" + "\n".join(f"- {o}" for o in kendi[:n]) + "\n"  # noqa: E731
    sis = taslak.sistem()
    sonuc = {}

    def dene(ad, f):
        t0 = time.time()
        try:
            s = f()
        except Exception as e:  # noqa: BLE001
            s = [f"(hata: {type(e).__name__}: {str(e)[:60]})"]
        sonuc[ad] = {"secenekler": s, "sn": round(time.time() - t0)}

    dene("A0_temel", lambda: secenekler_json(sor(sis, temel(15) + son)))
    dene("A1_benzer", lambda: secenekler_json(sor(sis, temel(15) + ciftler_txt(c8) + "\n" + uslup + son)))
    dene("A2_sohbet_fewshot", lambda: [duz(sor(KISA_SISTEM + "\n" + kart_satiri(sid) + "\nKonuşmanın son hali:\n" + kisa_konusma,
                                               "\n".join(gelen_metin), json_cevap=False, gecmis=cift_gecmisi(c12)))])

    def a3():
        adaylar = [duz(sor(KISA_SISTEM + "\n" + kart_satiri(sid) + "\nKonuşmanın son hali:\n" + kisa_konusma, "\n".join(gelen_metin),
                           json_cevap=False, gecmis=cift_gecmisi(c12), sicaklik=0.9)) for _ in range(4)]
        tekil = list(dict.fromkeys(a for a in adaylar if a))
        gecmis_cevaplar = [benzer._ngram(c) for _, c in c20] or [benzer._ngram(k) for k in kendi[:20]]
        # seçici: sahibin benzer durumlardaki gerçek cevaplarına en yakın aday öne
        tekil.sort(key=lambda x: -max(benzer._kosinus(benzer._ngram(x), g) for g in gecmis_cevaplar))
        return tekil[:3]
    dene("A3_coklu_sirala", a3)
    dene("A4_profil", lambda: secenekler_json(sor(sis, "SAHİBİNİN ÜSLUP KILAVUZU (buna uy):\n" + PROFIL_METNI + "\n\n" + temel(8) + ciftler_txt(c8) + son)))
    dene("A5_cok_ornek", lambda: secenekler_json(sor(sis, temel(40) + ciftler_txt(c20) + "\n" + uslup + son)))

    def a6():
        yon = sor("Sahibin vereceği cevabın olası YÖNLERİNİ çıkar. SADECE JSON: {\"yonler\": [\"3-6 kelimelik yön\", ...]} (en fazla 3, birbirinden farklı; "
                  "karar gerekmiyorsa tek yön).", f"Kişi: {ad}\nSon konuşma:\n{kisa_konusma}\nCevaplanacak: {' / '.join(gelen_metin)}")
        yonler = [y for y in (yon.get("yonler") or []) if isinstance(y, str)][:3] or ["uygun cevap"]
        cik = []
        for y in yonler:
            cik.append(duz(sor(KISA_SISTEM + "\n" + kart_satiri(sid) + f"\nBu cevap şu yönde olsun: {y}\nKonuşmanın son hali:\n" + kisa_konusma,
                               "\n".join(gelen_metin), json_cevap=False, gecmis=cift_gecmisi(c12))))
        return cik
    dene("A6_iki_asama", a6)

    def a7():
        ilk = (sonuc["A0_temel"]["secenekler"] or [""])[0]
        yeniden = sor("Verilen taslak cevabı, örnek mesajları yazan kişinin tarzıyla yeniden yaz. Anlamı, kararı ve bilgiyi DEĞİŞTİRME; sadece kelime seçimi, "
                      "uzunluk, harf ve noktalama alışkanlıklarını örneklere uydur. Sadece yeniden yazılmış mesajı yaz.",
                      f"ÖRNEK MESAJLAR:\n" + "\n".join(f"- {k}" for k in kendi[:15] + [c for _, c in c8[:6]]) + f"\n\nTASLAK: {ilk}", json_cevap=False)
        return [duz(yeniden)]
    dene("A7_yeniden_yaz", a7)
    return sonuc


def metrik(secenekler, gercek):
    if not secenekler:
        return {"top1": 0.0, "en_iyi": 0.0, "uzunluk_farki": 9.0}
    ng = benzer._ngram(gercek)
    p = [benzer._kosinus(benzer._ngram(s), ng) for s in secenekler]
    uz = abs(math.log((len(secenekler[0].split()) + 1) / (len(gercek.split()) + 1)))
    return {"top1": round(p[0], 3), "en_iyi": round(max(p), 3), "uzunluk_farki": round(uz, 2)}


def main():
    global PROFIL_METNI
    vakalar = vaka_sec()
    PROFIL_METNI = profil_hazirla({a["id"] for a, _, _ in vakalar})
    print("profil hazir,", len(vakalar), "vaka", flush=True)
    sonuclar = []
    for a, onceki, gelen in vakalar:
        if time.time() - BASLA > AZAMI_SN:
            print("sure doldu", flush=True)
            break
        adaylar = uret_vaka(a, onceki, gelen)
        for ad, v in adaylar.items():
            v.update(metrik(v["secenekler"], a["metin"]))
        sonuclar.append({"gelen": [m["metin"] for m in gelen], "gercek": a["metin"], "adaylar": adaylar})
        CIKTI.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=1))
        print(len(sonuclar), "vaka tamam", round((time.time() - BASLA) / 60), "dk", flush=True)


PROFIL_METNI = ""
if __name__ == "__main__":
    main()
