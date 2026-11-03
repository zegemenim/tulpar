"""Cihazlar arası tek pano: en son kopyalanan metin tüm cihazlara eşitlenir; geçmiş 7 gün saklanır (veri/pano.jsonl).
Şifre gibi duran tek parçalı metinler ve çok uzun metinler hiç kaydedilmez/eşitlenmez."""
import json
import pathlib
import threading
import time

from egitim_verisi import _sifre_gibi

DOSYA = pathlib.Path.home() / "tulpar/veri/pano.jsonl"
SAKLAMA_SN = 7 * 86400
SINIR = 20000
_kilit = threading.Lock()
_son = {"metin": "", "kaynak": "", "zaman": 0.0}


def _yukle():
    try:
        satirlar = [json.loads(s) for s in DOSYA.read_text().splitlines() if s.strip()]
    except (FileNotFoundError, ValueError):
        return []
    return [s for s in satirlar if time.time() - s["zaman"] < SAKLAMA_SN]


def _baslangic():
    g = _yukle()
    if g:
        _son.update(g[-1])


def uygun(metin):
    t = (metin or "").strip()
    if not t or len(t) > SINIR:
        return False
    return not (" " not in t and "\n" not in t and _sifre_gibi(t))


def yaz(metin, kaynak):
    if not uygun(metin):
        return False
    with _kilit:
        if metin == _son["metin"]:
            return True
        _son.update(metin=metin, kaynak=kaynak, zaman=time.time())
        g = _yukle() + [dict(_son)]  # 7 günden eskiler her yazışta ayıklanır
        DOSYA.parent.mkdir(parents=True, exist_ok=True)
        DOSYA.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in g) + "\n")
        DOSYA.chmod(0o600)
    return True


def oku():
    with _kilit:
        return dict(_son)


def gecmis(n=50):
    with _kilit:
        return list(reversed(_yukle()))[:n]


_baslangic()
