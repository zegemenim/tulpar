#!/usr/bin/env python3
"""Tulpar cihaz ajanı (Mac): HP'den gelen basit komutları (ses, müzik, parlaklık, rahatsız etme) uygular.
Sadece anahtarla, port 8097. Hiçbir komut dışarıdan gelen metni kabuğa vermez: işlemler sabit listedir.
YouTube Music kontrolü için Chrome'da: Görünüm > Geliştirici > "Apple Events'ten JavaScript'e İzin Ver" açık olmalı."""
import hmac
import json
import pathlib
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ANAHTAR = (pathlib.Path.home() / ".tulpar-ajan/anahtar").read_text().strip()
YTM = "music.youtube.com"


def osa(kod):
    return subprocess.run(["osascript", "-e", kod], capture_output=True, text=True, timeout=20)


def ses_oku():
    return int(osa("output volume of (get volume settings)").stdout.strip() or 0)


def ytm_js(js):
    """Açık YouTube Music sekmesinde JavaScript çalıştırır (Chrome)."""
    kod = f'''tell application "Google Chrome"
  repeat with w in windows
    repeat with t in tabs of w
      if URL of t contains "{YTM}" then return (execute t javascript "{js}")
    end repeat
  end repeat
  return "yok"
end tell'''
    return osa(kod).stdout.strip()


def ytm_ac_ve_devam():
    if ytm_js("1") == "yok":
        osa(f'tell application "Google Chrome" to open location "https://{YTM}"')
        time.sleep(8)  # sayfa ve son çalınan yüklensin
    sonuc = ytm_js("(document.querySelector('#play-pause-button').title||'').toLowerCase().includes('oynat')||(document.querySelector('#play-pause-button').title||'').toLowerCase().includes('play')?(document.querySelector('#play-pause-button').click(),'baslatildi'):'zaten calisiyor'")
    return sonuc or "tamam"


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
    elif ad in ("medya_dur", "medya_cal"):
        return ytm_js("document.querySelector('#play-pause-button').click()") or "tamam"
    elif ad == "medya_devam":
        return ytm_ac_ve_devam()
    elif ad == "medya_sonraki":
        return ytm_js("document.querySelector('.next-button').click()") or "tamam"
    elif ad == "medya_onceki":
        return ytm_js("document.querySelector('.previous-button').click()") or "tamam"
    elif ad == "parlaklik_ac":
        for _ in range(4):
            tus(144)
    elif ad == "parlaklik_kis":
        for _ in range(4):
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


ThreadingHTTPServer(("0.0.0.0", 8097), Is).serve_forever()
