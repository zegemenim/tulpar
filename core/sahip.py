"""Asistanın sahibine dair kişisel bilgiler. Repoda değil, sunucuda ~/tulpar/veri/sahip.json içinde durur.
Örnek: sunucu/sahip.json.ornek. İstem ve metinlerdeki {SAHIP} / {SAHIP_TAM} yer tutucuları buradan doldurulur."""
import json
import pathlib

YOL = pathlib.Path.home() / "tulpar/veri/sahip.json"
_VARSAYILAN = {"ad": "Kullanıcı", "tam_ad": "Kullanıcı", "adlar": ["kullanici"]}

try:
    _b = {**_VARSAYILAN, **json.loads(YOL.read_text())}
except FileNotFoundError:
    _b = _VARSAYILAN

AD = _b["ad"]                                 # konuşmada geçen kısa ad, örn. "Ali"
TAM_AD = _b["tam_ad"]                         # örn. "Ali Yılmaz"
ADLAR = [a.lower() for a in _b["adlar"]]      # mesajda geçince ona hitap sayılan adlar/kısaltmalar (ASCII, küçük harf)


def doldur(metin: str) -> str:
    return metin.replace("{SAHIP_TAM}", TAM_AD).replace("{SAHIP}", AD)
