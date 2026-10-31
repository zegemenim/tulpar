"""Raspberry Pi'de çalışan web araştırma servisi: HP'deki core/tarayici.py'yi aynen kullanır (salt okunur kurallar tek yerde).
Aynı anda tek araştırma, sistem Chromium'u, bellek sınırlı. Sadece anahtarla. POST /ara {"soru": "...", "n": 3}"""
import hmac
import json
import pathlib
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KOK = pathlib.Path(__file__).parent
sys.path.insert(0, str(KOK))
import tarayici  # noqa: E402  (core/tarayici.py kopyası)

ANAHTAR = (KOK / "anahtar-arastir").read_text().strip()


class Is(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _bitir(self, kod, govde):
        b = json.dumps(govde, ensure_ascii=False).encode()
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        if self.path != "/ara":
            return self._bitir(404, {})
        if not hmac.compare_digest(self.headers.get("x-tulpar-anahtar", ""), ANAHTAR):
            return self._bitir(401, {})
        try:
            veri = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length", "0")), 5000)))
            sayfalar = tarayici.yerel_ara(str(veri["soru"])[:500], max(1, min(int(veri.get("n", 3)), 5)))
            self._bitir(200, {"sayfalar": sayfalar})
        except tarayici.BotKorumasi as e:
            self._bitir(200, {"bot": str(e)})
        except Exception as e:  # noqa: BLE001
            self._bitir(500, {"hata": f"{type(e).__name__}: {str(e)[:200]}"})

    def do_GET(self):
        self._bitir(200, {"durum": "hazir"})


ThreadingHTTPServer(("0.0.0.0", 8096), Is).serve_forever()
