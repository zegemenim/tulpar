#!/usr/bin/env python3
"""Tulpar cihaz ajanı (Mac): HP'den gelen basit komutları (ses, müzik, parlaklık, rahatsız etme) uygular.
Sadece anahtarla, port 8097. Hiçbir komut dışarıdan gelen metni kabuğa vermez: işlemler sabit listedir.
YouTube Music kontrolü için Chrome'da: Görünüm > Geliştirici > "Apple Events'ten JavaScript'e İzin Ver" açık olmalı."""
import hmac
import json
import pathlib
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ANAHTAR = (pathlib.Path.home() / ".tulpar-ajan/anahtar").read_text().strip()
YTM = "music.youtube.com"


MOD_DOSYA = pathlib.Path.home() / ".tulpar-ajan/muzik"


def mod():
    """Müzik kaynağı: 'sistem' (varsayılan; sistem medya tuşları, en son çalan ne ise) ya da 'chrome' (Chrome'da YouTube Music)."""
    try:
        return "chrome" if MOD_DOSYA.read_text().strip() == "chrome" else "sistem"
    except FileNotFoundError:
        return "sistem"


def chrome_acik():  # kapalı uygulamaya "tell" göndermek onu açar; önce çalışıyor mu bak
    return subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True).returncode == 0


def osa(kod):
    return subprocess.run(["osascript", "-e", kod], capture_output=True, text=True, timeout=20)


def ses_oku():
    return int(osa("output volume of (get volume settings)").stdout.strip() or 0)


def ytm_js(js):
    """Açık YouTube Music sekmesinde JavaScript çalıştırır (Chrome)."""
    if not chrome_acik():
        return "yok"
    kod = f'''tell application "Google Chrome"
  repeat with w in windows
    repeat with t in tabs of w
      if URL of t contains "{YTM}" then return (execute t javascript "{js}")
    end repeat
  end repeat
  return "yok"
end tell'''
    r = osa(kod)
    if "turned off" in r.stderr:
        return "js_izni_yok"
    return r.stdout.strip()


JXA_TUS = """ObjC.import('Cocoa');
function tus(k, asagi) {
  var e = $.NSEvent.otherEventWithTypeLocationModifierFlagsTimestampWindowNumberContextSubtypeData1Data2(
    14, {x: 0, y: 0}, asagi ? 0xa00 : 0xb00, 0, 0, 0, 8, (k << 16) | ((asagi ? 0xa : 0xb) << 8), -1);
  $.CGEventPost(0, e.CGEvent);
}
tus(KOD, true); tus(KOD, false);"""
TUSLAR = {"cal": 16, "sonraki": 17, "onceki": 18}


def erisilebilirlik_izni():
    """Bu işlemin (ajanı çalıştıran python) Erişilebilirlik izni var mı? Yoksa medya tuşları sessizce düşer."""
    import ctypes
    try:
        lib = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        lib.AXIsProcessTrusted.restype = ctypes.c_bool
        return bool(lib.AXIsProcessTrusted())
    except Exception:  # noqa: BLE001
        return False


def medya_tusu(ad):
    """Sistem medya tuşu (Chrome JavaScript izni gerekmez; çalan YouTube Music sekmesi tuşu alır)."""
    if not erisilebilirlik_izni():
        return f"Erişilebilirlik izni yok: Sistem Ayarları > Gizlilik ve Güvenlik > Erişilebilirlik'e {sys.executable} eklenmeli"
    subprocess.run(["osascript", "-l", "JavaScript", "-e", JXA_TUS.replace("KOD", str(TUSLAR[ad]))], capture_output=True, timeout=10)
    return "tamam (medya tuşu)"


def ytm_sekmesi_var():
    """Chrome'da YouTube Music sekmesi açık mı (JavaScript izni gerekmez)?"""
    if not chrome_acik():
        return False
    r = osa(f'''tell application "Google Chrome"
  repeat with w in windows
    repeat with t in tabs of w
      if URL of t contains "{YTM}" then return "var"
    end repeat
  end repeat
  return "yok"
end tell''')
    return r.stdout.strip() == "var"


def zen_acik():
    return subprocess.run(["pgrep", "-x", "zen"], capture_output=True).returncode == 0


def medya(js, tus):
    if mod() == "sistem":
        return medya_tusu(tus)  # en son çalan ne ise onu yönetir
    sonuc = ytm_js(js)
    if sonuc == "js_izni_yok":
        return "Chrome'da Görünüm > Geliştirici > Apple Events'ten JavaScript'e İzin Ver açılmalı"
    if sonuc == "yok":
        return "Chrome'da YouTube Music açık değil"
    return sonuc or "tamam"


def ses_caliyor():
    """Mac'te şu an bir uygulama ses çalıyor mu? (güç yönetimi 'ses çalıyor' kaydından)"""
    cikti = subprocess.run(["pmset", "-g", "assertions"], capture_output=True, text=True).stdout.lower()
    return "playing audio" in cikti or "audio-out" in cikti


def ses_bekle(sn=8):
    """Çalan ses başlayana kadar en fazla `sn` saniye bekler (başka bir uygulamadaki medya geç başlayabilir)."""
    for _ in range(int(sn * 2)):
        if ses_caliyor():
            return True
        time.sleep(0.5)
    return False


def ytm_ac_ve_devam():
    """'Devam / çal' (sesli komut): zaten çalıyorsa dokunmaz; değilse klavyedeki oynat tuşu gibi basar (başka uygulamada
    duraklatılmış medya varsa o devam eder); ses hâlâ başlamazsa YouTube Music'i Chrome'dan başlatır."""
    if ses_caliyor():
        return "zaten çalıyor"
    return medya_oynat_durdur()


def medya_oynat_durdur():
    """⏯ düğmesi (her modda): önce klavyedeki oynat/durdur tuşu. Çalan bir şey varsa durdurur. Çalmıyorsa tuş başka bir
    uygulamadaki duraklatılmış medyayı başlatır; 8 sn içinde ses gelmezse son çalınan Chrome'dan başlatılır."""
    caliyordu = ses_caliyor()
    sonuc = medya_tusu("cal")
    if caliyordu or sonuc.startswith("Erişilebilirlik"):
        return sonuc  # çalan şey durduruldu
    if ses_bekle(8):
        return sonuc + " (başka uygulamadaki medya devam etti)"
    return _chrome_devam()


def _klavye_devam():
    """JavaScript izni yokken: YouTube Music sekmesini öne alıp Boşluk tuşuyla oynatır (Erişilebilirlik izni gerekir)."""
    if not erisilebilirlik_izni():
        return "Erişilebilirlik izni yok"
    if not ytm_sekmesi_var():
        osa(f'tell application "Google Chrome" to open location "https://{YTM}"')
        time.sleep(8)
    osa(f'''tell application "Google Chrome"
  activate
  repeat with w in windows
    set i to 0
    repeat with t in tabs of w
      set i to i + 1
      if URL of t contains "{YTM}" then
        set active tab index of w to i
        set index of w to 1
        return
      end if
    end repeat
  end repeat
end tell''')
    time.sleep(1)
    onde = osa('tell application "System Events" to return name of first application process whose frontmost is true').stdout.strip()
    if onde != "Google Chrome":
        return f"Chrome öne alınamadı ({onde})"
    osa('tell application "System Events" to keystroke " "')  # YouTube Music'te Boşluk: oynat/duraklat
    return "tamam (klavye)"


def _chrome_devam():
    """Chrome'da YouTube Music: oynatıcı varsa oynatır; yoksa (sayfa açılışta son çalınanı geri yüklemiyor) Geçmiş'teki
    en son şarkıyı başlatır."""
    if not ytm_sekmesi_var():
        osa(f'tell application "Google Chrome" to open location "https://{YTM}"')
        time.sleep(8)
    durum = ytm_js("document.querySelector('#play-pause-button') ? 'oynatici' : 'yok'")
    if durum == "js_izni_yok":
        return _klavye_devam()  # Chrome betik izni kapalı: klavye yöntemi
    if durum == "oynatici":
        ytm_js("(function(){var v=document.querySelector('video'); if(v&&v.paused){document.querySelector('#play-pause-button').click();}})()")
        return "baslatildi"
    ytm_js("location.href='https://" + YTM + "/history'")
    for _ in range(24):  # geçmiş listesi yüklenince hemen devam (en fazla ~12 sn)
        time.sleep(0.5)
        if ytm_js("document.querySelectorAll('ytmusic-responsive-list-item-renderer').length > 0 ? 'hazir' : 'bekle'") == "hazir":
            break
    ytm_js("(function(){var i=document.querySelector('ytmusic-responsive-list-item-renderer'); if(i){(i.querySelector('ytmusic-play-button-renderer, #play-button')||i).click();}})()")
    return "baslatildi (son çalınan: geçmişten)"


def tus(kod):  # parlaklık tuşları: 144 artır, 145 azalt (Erişilebilirlik izni gerekir)
    osa(f'tell application "System Events" to key code {kod}')


def kisayol(ad):
    r = subprocess.run(["shortcuts", "run", ad], capture_output=True, text=True, timeout=20)
    return "tamam" if r.returncode == 0 else f"kısayol çalışmadı ('{ad}' adlı Kısayol oluşturulmalı)"


def islem(ad, deger):
    if ad == "ses_ac":
        osa(f"set volume output volume {min(ses_oku() + 12, 100)}")
    elif ad == "ses_kis":
        osa(f"set volume output volume {max(ses_oku() - 12, 0)}")
    elif ad == "ses_ayar" and deger is not None:
        osa(f"set volume output volume {max(0, min(int(deger), 100))}")
    elif ad == "sessiz":
        osa("set volume with output muted")
    elif ad == "medya_dur":
        return medya_tusu("cal")  # klavyedeki oynat/durdur tuşu: çalan oturumu durdurur
    elif ad == "medya_cal":  # birleşik oynat/duraklat düğmesi
        return medya_oynat_durdur()
    elif ad == "medya_devam":
        return ytm_ac_ve_devam()
    elif ad == "medya_sonraki":
        return medya_tusu("sonraki")
    elif ad == "medya_onceki":
        return medya_tusu("onceki")
    elif ad == "parlaklik_ac":
        tus(144)  # klavyedeki tek basış gibi: tek adım
    elif ad == "parlaklik_kis":
        tus(145)
    elif ad == "rahatsiz_etme_ac":
        return kisayol("Tulpar Rahatsız Etme Aç")
    elif ad == "rahatsiz_etme_kapat":
        return kisayol("Tulpar Rahatsız Etme Kapat")
    else:
        return "bu işlem Mac'te desteklenmiyor"
    return "tamam"


class Is(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        govde, kod = {"durum": "yetkisiz"}, 401
        if self.path == "/islem" and hmac.compare_digest(self.headers.get("x-tulpar-anahtar", ""), ANAHTAR):
            try:
                v = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 2000)))
                govde, kod = {"durum": islem(str(v.get("islem")), v.get("deger"))}, 200
            except Exception as e:  # noqa: BLE001
                govde, kod = {"durum": f"hata: {type(e).__name__}"}, 500
        b = json.dumps(govde, ensure_ascii=False).encode()
        self.send_response(kod); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


def ytm_sarki_cal(ad):
    """YouTube Music'te arar ve ilk şarkıyı çalar (sayfa yapısına bağlı, kırılabilir)."""
    if mod() == "sistem":
        return "Sistem modunda şarkı adıyla arama yapılamaz; müzik kaynağını Chrome yap"
    ad = "".join(c for c in str(ad) if c.isalnum() or c in " -'").strip()[:80]
    if not ad:
        return "şarkı adı boş"
    url = "https://" + YTM + "/search?q=" + ad.replace(" ", "+")
    osa(f'tell application "Google Chrome" to open location "{url}"')
    time.sleep(6)
    js = ("(document.querySelector('ytmusic-shelf-renderer ytmusic-responsive-list-item-renderer #play-button')"
          "||document.querySelector('ytmusic-responsive-list-item-renderer')).click();'tamam'")
    return ytm_js(js) or "tamam"


# ---- pano eşitleme: ~/.tulpar-ajan/hp.json {"adres": "http://100.x:8000", "anahtar": "..."} varsa çalışır ----
def pano_esitle():
    import urllib.request
    yol = pathlib.Path.home() / ".tulpar-ajan/hp.json"
    if not yol.exists():
        return
    hp = json.loads(yol.read_text())
    adresler = hp.get("adresler") or [hp.get("adres", "")]
    baslik = {"x-tulpar-anahtar": hp["anahtar"], "Content-Type": "application/json"}

    def git(yol_, govde=None):  # ilk cevap veren adres (Tailscale / ev ağı)
        for ad in adresler:
            try:
                r = urllib.request.Request(ad + yol_, headers=baslik, data=json.dumps(govde).encode() if govde is not None else None)
                return json.load(urllib.request.urlopen(r, timeout=4))
            except Exception:  # noqa: BLE001
                continue
        raise ConnectionError("HP yok")
    son = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    while True:
        time.sleep(2)
        try:
            simdi = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
            if simdi != son and simdi.strip():
                son = simdi
                git("/pano", {"metin": simdi, "kaynak": "mac"})
            else:
                r = git("/pano")
                if r["metin"] and r["kaynak"] != "mac" and r["metin"] != son:
                    son = r["metin"]
                    subprocess.run(["pbcopy"], input=son, text=True)
        except Exception:  # noqa: BLE001  ağ yoksa sessizce yeniden dener
            time.sleep(10)


if __name__ == "__main__":
    import threading
    threading.Thread(target=pano_esitle, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", 8097), Is).serve_forever()
