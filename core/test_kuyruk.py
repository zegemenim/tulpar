"""Kuyruk testi (HP'de, gerçek modellerle): büyük işler sürerken acil iş gelirse öne geçmeli."""
import time
from kuyruk import Kuyruk, Is

k = Kuyruk()
t0 = time.time()
uzun = [k.ekle(Is("taslak", "Türkçe yaz.", f"Kulüp için {n}. etkinlik hakkında 150 kelimelik duyuru yaz.", json_cevap=False))
        for n in (1, 2)]
time.sleep(25)
ta = time.time()
acil = k.ekle(Is("komut", "Kısa cevap ver. SADECE JSON: {\"cevap\": \"...\"}", "Yarın saat 9'daki sınav için kaçta kalkmalıyım?"))
acil.bekle()
print(f"acil is {time.time() - ta:.0f} sn'de bitti: {acil.sonuc}")
for u in uzun:
    u.bekle()
    print(f"uzun is bitti (kesilme {u.kesilme}), {len(u.sonuc or '')} karakter, hata={u.hata}")
print(f"toplam {time.time() - t0:.0f} sn")
