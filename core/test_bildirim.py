"""Bildirim süzgeci: OTP kaydedilmez, normal bildirim kaydedilir, tekrar yok sayılır. Çalıştır: python test_bildirim.py"""
import pathlib
import tempfile

import bildirim

bildirim.DOSYA = pathlib.Path(tempfile.mkdtemp()) / "b.jsonl"

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
print("tamam")
