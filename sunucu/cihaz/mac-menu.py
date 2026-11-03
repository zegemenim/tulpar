#!/usr/bin/env python3
"""Tulpar menü çubuğu uygulaması (Mac): taslaklar, görevler ve bu Mac'in kontrolleri. Gerekli: pip install rumps.
Ayar: ~/.tulpar-ajan/hp.json {"adres": "http://100.x:8000", "anahtar": "..."}; Mac ajanı (8097) aynı klasörde çalışır."""
import json
import pathlib
import urllib.request

import rumps

K = pathlib.Path.home() / ".tulpar-ajan"
try:
    HP = json.loads((K / "hp.json").read_text())
except FileNotFoundError:
    HP = None  # HP bağlantısı yoksa yalnızca bu Mac'in kontrolleri çalışır
AJAN_ANAHTAR = (K / "anahtar").read_text().strip()


def hp(yol, govde=None):
    for adres in HP.get("adresler") or [HP["adres"]]:  # Tailscale ya da ev ağı: ilk cevap veren
        try:
            r = urllib.request.Request(adres + yol, headers={"x-tulpar-anahtar": HP["anahtar"], "Content-Type": "application/json"},
                                       data=json.dumps(govde).encode() if govde is not None else None)
            return json.load(urllib.request.urlopen(r, timeout=5))
        except Exception:  # noqa: BLE001
            continue
    raise ConnectionError("HP yok")


HEDEF = {"ad": "mac"}  # menüden seçilen cihaz


def mac(islem, deger=None):
    if HEDEF["ad"] != "mac":  # başka cihaz: HP üzerinden gönder
        try:
            return hp("/cihaz/komut", {"hedef": HEDEF["ad"], "islem": islem, "deger": deger})["durum"]
        except Exception as e:  # noqa: BLE001
            return f"hata: {type(e).__name__}"
    r = urllib.request.Request("http://127.0.0.1:8097/islem", headers={"x-tulpar-anahtar": AJAN_ANAHTAR},
                               data=json.dumps({"islem": islem, "deger": deger}).encode())
    try:
        return json.load(urllib.request.urlopen(r, timeout=25))["durum"]
    except Exception as e:  # noqa: BLE001
        return f"hata: {type(e).__name__}"


class Menu(rumps.App):
    def __init__(self):
        super().__init__("T", quit_button="Çık")
        self.hedef_menu = rumps.MenuItem("Hedef cihaz: mac")
        self.hedef_menu.add(rumps.MenuItem("mac", callback=self.sec))
        self.menu = [
            "Taslaklar", "Görevler", "Pano geçmişi", None, self.hedef_menu,
            ("Ses", [rumps.MenuItem("Aç", callback=lambda _: mac("ses_ac")), rumps.MenuItem("Kıs", callback=lambda _: mac("ses_kis")),
                     rumps.MenuItem("Sessiz", callback=lambda _: mac("sessiz"))]),
            ("Müzik", [rumps.MenuItem("Duraklat / Oynat", callback=lambda _: mac("medya_cal")),
                       rumps.MenuItem("Sonraki", callback=lambda _: mac("medya_sonraki")),
                       rumps.MenuItem("Önceki", callback=lambda _: mac("medya_onceki"))]),
            ("Ekran", [rumps.MenuItem("Parlaklık +", callback=lambda _: mac("parlaklik_ac")),
                       rumps.MenuItem("Parlaklık -", callback=lambda _: mac("parlaklik_kis")),
                       rumps.MenuItem("Rahatsız etme aç", callback=lambda _: mac("rahatsiz_etme_ac")),
                       rumps.MenuItem("Rahatsız etme kapat", callback=lambda _: mac("rahatsiz_etme_kapat"))]),
            None,
        ]

    def sec(self, oge):
        HEDEF["ad"] = oge.title
        self.hedef_menu.title = f"Hedef cihaz: {oge.title}"

    @rumps.timer(30)
    def yenile(self, _=None):
        if HP is None:
            return
        try:
            alt = self.hedef_menu
            for ad in hp("/cihaz/liste"):
                if ad not in alt:
                    alt.add(rumps.MenuItem(ad, callback=self.sec))
        except Exception:  # noqa: BLE001
            pass
        try:
            t = [x for x in hp("/taslaklar") if x.get("durum") == "bekliyor"]
            g = hp("/gorevler")
            p = hp("/pano/gecmis?n=10")
        except Exception:  # noqa: BLE001
            self.title = "T!"
            return
        self.title = f"T {len(t)}" if t else "T"
        self._liste("Taslaklar", [f"{x.get('sohbet_adi')}: {str(x.get('ozet', ''))[:45]}" for x in t])
        self._liste("Görevler", [str(x.get("metin"))[:50] for x in g])
        self._liste("Pano geçmişi", [str(x["metin"]).replace("\n", " ")[:50] for x in p], lambda ad, tam=p: None)

    def _liste(self, ad, satirlar, _=None):
        alt = self.menu[ad]
        alt.clear()
        for s in satirlar[:12] or ["(boş)"]:
            alt.add(rumps.MenuItem(s))


Menu().run()
