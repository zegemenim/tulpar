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
    r = urllib.request.Request(HP["adres"] + yol, headers={"x-tulpar-anahtar": HP["anahtar"], "Content-Type": "application/json"},
                               data=json.dumps(govde).encode() if govde is not None else None)
    return json.load(urllib.request.urlopen(r, timeout=6))


def mac(islem, deger=None):
    r = urllib.request.Request("http://127.0.0.1:8097/islem", headers={"x-tulpar-anahtar": AJAN_ANAHTAR},
                               data=json.dumps({"islem": islem, "deger": deger}).encode())
    try:
        return json.load(urllib.request.urlopen(r, timeout=25))["durum"]
    except Exception as e:  # noqa: BLE001
        return f"hata: {type(e).__name__}"


class Menu(rumps.App):
    def __init__(self):
        super().__init__("T", quit_button="Çık")
        self.menu = [
            "Taslaklar", "Görevler", None,
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

    @rumps.timer(30)
    def yenile(self, _=None):
        if HP is None:
            return
        try:
            t = hp("/onaylar")
            g = hp("/gorevler")
        except Exception:  # noqa: BLE001
            self.title = "T!"
            return
        self.title = f"T {len(t)}" if t else "T"
        self._liste("Taslaklar", [f"{o['veri'].get('kisi') or o['veri'].get('sohbet') or o.get('tur')}: {str(o['veri'].get('metin', ''))[:40]}" for o in t])
        self._liste("Görevler", [str(x.get("baslik") or x.get("metin") or x)[:50] for x in g])

    def _liste(self, ad, satirlar):
        alt = self.menu[ad]
        alt.clear()
        for s in satirlar[:12] or ["(boş)"]:
            alt.add(rumps.MenuItem(s))


Menu().run()
