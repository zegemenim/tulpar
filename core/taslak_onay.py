"""Terminalde taslak inceleme ve onay (Android uygulaması gelene kadar).
Kullanım: tulpar-taslaklar   (Mac'ten: ssh -t tulpar tulpar-taslaklar)
Her taslakta: seçenek numarası = o seçeneği gönder, d = düzenleyip gönder, r = reddet, Enter = sonra bak, q = çık.
Hiçbir şey 'e' ile ayrıca onaylanmadan gönderilmez."""
import json
import pathlib
import urllib.error
import urllib.request
from datetime import datetime

ANAHTAR = (pathlib.Path.home() / "tulpar/veri/anahtar").read_text().strip()
U = "http://127.0.0.1:8090"
K, Y, S, M, D, N = "\033[1m", "\033[32m", "\033[33m", "\033[36m", "\033[2m", "\033[0m"


def git(yol, veri=None):
    r = urllib.request.Request(U + yol, data=json.dumps(veri).encode() if veri is not None else None,
                               headers={"Content-Type": "application/json", "x-tulpar-anahtar": ANAHTAR})
    return json.load(urllib.request.urlopen(r, timeout=120))


def goster(t, sira, toplam):
    print(f"\n{K}── Taslak {sira}/{toplam} · {t['sohbet_adi']} · {datetime.fromtimestamp(t['olusturma']):%d.%m %H:%M} ──{N}")
    for g in t["gelenler"]:
        print(f"  {M}{g['gonderen_adi']}:{N} {g['metin']}")
    if t.get("ozet"):
        print(f"  {D}özet: {t['ozet']}{N}")
    for u in t["uyarilar"]:
        if isinstance(u, str):
            print(f"  {S}! {u}{N}")
    for i, sec in enumerate(t["mesajlar"], 1):
        print(f"  {Y}{i}) {sec['etiket']}{N}")
        for m in sec["mesajlar"]:
            alinti = next((g["metin"][:40] for g in t["gelenler"] if g["id"] == m.get("yanit_id")), None)
            if alinti:
                print(f"       {D}↪ {alinti}{N}")
            print(f"       {m['metin']}")


def duzenle(t):
    print("  Her satır ayrı mesaj olarak gider. Bitirmek için boş satır.")
    satirlar = []
    while (s := input("  > ").strip()):
        satirlar.append(s)
    if not satirlar:
        return None
    hedef = t["mesaj_idler"][-1] if t["mesaj_idler"] else None
    return [{"yanit_id": hedef if i == 0 else None, "metin": s} for i, s in enumerate(satirlar)]


def ana():
    taslaklar = git("/taslaklar")
    if not taslaklar:
        print("Bekleyen taslak yok.")
        return
    for sira, t in enumerate(taslaklar, 1):
        goster(t, sira, len(taslaklar))
        secim = input(f"\n  {K}Seçim{N} [1-{len(t['mesajlar'])} gönder · d düzenle · r reddet · Enter geç · q çık]: ").strip().lower()
        if secim == "q":
            return
        if secim == "r":
            git(f"/taslak/{t['id']}/reddet", {})
            print("  reddedildi")
            continue
        govde = None
        if secim == "d":
            mesajlar = duzenle(t)
            govde = {"mesajlar": mesajlar} if mesajlar else None
        elif secim.isdigit() and 1 <= int(secim) <= len(t["mesajlar"]):
            govde = {"secenek": int(secim) - 1}
            if any("[" in m["metin"] for m in t["mesajlar"][int(secim) - 1]["mesajlar"]):
                print(f"  {S}Bu seçenekte doldurulması gereken [boşluk] var; d ile düzenle.{N}")
                continue
        if not govde:
            continue
        if input(f"  {S}{t['sohbet_adi']} kişisine gönderilsin mi? (e/h): {N}").strip().lower() != "e":
            print("  gönderilmedi")
            continue
        try:
            git(f"/taslak/{t['id']}/gonder", govde)
            print(f"  {Y}gönderildi ✓{N}")
        except urllib.error.HTTPError as e:
            print(f"  {S}gönderilemedi: {e.read().decode()[:200]}{N}")


if __name__ == "__main__":
    try:
        ana()
    except (KeyboardInterrupt, EOFError):
        print()
