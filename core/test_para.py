"""Para çıkarma: işlem metinleri sayılır, kampanya/bakiye sayılmaz. Çalıştır: python test_para.py"""
import pathlib
import tempfile
import time

import para

para.DOSYA = pathlib.Path(tempfile.mkdtemp()) / "p.jsonl"

VAKA = [("Kartınızdan 1.250,00 TL harcama yapıldı. Kullanılabilir limitiniz 8.000,00 TL", ("gider", 1250.0)),
        ("Hesabınıza 15.000,50 TL maaş yatırıldı", ("gelir", 15000.5)),
        ("MIGROS 349,90 TL alışveriş", ("gider", 349.9)),
        ("Bakiyeniz 2.000 TL. Kartınızdan 100 TL çekildi", ("gider", 100.0)),
        ("Ahmet'ten gelen havale 500₺", ("gelir", 500.0)),
        ("1,250.75 TRY odeme yapildi", ("gider", 1250.75)),
        ("Bu hafta 500 TL harcama yapana 50 TL indirim fırsatı", None),
        ("Hesap bakiyeniz 3.000,00 TL", None),
        ("Yarın 200 TL getir", None),
        ("Kartınızdan 300 TL işlem başarısız oldu", None)]
for metin, beklenen in VAKA:
    k = para.cikar(metin)
    assert (k and (k["yon"], k["tutar"])) == beklenen or (k is None and beklenen is None), (metin, k)

simdi = time.time()
para.isle("banka", "Banka", "Kartınızdan 100 TL harcama yapıldı", simdi)
para.isle("banka", "Banka", "Hesabınıza 400 TL yatırıldı", simdi)
a = para.aylik()
assert (a["gider"], a["gelir"], a["net"], a["adet"]) == (100, 400, 300, 2), a
print("tamam")
