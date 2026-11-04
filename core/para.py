"""Para hareketleri: banka SMS'i/bildiriminden tutar ve yön çıkarır, veri/para.jsonl'de kalıcı tutar (bildirimler 30 günde silinir).
Model kullanmaz; yalnızca kesin "işlem" diline uyan metinler sayılır, kampanya ve bakiye bilgisi sayılmaz. Yatırım tavsiyesi vermez."""
import collections
import datetime
import json
import pathlib
import re
import threading
import zoneinfo

DOSYA = pathlib.Path.home() / "tulpar/veri/para.jsonl"
TZ = zoneinfo.ZoneInfo("Europe/Istanbul")
_kilit = threading.Lock()

TUTAR = re.compile(r"(?<![\d.,])(\d{1,3}(?:[.,]\d{3})+(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:TL|TRY|₺)(?![a-zçğıöşü])", re.I)
ONCE_YOK = re.compile(r"(bakiye\w*|limit\w*|borc\w*|borç\w*|asgari|kalan\w*|toplam\w*)\W*(?:\w+\W+)?$", re.I)
REKLAM = re.compile(r"kampanya|fırsat|firsat|kazan|hediye|indirim|taksit imkan|kredi teklif|başvur|basvur|ödül|puan|chip|\bRET\b|iptal edil|reddedil|başarısız|basarisiz", re.I)
GELIR = re.compile(r"hesabınıza .*(yatırıl|gönderil|geldi)|yatırıldı|maaş|maas|gelen (havale|eft|fast)|tarafınıza|iade edil|iadeniz|alacak", re.I)
GIDER = re.compile(r"harcama|alışveriş|alisveris|ödeme yapıl|odeme yapil|ödemeniz|çekildi|cekildi|çekim|gönderildi|gonderildi|hesabınızdan|kartınızdan|otomatik ödeme|\bPOS\b|tahsil edil", re.I)


def _sayi(s):
    """1.250,00 / 1,250.00 / 1250.5 / 1.250 -> float."""
    ayrac = max(s.rfind("."), s.rfind(","))
    if ayrac >= 0 and len(s) - ayrac - 1 <= 2:
        return float(re.sub(r"[.,]", "", s[:ayrac]) + "." + s[ayrac + 1:])
    return float(re.sub(r"[.,]", "", s))


def cikar(metin):
    """{'yon': 'gider'|'gelir', 'tutar': float} ya da None. Emin değilse None: yanlış kayıt, eksik kayıttan kötüdür."""
    if not metin or REKLAM.search(metin):
        return None
    yon = "gelir" if GELIR.search(metin) else "gider" if GIDER.search(metin) else None
    if not yon:
        return None
    for m in TUTAR.finditer(metin):
        if not ONCE_YOK.search(metin[:m.start()]):
            return {"yon": yon, "tutar": _sayi(m.group(1))}
    return None


def isle(paket, baslik, metin, zaman):
    k = cikar(f"{baslik} {metin}".strip())
    if not k:
        return None
    with _kilit:
        DOSYA.parent.mkdir(parents=True, exist_ok=True)
        with open(DOSYA, "a", encoding="utf-8") as f:
            f.write(json.dumps({**k, "paket": paket, "baslik": baslik, "metin": metin[:200], "zaman": zaman}, ensure_ascii=False) + "\n")
        DOSYA.chmod(0o600)
    return k


def _yukle():
    try:
        return [json.loads(s) for s in DOSYA.read_text(encoding="utf-8").splitlines() if s.strip()]
    except (FileNotFoundError, ValueError):
        return []


def aylik(ay=None):
    """ay 'YYYY-AA' (boşsa bu ay): {ay, gider, gelir, net, adet, kaynaklar, son}."""
    ay = ay or datetime.datetime.now(TZ).strftime("%Y-%m")
    h = [x for x in _yukle() if datetime.datetime.fromtimestamp(x["zaman"], TZ).strftime("%Y-%m") == ay]
    gider = sum(x["tutar"] for x in h if x["yon"] == "gider")
    gelir = sum(x["tutar"] for x in h if x["yon"] == "gelir")
    kaynak = collections.Counter()
    for x in h:
        if x["yon"] == "gider":
            kaynak[x["baslik"] or x["paket"]] += x["tutar"]
    return {"ay": ay, "gider": round(gider, 2), "gelir": round(gelir, 2), "net": round(gelir - gider, 2), "adet": len(h),
            "kaynaklar": [{"ad": a, "tutar": round(t, 2)} for a, t in kaynak.most_common(10)], "son": h[-20:][::-1]}
