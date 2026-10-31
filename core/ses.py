"""Sesli mesajları HP'de yazıya döker (faster-whisper large-v3-turbo). Ses dosyası işlenince silinir."""
import pathlib
import subprocess
import threading
import time

import numpy as np

import ayarlar
from kuyruk import log

MODEL_YOL = pathlib.Path.home() / "tulpar/models/whisper"
_model = None
IPUCU = ("Türkçe konuşma; arada İngilizce terimler geçebilir: deploy, commit, push, server, model, prompt, "
         "update, meeting, deadline, feedback, link, story, app, Tulpar.")
_kilit = threading.Lock()


_ipucu_onbellek = (0.0, "")


def kisisel_ipucu():
    """Whisper'a her seferinde verilen ipucu: sahibinin sık yazıştığı kişilerin adları ve hafızadaki özel kelimeler.
    Böylece 'Kerem', 'Burak', 'Ayşe Hanım' gibi adlar ve karışık İngilizce terimler daha doğru yazılır. 10 dk önbelleklenir."""
    global _ipucu_onbellek
    if time.time() - _ipucu_onbellek[0] < 600:
        return _ipucu_onbellek[1]
    try:
        import db
        adlar = []
        for r in db.oku("""SELECT gonderen_adi ad, COUNT(*) n FROM mesajlar WHERE benden=0 AND grup=0 AND gonderen_adi IS NOT NULL
                           GROUP BY gonderen_adi ORDER BY n DESC LIMIT 60"""):
            ilk = (r["ad"] or "").split()[0] if r["ad"] else ""
            if ilk.isalpha() and 3 <= len(ilk) <= 14 and ilk not in adlar:
                adlar.append(ilk)
        hafiza = [b["bilgi"] for b in db.oku("SELECT bilgi FROM hafiza WHERE guven='kesin' ORDER BY guncel DESC LIMIT 6")]
        metin = IPUCU + " Kişiler: " + ", ".join(adlar[:30]) + "." + ((" " + " ".join(hafiza)) if hafiza else "")
    except Exception:
        metin = IPUCU
    _ipucu_onbellek = (time.time(), metin[:700])
    return _ipucu_onbellek[1]


def _coz(dosya):
    """Her türlü ses dosyasını (ogg/opus, m4a, wav) ffmpeg ile 16 kHz mono'ya çözer.
    faster-whisper'ın kendi çözücüsü yeni PyAV sürümleriyle uyumsuz olduğu için bunu kullanıyoruz."""
    ham = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", str(dosya), "-f", "s16le", "-ac", "1",
                          "-ar", "16000", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(ham, np.int16).astype(np.float32) / 32768.0


def _yukle():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=4,
                              download_root=str(MODEL_YOL))


_son_kullanim = 0.0


def _bosta_birak():
    global _model
    while True:
        time.sleep(2)
        with _kilit:
            if _model is not None and time.time() - _son_kullanim > ayarlar.al("whisper_bosta_sn"):  # Gemma ile 16 GB'a sığmıyor
                _model = None
                import gc
                gc.collect()
                log("whisper bellekten birakildi (bosta)")


threading.Thread(target=_bosta_birak, daemon=True).start()


def hazirla():
    """Mikrofona basılınca çağrılır: Whisper'ı arka planda belleğe al ve bellekte tut. Yükleme bitince ve her
    çağrıda 'bosta' sayacı yeniden başlar (kayıt uzun sürerse uygulama birkaç sn'de bir tekrar çağırır)."""
    global _son_kullanim
    _son_kullanim = time.time()
    if _model is not None:
        return

    def yukle():
        global _son_kullanim
        with _kilit:
            _yukle()
            _son_kullanim = time.time()
        log("whisper mikrofon basilinca yuklendi")
    threading.Thread(target=yukle, daemon=True).start()


def yaziya_dok(dosya):
    with _kilit:  # aynı anda tek döküm: işlemciyi modellerle paylaşıyoruz
        _yukle()
        t0 = time.time()
        # Türkçe ağırlıklı ama arada İngilizce terim geçen konuşma: dili Türkçe sabitle, ipucuyla İngilizce
        # kelimeleri olduğu gibi yazmaya yönlendir ("deploy" -> "diplay" olmasın)
        global _son_kullanim
        _son_kullanim = time.time()
        parcalar, bilgi = _model.transcribe(_coz(dosya), language="tr", vad_filter=True, initial_prompt=kisisel_ipucu())
        metin = " ".join(p.text.strip() for p in parcalar).strip()
        _son_kullanim = time.time()  # bosta sayacı dökümün BİTTİĞİ andan başlar
    log(f"sesli mesaj yaziya dokuldu: {bilgi.duration:.0f} sn ses, {time.time() - t0:.0f} sn surdu")
    return metin
