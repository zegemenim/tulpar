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

KOD_KELIME = re.compile(r"doğrulama|dogrulama|onay kodu|tek kullanımlık|tek kullanimlik|şifre|sifre|parola|otp|verification|one[- ]time|security code|\bcode\b|\bkod\b|\bkodu\b|\bpin\b|3d secure|3dsecure", re.I)
KOD_SAYI = re.compile(r"(?<![\d])(?<![.,]\d)\d{4,8}(?!\d)(?![.,]\d)")  # 1.250,00 gibi tutarlar kod sayılmaz


def kod_iceriyor(metin):
    """Doğrulama kodu gibi duruyorsa True: anahtar sözcük + 4-8 haneli sayı birlikte."""
    return bool(KOD_KELIME.search(metin) and KOD_SAYI.search(metin))


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


def liste(n=100, tur=None, paket=None):
    with _kilit:
        g = _yukle()
    g = [x for x in g if (not tur or x["tur"] == tur) and (not paket or x["paket"] == paket)]
    return list(reversed(g))[:n]
