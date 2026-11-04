#!/usr/bin/env python3
"""Tulpar menü çubuğu uygulaması (Mac): taslaklar, görevler ve bu Mac'in kontrolleri. Gerekli: pip install rumps.
Ayar: ~/.tulpar-ajan/hp.json {"adres": "http://100.x:8000", "anahtar": "..."}; Mac ajanı (8097) aynı klasörde çalışır."""
import json
import pathlib
import urllib.request

import threading

import objc
import rumps
from AppKit import NSButton, NSMakeRect, NSPasteboard, NSPasteboardTypeString, NSTextField, NSView
from Foundation import NSObject

K = pathlib.Path.home() / ".tulpar-ajan"
try:
    HP = json.loads((K / "hp.json").read_text())
except FileNotFoundError:
    HP = None  # HP bağlantısı yoksa yalnızca bu Mac'in kontrolleri çalışır
AJAN_ANAHTAR = (K / "anahtar").read_text().strip()


SON_ADRES = {"adres": None}


def hp(yol, govde=None):
    adresler = HP.get("adresler") or [HP["adres"]]  # Tailscale ya da ev ağı: ilk cevap veren; son çalışan önce denenir
    for adres in sorted(adresler, key=lambda a: a != SON_ADRES["adres"]):
        try:
            r = urllib.request.Request(adres + yol, headers={"x-tulpar-anahtar": HP["anahtar"], "Content-Type": "application/json"},
                                       data=json.dumps(govde).encode() if govde is not None else None)
            sonuc = json.load(urllib.request.urlopen(r, timeout=4))
            SON_ADRES["adres"] = adres
            return sonuc
        except Exception:  # noqa: BLE001
            continue
    raise ConnectionError("HP yok")


HEDEF = {"ad": "telefon" if HP else "mac"}  # menüden seçilen cihaz


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


def kopyala(metin):
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(metin, NSPasteboardTypeString)


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


def metin_ogesi(metin):
    """Uzun metni satırlara bölerek gösteren menü öğesi."""
    alan = NSTextField.wrappingLabelWithString_(metin[:1500])
    yukseklik = alan.cell().cellSizeForBounds_(NSMakeRect(0, 0, 400, 10000)).height
    alan.setFrame_(NSMakeRect(14, 5, 400, yukseklik))
    gorunum = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 428, yukseklik + 10))
    gorunum.addSubview_(alan)
    oge = rumps.MenuItem("Tam metin")
    oge._menuitem.setView_(gorunum)
    return oge


class Menu(rumps.App):
    def __init__(self):
        super().__init__("T", quit_button="Çık")
        self._gelen, self._getiriliyor = None, False
        self.hedef_menu = rumps.MenuItem(f"Hedef cihaz: {HEDEF['ad']}")
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

    def _getir(self):
        """Ağ işi arka planda: ulaşılamayan adres menüyü dondurmasın. Menü ana iş parçacığında (uygula) güncellenir."""
        try:
            self._gelen = {"cihazlar": hp("/cihaz/liste"), "t": [x for x in hp("/taslaklar") if x.get("durum") == "bekliyor"], "g": hp("/gorevler"),
                           "p": hp("/pano/gecmis?n=10"), "oz": hp("/ozet"), "bi": hp("/bildirim?n=15&onemli=true")}
        except Exception:  # noqa: BLE001
            self._gelen = {}
        finally:
            self._getiriliyor = False

    @rumps.timer(30)
    def yenile(self, _=None):
        if HP is not None and not self._getiriliyor:
            self._getiriliyor = True
            threading.Thread(target=self._getir, daemon=True).start()

    @rumps.timer(1)
    def uygula(self, _=None):
        v, self._gelen = self._gelen, None
        if v is None:
            return
        if not v:
            self.title = "T!"
            return
        t, g, p, oz, bi = v["t"], v["g"], v["p"], v["oz"], v["bi"]
        for ad in v["cihazlar"]:
            if ad not in self.hedef_menu:
                self.hedef_menu.add(rumps.MenuItem(ad, callback=self.sec))
        self.title = f"T {len(t)}" if t else "T"
        self._liste("Taslaklar", [f"{x.get('sohbet_adi')}: {str(x.get('ozet', ''))[:45]}" for x in t], [f"{x.get('sohbet_adi')}\n{x.get('ozet', '')}" for x in t])
        self._liste("Görevler", [str(x.get("metin"))[:50] for x in g], [str(x.get("metin")) for x in g])
        self._liste("WhatsApp özeti", [("⚠ " if x["cevap_gerekli"] else "") + f"{x['ad']}: {x['ozet']}"[:70] for x in oz.get("sohbetler", [])],
                    [f"{x['ad']}\n{x['ozet']}" + (f"\n\nYapılacak: {x['ne']}" if x.get("ne") else "") for x in oz.get("sohbetler", [])])
        self._liste("Telefon bildirimleri", [f"{x['baslik'] or x['paket'].split('.')[-1]}: {x['metin']}".replace("\n", " ")[:70] for x in bi], [f"{x['baslik']}\n{x['metin']}".strip() for x in bi])
        self._liste("Pano geçmişi", [str(x["metin"]).replace("\n", " ")[:50] for x in p], [str(x["metin"]) for x in p])

    def _liste(self, ad, satirlar, tamlar=None):
        """tamlar verilirse satırın üstüne gelince tam metin açılır; altındaki Kopyala Mac panosuna alır."""
        alt = self.menu[ad]
        if alt._menu is not None:  # alt menüsü henüz yoksa rumps clear() hata verir
            alt.clear()
        for i, s in enumerate(satirlar[:12] or ["(boş)"]):
            oge = rumps.MenuItem(s)
            if tamlar and satirlar:
                oge.add(metin_ogesi(tamlar[i]))
                oge.add(rumps.MenuItem("Kopyala", callback=lambda _, t=tamlar[i]: kopyala(t)))
            alt.add(oge)


Menu().run()
