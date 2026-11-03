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
    simdi = time.time()
    return [s for s in satirlar if simdi - s["zaman"] < SAKLAMA_SN and s.get("sona_erer", simdi + 1) > simdi]


def _baslangic():
    g = _yukle()
    if g:
        _son.update(g[-1])


def uygun(metin):
    t = (metin or "").strip()
    if not t or len(t) > SINIR:
        return False
    return not (" " not in t and "\n" not in t and _sifre_gibi(t))


KOD_OMRU_SN = 600


def yaz(metin, kaynak, kod=False):
    """kod=True: doğrulama kodu; şifre denetimine takılmaz ama geçmişten 10 dk sonra silinir."""
    if kod and not (metin or "").strip():
        return False
    if not kod and not uygun(metin):
        return False
    with _kilit:
        if metin == _son["metin"]:
            return True
        _son.update(metin=metin, kaynak=kaynak, zaman=time.time())
        _son.pop("sona_erer", None)
        if kod:
            _son["sona_erer"] = time.time() + KOD_OMRU_SN
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
