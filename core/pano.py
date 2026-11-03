"""Cihazlar arası pano eşitleme: en son kopyalanan metin bellekte tutulur (diske yazılmaz, geçmiş yok).
Şifre gibi duran tek parçalı metinler ve çok uzun metinler eşitlenmez."""
import threading
import time

from egitim_verisi import _sifre_gibi

_kilit = threading.Lock()
_son = {"metin": "", "kaynak": "", "zaman": 0.0}
SINIR = 20000


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
    return True


def oku():
    with _kilit:
        return dict(_son)
