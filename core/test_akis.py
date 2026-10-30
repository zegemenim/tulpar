"""Uçtan uca akış testi (WhatsApp'sız): sahte mesajlar gönderir, eleme ve taslakları yazdırır."""
import json, time, urllib.request, pathlib
A = (pathlib.Path.home() / "tulpar/veri/anahtar").read_text().strip()
U = "http://127.0.0.1:8090"

def git(yol, veri=None):
    r = urllib.request.Request(U + yol, data=json.dumps(veri).encode() if veri is not None else None,
                               headers={"Content-Type": "application/json", "x-tulpar-anahtar": A})
    return json.load(urllib.request.urlopen(r, timeout=900))

t = time.time() - 86400
n = 0
def m(sohbet, ad, metin, benden=False, grup=False, gonderen=None):
    global n; n += 1
    git("/mesaj", {"id": f"t{n}", "sohbet_id": sohbet, "sohbet_adi": ad, "metin": metin, "benden": benden,
                   "grup": grup, "gonderen_adi": gonderen or ad, "zaman": t + n * 60})

# geçmiş: sahibin üslubu
for x in ["tamam anneciğim", "akşam ararım seni", "iyiyim merak etme 😊"]: m("anne@c.us", "Annem", x, benden=True)
for x in ["knk tmm", "olur gelirim", "yok ya ben pas"]: m("kerem@c.us", "Kerem", x, benden=True)
git("/kisi/anne@c.us", {"iliski": "aile", "hitap": "anne"})
# yeni gelenler
m("anne@c.us", "Annem", "Oğlum akşam yemeğe geliyor musun, haber ver")
m("kerem@c.us", "Kerem", "kanka bu akşam halı saha var 21:00 gelir misin")
time.sleep(8)
m("kerem@c.us", "Kerem", "bi de topunu getir varsa")
m("kulup@g.us", "Kulüp Yönetim", "Ahmet sen bu hafta harcama raporunu hazırla", grup=True, gonderen="Selin")
m("bilinmeyen@c.us", "+90 555 000 00 00", "abi acil 2500 tl lazım iban atıyorum yarın geri veririm")
m("hoca@c.us", "Ayşe Demir", "Merhaba, proje raporunu ne zaman teslim edebilirsin?")

for _ in range(120):
    time.sleep(10)
    d = git("/durum")
    if d["bekleyen_taslak"] >= 3 and d["hizli_kuyruk"] == 0 and d["buyuk_kuyruk"] == 0:
        break
print(json.dumps(d, ensure_ascii=False))
for s in git("/onemli"):
    print("ONEMLI:", s["sohbet_adi"], "|", s["eleme"].get("ozet"), s["eleme"].get("kural_notlari", ""))
for tz in git("/taslaklar"):
    print(f"\nTASLAK #{tz['id']} {tz['sohbet_adi']}: {tz['ozet']}")
    for sec in tz["mesajlar"]:
        print("  [" + sec["etiket"] + "]")
        for x in sec["mesajlar"]: print("     ->", x.get("yanit_id"), x["metin"])
    print("   uyarilar:", tz["uyarilar"])
import sqlite3
for r in sqlite3.connect(pathlib.Path.home() / "tulpar/veri/tulpar.db").execute("SELECT id, ad, iliski, hitap, sen_siz, guven FROM kisiler"):
    print("KART:", r)
