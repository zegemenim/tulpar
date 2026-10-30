"""Fine-tune verisi: sahibin her cevabı için "önceki konuşma -> sahibin yazdığı" örnekleri çıkarır.

- Hariç tutulan sohbetler hiç alınmaz; medya indirilmez ([fotoğraf] gibi yer tutucular bağlamda kalır).
- Art arda yazılan mesajlar (5 dk içinde) tek cevap sayılır: model birden çok kısa mesaj atmayı da öğrenir.
- Bağlam: cevaptan önceki en fazla 15 mesaj (son 12 saat). Kimseye cevap olmayan mesajlar alınmaz.
- Maskeleme: şifre/kod ifadeleri, kredi kartı (Luhn), CVV, telefon, e-posta, link, IBAN, uzun sayılar; kişi adları sohbet içinde tutarlı takma adlara çevrilir.
- Çıktı: ~/tulpar/veri/egitim/{egitim,dogrulama}.jsonl (chat formatı) + istatistik.
Kullanım: python3 egitim_verisi.py
"""
import json
import pathlib
import random
import re
import sqlite3
from collections import Counter

import sahip

VERI = pathlib.Path.home() / "tulpar/veri"
CIKTI = VERI / "egitim"
BAGLAM = 15
BIRLESTIR_SN = 300
BAGLAM_PENCERE_SN = 12 * 3600
SADE_CEVAP_ORANI = 0.15  # "tmm", "ok", tek emoji gibi cevapların sadece bu kadarı tutulur
SADE = re.compile(r"^\W*(tmm|tamam|ok|okey|olur|evet|hayır|yok|he|hı|aynen|eyv|eyvallah|sağol|tşk|tesekkurler|teşekkürler)?\W*$", re.I)

def _kart(m):
    """13-19 haneli sayı Luhn kontrolünden geçiyorsa kredi kartı say."""
    rakam = [int(c) for c in re.sub(r"\D", "", m.group(0))]
    toplam = sum((d * 2 - 9 if d > 4 else d * 2) if i % 2 == len(rakam) % 2 else d for i, d in enumerate(rakam))
    return ("[kart] " if m.group(0).endswith(" ") else "[kart]") if 13 <= len(rakam) <= 19 and toplam % 10 == 0 else m.group(0)


MASKELER = [
    # "şifre: x", "parola x", "pw: x", "kod 123456" gibi: anahtar kelimeden sonraki ifade
    (re.compile(r"(?i)\b(şifre(?:m|si|n)?|sifre(?:m|si|n)?|parola(?:m|sı)?|password|pass|pw|pin|kod(?:u|um)?|code|otp)\b(\s*[:=]?\s*)\S+"), r"\1\2[gizli]"),
    (re.compile(r"\bTR\s?\d{2}(?:\s?\d{4}){5}\s?\d{0,2}\b", re.I), "[iban]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), _kart),
    (re.compile(r"(?i)\b(cvv|cvc|skt|son kullanma)\b\s*[:=]?\s*[\d/]+"), r"\1 [gizli]"),
    (re.compile(r"https?://\S+|www\.\S+"), "[link]"),
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b"), "[eposta]"),
    (re.compile(r"\b\d{6,}\b"), "[sayı]"),
    (re.compile(r"(?:\+?90[\s-]?)?\(?0?5\d{2}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}"), "[telefon]"),
]


def maskele(metin, adlar):
    for desen, yerine in MASKELER:
        metin = desen.sub(yerine, metin)
    for gercek, takma in adlar.items():
        metin = re.sub(rf"\b{re.escape(gercek)}\b", takma, metin, flags=re.I)
    return metin


def haric():
    try:
        return set(json.loads((VERI / "haric.json").read_text()).get("sohbetler", []))
    except FileNotFoundError:
        return set()


def ilk_ad(ad):
    ad = (ad or "").strip()
    return ad.split()[0] if ad and not ad.startswith("+") and not ad[0].isdigit() else None


def sohbet_ornekleri(mesajlar, kart, grup):
    """Tek sohbetin mesajları (zaman sıralı) -> örnekler."""
    takma, adlar = {}, {}
    for a in sahip.ADLAR + [sahip.AD]:
        adlar[a] = "[ben]"
    harf = iter("ABCDEFGHIJKLMNOPRSTUVYZ" * 4)

    def kim(m):
        if m["benden"]:
            return "Ben"
        anahtar = m["gonderen_adi"] or "?"
        if anahtar not in takma:
            takma[anahtar] = f"Kişi {next(harf)}" if grup else "Karşı taraf"
            if ilk_ad(anahtar) and len(ilk_ad(anahtar)) > 2:
                adlar[ilk_ad(anahtar)] = takma[anahtar]
        return takma[anahtar]

    ornekler, i = [], 0
    while i < len(mesajlar):
        m = mesajlar[i]
        if not m["benden"]:
            kim(m)
            i += 1
            continue
        j = i  # art arda kendi mesajları
        while j + 1 < len(mesajlar) and mesajlar[j + 1]["benden"] and mesajlar[j + 1]["zaman"] - mesajlar[j]["zaman"] < BIRLESTIR_SN:
            j += 1
        cevap = [x["metin"] for x in mesajlar[i:j + 1] if not x["metin"].startswith("[")]
        onceki = [x for x in mesajlar[max(0, i - BAGLAM):i] if m["zaman"] - x["zaman"] < BAGLAM_PENCERE_SN]
        if cevap and onceki and not onceki[-1]["benden"]:
            ornekler.append((onceki, cevap))
        i = j + 1

    sonuc = []
    for onceki, cevap in ornekler:
        baglam = "\n".join(f"{kim(x)}: {maskele(x['metin'][:400].replace('(sahibin mesajına cevap) ', '↪ '), adlar)}" for x in onceki)
        sonuc.append({"baglam": baglam, "cevap": [maskele(c, adlar) for c in cevap]})
    return sonuc


def sistem_istemi(kart, grup):
    iliski = (kart or {}).get("iliski") or "bilinmiyor"
    hitap = (kart or {}).get("hitap")
    return ("Sen [ben] olarak WhatsApp'ta yazıyorsun; onun gerçek üslubuyla, kısa ve doğal cevap ver. "
            f"Sohbet: {'grup' if grup else 'birebir'}. Karşı tarafla ilişki: {iliski}"
            + (f", hitap: {hitap}" if hitap else "") + ". Birden çok mesaj atacaksan her birini ayrı satıra yaz.")


def main():
    random.seed(42)
    b = sqlite3.connect(VERI / "tulpar.db", timeout=120)
    b.row_factory = sqlite3.Row
    disari = haric()
    kartlar = {r["id"]: dict(r) for r in b.execute("SELECT * FROM kisiler")}
    sohbetler = [r[0] for r in b.execute("SELECT DISTINCT sohbet_id FROM mesajlar")]
    tum, istat = [], Counter()
    for sid in sohbetler:
        if sid in disari:
            istat["haric_sohbet"] += 1
            continue
        mesajlar = [dict(r) for r in b.execute(
            "SELECT benden, gonderen_adi, metin, zaman, grup FROM mesajlar WHERE sohbet_id=? AND metin!='' ORDER BY zaman", (sid,))]
        if not mesajlar:
            continue
        grup = bool(mesajlar[0]["grup"])
        for o in sohbet_ornekleri(mesajlar, kartlar.get(sid), grup):
            sade = all(SADE.match(c) for c in o["cevap"])
            if sade and random.random() > SADE_CEVAP_ORANI:
                istat["atilan_sade"] += 1
                continue
            istat["grup" if grup else "birebir"] += 1
            tum.append({"messages": [
                {"role": "system", "content": sistem_istemi(kartlar.get(sid), grup)},
                {"role": "user", "content": o["baglam"]},
                {"role": "assistant", "content": "\n".join(o["cevap"])},
            ]})
    random.shuffle(tum)
    n_dog = max(1, len(tum) // 20)
    CIKTI.mkdir(parents=True, exist_ok=True)
    for ad, parca in (("dogrulama", tum[:n_dog]), ("egitim", tum[n_dog:])):
        with open(CIKTI / f"{ad}.jsonl", "w") as f:
            for x in parca:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    (CIKTI / "istatistik.json").write_text(json.dumps({"ornek": len(tum), **istat}, ensure_ascii=False, indent=1))
    print(f"{len(tum)} örnek (eğitim {len(tum) - n_dog}, doğrulama {n_dog}); {dict(istat)}")


if __name__ == "__main__":
    main()
