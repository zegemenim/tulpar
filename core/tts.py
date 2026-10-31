"""Konuşma sentezi (HP'de, çevrimdışı): Piper Türkçe ses. Telefonun kendi sesi yerine bu kullanılır; böylece
Türkçe karakterler ve tonlama telefon ayarlarından bağımsız doğru çıkar. İngilizce terimler için telaffuz sözlüğü var."""
import io
import re
import threading
import time
import wave

from kuyruk import log

MODEL = "/home/zegemenim/tulpar/models/piper/tr_TR-dfki-medium.onnx"
_ses = None
_kilit = threading.Lock()
_son = 0.0
BOSTA_SN = 300

# Türkçe sesin doğru okuması için İngilizce terimlerin Türkçe yazımı (küçük harf). Yenileri buraya eklenir.
SOZLUK = {
    "deploy": "diploy", "commit": "komit", "push": "puş", "pull": "pul", "merge": "mörç", "branch": "brençh",
    "server": "sörvır", "serverı": "sörvırı", "prompt": "prompt", "meeting": "miting", "deadline": "dedlayn",
    "feedback": "fidbek", "update": "apdeyt", "app": "ep", "link": "link", "story": "stori", "email": "imeyl",
    "mail": "meyl", "whatsapp": "votsap", "instagram": "instagram", "google": "gugıl", "gmail": "cimeyl",
    "youtube": "yutub", "wifi": "vayfay", "wi-fi": "vayfay", "online": "onlayn", "offline": "oflayn",
    "tailscale": "teylskeyl", "github": "gitab", "claude": "klod", "gemma": "cemma", "whisper": "vispır",
    "tulpar": "tulpar", "kâhya": "kâhya", "ok": "okey", "okay": "okey", "bug": "bag", "fix": "fiks",
    "test": "test", "backup": "bekap", "download": "davnlod", "upload": "aplod", "login": "login", "password": "pasvörd",
    "pdf": "pe de ef", "ai": "ey ay", "api": "ey pi ay", "gpu": "ce pe u", "cpu": "se pe u", "ram": "ram",
}


def duzelt(metin: str) -> str:
    """Sözlükteki İngilizce kelimeleri Türkçe okunuşlarıyla değiştirir; emoji ve işaretleri temizler."""
    metin = re.sub(r"[*_`#>~]", "", metin)
    metin = re.sub(r"[\U0001F000-\U0001FFFF☀-➿️]", "", metin)
    return re.sub(r"[A-Za-zÇĞİÖŞÜçğıöşü\-]+", lambda m: SOZLUK.get(m.group(0).lower(), m.group(0)), metin)


def _yukle():
    global _ses
    if _ses is None:
        from piper import PiperVoice
        _ses = PiperVoice.load(MODEL)


def uret(metin: str) -> bytes:
    """Metni WAV bayt dizisi olarak üretir."""
    global _son
    metin = duzelt(metin).strip()
    if not metin:
        return b""
    with _kilit:
        _yukle()
        _son = time.time()
        tampon = io.BytesIO()
        with wave.open(tampon, "wb") as w:
            _ses.synthesize_wav(metin, w)
    return tampon.getvalue()


def _bosta_birak():
    global _ses
    while True:
        time.sleep(60)
        with _kilit:
            if _ses is not None and time.time() - _son > BOSTA_SN:
                _ses = None
                log("tts sesi bellekten birakildi (bosta)")


threading.Thread(target=_bosta_birak, daemon=True).start()
