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
        time.sleep(30)
        with _kilit:
            if _model is not None and time.time() - _son_kullanim > ayarlar.al("whisper_bosta_sn"):  # Gemma ile 16 GB'a sığmıyor
                _model = None
                import gc
                gc.collect()
                log("whisper bellekten birakildi (bosta)")


threading.Thread(target=_bosta_birak, daemon=True).start()


def yaziya_dok(dosya):
    with _kilit:  # aynı anda tek döküm: işlemciyi modellerle paylaşıyoruz
        _yukle()
        t0 = time.time()
        # Türkçe ağırlıklı ama arada İngilizce terim geçen konuşma: dili Türkçe sabitle, ipucuyla İngilizce
        # kelimeleri olduğu gibi yazmaya yönlendir ("deploy" -> "diplay" olmasın)
        global _son_kullanim
        _son_kullanim = time.time()
        parcalar, bilgi = _model.transcribe(_coz(dosya), language="tr", vad_filter=True, initial_prompt=IPUCU)
        metin = " ".join(p.text.strip() for p in parcalar).strip()
    log(f"sesli mesaj yaziya dokuldu: {bilgi.duration:.0f} sn ses, {time.time() - t0:.0f} sn surdu")
    return metin
