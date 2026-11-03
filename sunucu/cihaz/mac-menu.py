#!/usr/bin/env python3
"""Tulpar menü çubuğu uygulaması (Mac): taslaklar, görevler ve bu Mac'in kontrolleri. Gerekli: pip install rumps.
Ayar: ~/.tulpar-ajan/hp.json {"adres": "http://100.x:8000", "anahtar": "..."}; Mac ajanı (8097) aynı klasörde çalışır."""
import json
import pathlib
import urllib.request

import threading

import objc
import rumps
from AppKit import NSButton, NSMakeRect, NSTextField, NSView
from Foundation import NSObject

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


class DugmeHedefi(NSObject):
    """Menü içindeki özel görünüm düğmeleri: basınca menü KAPANMAZ, art arda basılabilir."""
    def init(self):
        self = objc.super(DugmeHedefi, self).init()
        self.islemler = []
        return self

    def tikla_(self, gonderen):
        islem = self.islemler[gonderen.tag()]
        threading.Thread(target=mac, args=(islem,), daemon=True).start()


HEDEFLER_REF = []  # nesneler bellekten silinmesin


def dugme_satiri(baslik, dugmeler):
    """dugmeler: [(yazı, işlem)]; menüde açık kalan tek satır."""
    hedef = DugmeHedefi.alloc().init()
    hedef.islemler = [i for _, i in dugmeler]
    gorunum = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 270, 30))
    etiket = NSTextField.labelWithString_(baslik)
    etiket.setFrame_(NSMakeRect(14, 5, 90, 20))
    gorunum.addSubview_(etiket)
    x = 100
    for sira, (yazi, _) in enumerate(dugmeler):
        d = NSButton.buttonWithTitle_target_action_(yazi, hedef, "tikla:")
        d.setTag_(sira)
        d.setFrame_(NSMakeRect(x, 2, 50, 26))
        gorunum.addSubview_(d)
        x += 54
    HEDEFLER_REF.append(hedef)
    oge = rumps.MenuItem(baslik)
    oge._menuitem.setView_(gorunum)
    return oge


class Menu(rumps.App):
    def __init__(self):
        super().__init__("T", quit_button="Çık")
        self.hedef_menu = rumps.MenuItem("Hedef cihaz: mac")
        self.hedef_menu.add(rumps.MenuItem("mac", callback=self.sec))
        self.menu = [
            "Taslaklar", "Görevler", "WhatsApp özeti", "Telefon bildirimleri", "Pano geçmişi", None,
            dugme_satiri("Ses", [("−", "ses_kis"), ("+", "ses_ac"), ("🔇", "sessiz")]),
            dugme_satiri("Parlaklık", [("−", "parlaklik_kis"), ("+", "parlaklik_ac")]),
            dugme_satiri("Müzik", [("⏮", "medya_onceki"), ("⏯", "medya_cal"), ("⏭", "medya_sonraki")]),
            None, self.hedef_menu,
            ("Müzik kaynağı", [rumps.MenuItem("Sistem (en son çalan)", callback=lambda _: mac("muzik_sistem")),
                               rumps.MenuItem("Google Chrome", callback=lambda _: mac("muzik_chrome"))]),
            ("Rahatsız etme", [rumps.MenuItem("Aç", callback=lambda _: mac("rahatsiz_etme_ac")),
                               rumps.MenuItem("Kapat", callback=lambda _: mac("rahatsiz_etme_kapat"))]),
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
            oz = hp("/ozet")
            bi = hp("/bildirim?n=15&onemli=true")
        except Exception:  # noqa: BLE001
            self.title = "T!"
            return
        self.title = f"T {len(t)}" if t else "T"
        self._liste("Taslaklar", [f"{x.get('sohbet_adi')}: {str(x.get('ozet', ''))[:45]}" for x in t])
        self._liste("Görevler", [str(x.get("metin"))[:50] for x in g])
        self._liste("WhatsApp özeti", [("⚠ " if x["cevap_gerekli"] else "") + f"{x['ad']}: {x['ozet']}"[:70] for x in oz.get("sohbetler", [])])
        self._liste("Telefon bildirimleri", [f"{x['baslik'] or x['paket'].split('.')[-1]}: {x['metin']}".replace("\n", " ")[:70] for x in bi])
        self._liste("Pano geçmişi", [str(x["metin"]).replace("\n", " ")[:50] for x in p], lambda ad, tam=p: None)

    def _liste(self, ad, satirlar, _=None):
        alt = self.menu[ad]
        alt.clear()
        for s in satirlar[:12] or ["(boş)"]:
            alt.add(rumps.MenuItem(s))


Menu().run()
