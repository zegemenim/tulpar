"""Telefon bildirimleri ve SMS'ler: uygulamadan gelir, 30 gün saklanır (veri/bildirim.jsonl, 0600).
Doğrulama kodu / şifre içerenler HİÇ kaydedilmez (OTP saklanmaz). Aylık para analizi ve özetler buradan beslenir."""
import json
import pathlib
import re
import threading
import time

DOSYA = pathlib.Path.home() / "tulpar/veri/bildirim.jsonl"
SAKLAMA_SN = 30 * 86400
SINIR = 600  # tek bildirimin saklanan en uzun metni
TEKRAR_SN = 90  # aynı bildirim bu süre içinde ikinci kez gelirse yok sayılır
_kilit = threading.Lock()
_son = {}  # (paket, baslik, metin) -> zaman

KOD_KELIME = re.compile(r"doğrulama|dogrulama|onay kodu|tek kullanımlık|tek kullanimlik|şifre|sifre|parola|otp|verification|one[- ]time|security code|\bcode\b|\bkod\w*|\bpin\b|3d secure|3dsecure", re.I)
KOD_SAYI = re.compile(r"(?<![\d])(?<![.,]\d)\d{4,8}(?!\d)(?![.,]\d)")  # 1.250,00 gibi tutarlar kod sayılmaz


def kod_iceriyor(metin):
    """Doğrulama kodu gibi duruyorsa True: anahtar sözcük + 4-8 haneli sayı birlikte."""
    return bool(KOD_KELIME.search(metin) and (KOD_SAYI.search(metin) or kod_cikar(metin)))


ADAY = re.compile(r"(?<![\w.,/-])([A-Za-z]{1,3}-?\d{4,8}|\d{3}[- ]\d{3}|\d{4,8}|(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{6,8})(?![\w]|[.,]\d)")
ONCE_KOD = re.compile(r"kod|şifre|sifre|code|otp|parola|\bpin\b|doğrulama|dogrulama|verification", re.I)
ONCE_REF = re.compile(r"ref|işlem no|islem no|sipariş|siparis|sıra no|\bno\b|\bid\b|tutar|bakiye|limit|tel|numara", re.I)
SONRA_REF = re.compile(r"^\s*(ref|numaral|no\b|nolu|sipariş|siparis|tl\b|₺|try|eur|usd|\$|%|adet|taksit)", re.I)


def kod_cikar(metin):
    """Mesajdaki gerçek doğrulama kodunu seçer (yoksa None): kod/şifre sözcüğünden sonra gelen, tutar/referans/tarih olmayan en iyi aday."""
    if not KOD_KELIME.search(metin):
        return None
    en = (0, None)
    for m in ADAY.finditer(metin):
        aday, bas, son = m.group(1), m.start(), m.end()
        onceki, sonraki = metin[max(0, bas - 30):bas], metin[son:son + 14]
        puan = 0
        if ONCE_KOD.search(onceki):
            puan += 5
        elif ONCE_KOD.search(metin[son:son + 25]):
            puan += 2  # "123456 kodunu girin" biçimi
        saf = re.sub(r"\D", "", aday)
        puan += 2 if len(saf) == 6 else 1
        if ONCE_REF.search(onceki[-15:]) and not ONCE_KOD.search(onceki[-15:]):
            puan -= 6
        if SONRA_REF.search(sonraki):
            puan -= 6
        if aday[0].isalpha() and "-" not in aday and aday.isalnum() and not re.search(r"\d", aday[:1]) and len(saf) < len(aday) and puan < 7:
            puan -= 3  # B1245 gibi harf önekli numara: kodun kendisi nadiren böyle yazılır
        if len(saf) == 4 and 1990 <= int(saf) <= 2100 and not ONCE_KOD.search(onceki):
            puan -= 3
        if puan > en[0]:
            en = (puan, aday)
    return re.sub(r"[ -]", "", en[1]) if en[1] and en[0] >= 3 else None


def _yukle():
    try:
        satirlar = [json.loads(s) for s in DOSYA.read_text().splitlines() if s.strip()]
    except (FileNotFoundError, ValueError):
        return []
    return [s for s in satirlar if time.time() - s["zaman"] < SAKLAMA_SN]


def yaz(paket, baslik, metin, tur="bildirim", zaman=None):
    """Kaydeder; süzülürse (OTP, tekrar, boş) False döner."""
    baslik, metin = (baslik or "").strip()[:200], (metin or "").strip()[:SINIR]
    if not (baslik or metin) or kod_iceriyor(f"{baslik} {metin}"):
        return False
    simdi = time.time()
    anahtar = (paket, baslik, metin)
    with _kilit:
        if simdi - _son.get(anahtar, 0) < TEKRAR_SN:
            return False
        _son[anahtar] = simdi
        for k in [k for k, z in _son.items() if simdi - z > TEKRAR_SN]:
            del _son[k]
        g = _yukle() + [{"paket": paket, "baslik": baslik, "metin": metin, "tur": tur, "zaman": zaman or simdi}]
        DOSYA.parent.mkdir(parents=True, exist_ok=True)
        DOSYA.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in g) + "\n")
        DOSYA.chmod(0o600)
    return True


ONEMLI = re.compile(r"harcama|ödeme|odeme|fatura|borç|borc|kargo|teslim|randevu|toplantı|toplanti|hesab[ıi]n|havale|eft|iade|güvenlik|guvenlik|son gün|son gun|kart|bakiye|ödenmedi|gecikme|şüpheli|supheli|giriş yapıldı|login", re.I)


def onemli(x):
    """SMS'ler ve para/kargo/randevu/güvenlik gibi anlamlı bildirimler; reklam ve uygulama gürültüsü değil."""
    return x["tur"] == "sms" or bool(ONEMLI.search(f"{x['baslik']} {x['metin']}"))


def liste(n=100, tur=None, paket=None, sadece_onemli=False):
    with _kilit:
        g = _yukle()
    g = [x for x in g if (not tur or x["tur"] == tur) and (not paket or x["paket"] == paket) and (not sadece_onemli or onemli(x))]
    return list(reversed(g))[:n]
