"""Raspberry Pi'de çalışan konuşma sentezi (Piper) servisi: HP'nin işlemcisini rahatlatır.
HP'deki core/tts.py'yi aynen kullanır (sözlük ve ses ayarı tek yerde kalır). Sadece ev ağından, anahtarla erişilir.
POST /uret {"metin": "..."} -> audio/wav"""
import hmac
import json
import os
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KOK = pathlib.Path(__file__).parent
sys.path.insert(0, str(KOK))
import tts  # noqa: E402  (core/tts.py kopyası)

tts.MODEL = str(KOK / "ses/tr_TR-dfki-medium.onnx")
ANAHTAR = (KOK / "anahtar").read_text().strip()
PORT = int(os.environ.get("PORT", "8095"))


class Is(BaseHTTPRequestHandler):
    def log_message(self, *a):  # sessiz
        pass

    def _bitir(self, kod, govde=b"", tur="application/json"):
        self.send_response(kod)
        self.send_header("Content-Type", tur)
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def do_POST(self):
        if self.path != "/uret":
            return self._bitir(404, b"{}")
        if not hmac.compare_digest(self.headers.get("x-tulpar-anahtar", ""), ANAHTAR):
            return self._bitir(401, b"{}")
        try:
            uzun = int(self.headers.get("Content-Length", "0"))
            metin = json.loads(self.rfile.read(min(uzun, 20000)))["metin"]
            wav = tts.uret(metin)
        except Exception as e:  # noqa: BLE001
            return self._bitir(500, json.dumps({"hata": str(e)[:200]}).encode())
        self._bitir(200, wav, "audio/wav")

    def do_GET(self):
        self._bitir(200, b'{"durum": "hazir"}')


ThreadingHTTPServer(("0.0.0.0", PORT), Is).serve_forever()
