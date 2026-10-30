"""Sesli mesajları HP'de yazıya döker (faster-whisper large-v3-turbo). Ses dosyası işlenince silinir."""
import pathlib
import threading
import time

from kuyruk import log

MODEL_YOL = pathlib.Path.home() / "tulpar/models/whisper"
_model = None
IPUCU = ("Türkçe konuşma; arada İngilizce terimler geçebilir: deploy, commit, push, server, model, prompt, "
         "update, meeting, deadline, feedback, link, story, app, Tulpar.")
_kilit = threading.Lock()


def yaziya_dok(dosya):
    global _model
    with _kilit:  # aynı anda tek döküm: işlemciyi modellerle paylaşıyoruz
        if _model is None:
            from faster_whisper import WhisperModel
            _model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8", cpu_threads=4,
                                  download_root=str(MODEL_YOL))
        t0 = time.time()
        # Türkçe ağırlıklı ama arada İngilizce terim geçen konuşma: dili Türkçe sabitle, ipucuyla İngilizce
        # kelimeleri olduğu gibi yazmaya yönlendir ("deploy" -> "diplay" olmasın)
        parcalar, bilgi = _model.transcribe(str(dosya), language="tr", vad_filter=True, initial_prompt=IPUCU)
        metin = " ".join(p.text.strip() for p in parcalar).strip()
    log(f"sesli mesaj yaziya dokuldu: {bilgi.duration:.0f} sn ses, {time.time() - t0:.0f} sn surdu")
    return metin
