"""Bildirim süzgeci: OTP kaydedilmez, normal bildirim kaydedilir, tekrar yok sayılır. Çalıştır: python test_bildirim.py"""
import pathlib
import tempfile

import bildirim
import para

bildirim.DOSYA = pathlib.Path(tempfile.mkdtemp()) / "b.jsonl"
para.DOSYA = bildirim.DOSYA.with_name("p.jsonl")

OTP = ["Doğrulama kodunuz: 482913", "Your verification code is 5521", "Şifreniz 123456, kimseyle paylaşmayın",
       "3D Secure onay kodu 904215 ile 250,00 TL işlem"]
NORMAL = ["Kartınızdan 1.250,00 TL harcama yapıldı", "Siparişiniz 1234567 numarası ile yola çıktı", "Yarın saat 14:30 toplantı",
          "Kodu yazdım abi bakarsın"]
for t in OTP:
    assert bildirim.kod_iceriyor(t), t
for t in NORMAL:
    assert not bildirim.kod_iceriyor(t), t

assert not bildirim.yaz("sms", "Banka", OTP[0], "sms")
assert bildirim.yaz("sms", "Banka", NORMAL[0], "sms")
assert not bildirim.yaz("sms", "Banka", NORMAL[0], "sms"), "aynı bildirim tekrar kaydedilmemeli"
assert bildirim.yaz("com.x", "", NORMAL[2])
assert not bildirim.yaz("com.x", "", "   ")
assert len(bildirim.liste()) == 2 and len(bildirim.liste(tur="sms")) == 1
KODLAR = {
    "Doğrulama kodunuz: 482913": "482913",
    "B1245 referanslı işleminiz için tek kullanımlık şifreniz 739104": "739104",
    "Your verification code is 5521. Do not share.": "5521",
    "3D Secure şifresi: 904215 - 250,00 TL tutarındaki işlem için": "904215",
    "Kod 123-456 (geçerlilik 5 dk). Ref no 889900": "123456",
    "Sipariş 5543210 için onay kodunuz 8821, bakiyeniz 12000 TL": "8821",
    "Giriş kodun G7H2K9 kimseyle paylaşma": "G7H2K9",
    "Merhaba 2024 yılı kampanya": None,
}
for metin, beklenen in KODLAR.items():
    assert bildirim.kod_cikar(metin) == beklenen, (metin, bildirim.kod_cikar(metin))
assert bildirim.onemli({"tur": "sms", "baslik": "x", "metin": "y"})
assert bildirim.onemli({"tur": "bildirim", "baslik": "Kargo", "metin": "Paketiniz teslim edildi"})
assert not bildirim.onemli({"tur": "bildirim", "baslik": "Oyun", "metin": "Günlük ödülünü al"})

import pano
pano.DOSYA = pathlib.Path(tempfile.mkdtemp()) / "p.jsonl"
assert pano.yaz("482913", "test", kod=True) and pano.oku()["metin"] == "482913"
assert pano.gecmis()[0]["metin"] == "482913"
pano._son["sona_erer"] = 1  # süresi dolmuş kod geçmişte görünmemeli
pano.DOSYA.write_text(pano.DOSYA.read_text().replace(pano.DOSYA.read_text().split('"sona_erer": ')[1].split("}")[0], "1"))
assert pano.gecmis() == []
print("tamam")
