"""Tulpar iş kuyruğu ve yönlendirici.

İki şerit var:
  hızlı şerit  -> 9B: mesaj elemesi, sesli komutlar, acil işler. Hep açık.
  büyük şerit  -> Gemma (taslak, özet) veya gpt-oss (özenli mod). İhtiyaç olunca açılır,
                  boş kalınca kapanır. Acil bir iş gelirse o anki iş kesilir, acil iş
                  bitince baştan yeniden yapılır.
"""
import itertools
import queue
import syslog
import threading
import time
from dataclasses import dataclass, field

import llm

ONCELIK = {"acil": 0, "normal": 1, "arka": 2}

# iş türü -> (model, varsayılan öncelik)
# Gerçek mesaj testinde Gemma 9B'den hem daha doğru hem ~2 kat hızlı çıktı ve iki model birlikte RAM'e
# sığmıyordu; bu yüzden "hizli" servisi artık Gemma'yı çalıştırıyor ve günlük işlerin hepsi onda.
YONLENDIRME = {
    "eleme": ("hizli", "normal"),     # gelen her mesaj/bildirimin ilk değerlendirmesi
    "komut": ("hizli", "acil"),       # "hemen bak", sesli istek
    "taslak": ("hizli", "normal"),    # cevap taslağı
    "ozet": ("hizli", "arka"),        # grup / gün özeti
    "ozenli": ("ozenli", "arka"),     # önemli ve acelesiz iş (gpt-oss)
}
BUYUK_BOSTA_KAPAT_SN = 15 * 60
# Telefonun bağlantısı koparsa konuşma üreteci kapanmayıp "canlı" kaydını bırakmayabiliyor; bu kayıt bütün
# arka plan işlerini sonsuza kadar bekletiyordu. Bundan eski canlı kayıtlar sayılmaz.
CANLI_EN_FAZLA_SN = 600  # bu işlemcide uzun bir cevap birkaç dakika sürebiliyor

SEVIYE_SISTEM = ("Bir işin ne kadar düşünme gerektirdiğine karar ver. low = basit, kısa; medium = birkaç adımlı; "
                 "high = önemli, riskli veya çok adımlı (sözleşme, önemli mail, plan). "
                 'SADECE JSON: {"seviye": "low|medium|high"}')


def log(mesaj):
    syslog.openlog("tulpar")
    syslog.syslog(mesaj)


_sira = itertools.count()


@dataclass(order=True)
class Is:
    sira_anahtari: tuple = field(init=False, repr=False)
    tur: str = field(compare=False)
    sistem: str = field(compare=False)
    kullanici: str = field(compare=False)
    oncelik: str = field(default="", compare=False)
    dusunme: str = field(default=None, compare=False)
    json_cevap: bool = field(default=True, compare=False)
    sonuc: object = field(default=None, compare=False)
    hata: str = field(default=None, compare=False)
    kesilme: int = field(default=0, compare=False)
    bitti: threading.Event = field(default_factory=threading.Event, compare=False)

    def __post_init__(self):
        self.model = YONLENDIRME[self.tur][0]
        self.oncelik = self.oncelik or YONLENDIRME[self.tur][1]
        self.sira_anahtari = (ONCELIK[self.oncelik], next(_sira))

    def bekle(self, zaman_asimi=None):
        self.bitti.wait(zaman_asimi)
        return self.sonuc


class Kuyruk:
    def __init__(self):
        self.hizli = queue.PriorityQueue()
        self.buyuk = queue.PriorityQueue()
        self.acil_sayisi = 0
        self.canli_kayit = {}  # canlı konuşma -> başlangıç zamanı
        self.kilit = threading.Lock()
        self.acil_var = threading.Event()   # set iken büyük şerit durur
        self.son_buyuk = time.time()
        self.acik_buyuk = None
        for hedef in (self._hizli_isci, self._buyuk_isci, self._bosta_kapatici):
            threading.Thread(target=hedef, daemon=True).start()

    def ekle(self, is_):
        if is_.oncelik == "acil":
            with self.kilit:
                self.acil_sayisi += 1
                self.acil_var.set()
        (self.hizli if is_.model == "hizli" else self.buyuk).put(is_)
        log(f"is eklendi: {is_.tur} ({is_.oncelik}) -> {is_.model}")
        return is_

    def _acil_bitti(self):
        with self.kilit:
            self.acil_sayisi -= 1
            if self.acil_sayisi == 0:
                self.acil_var.clear()

    def _calistir(self, is_, durdur=None):
        t0 = time.time()
        is_.sonuc = llm.sor(is_.model, is_.sistem, is_.kullanici, is_.json_cevap, is_.dusunme, durdur)
        log(f"is bitti: {is_.tur} {is_.model} ({time.time() - t0:.0f} sn)")

    def canli(self):
        """Sahibiyle anlık sesli/yazılı konuşma sürerken arka plan işleri yeni iş almaz (işlemci ona kalsın)."""
        kuyruk = self

        class _Canli:
            def __enter__(self):
                with kuyruk.kilit:
                    kuyruk.canli_kayit[id(self)] = time.time()

            def __exit__(self, *_):
                with kuyruk.kilit:
                    kuyruk.canli_kayit.pop(id(self), None)
        return _Canli()

    def _canli_var(self):
        sinir = time.time() - CANLI_EN_FAZLA_SN
        with self.kilit:
            for k, t in list(self.canli_kayit.items()):
                if t < sinir:
                    del self.canli_kayit[k]
                    log("canli konusma kaydi zaman asimina ugradi (baglanti kopmus olabilir), temizlendi")
            return bool(self.canli_kayit)

    def _hizli_isci(self):
        while True:
            is_ = self.hizli.get()
            while is_.oncelik != "acil" and self._canli_var():  # canlı konuşma bitene kadar bekle
                time.sleep(0.3)
            try:
                self._calistir(is_)
            except Exception as e:
                is_.hata = str(e)
                log(f"HATA is: {is_.tur}: {e}")
            finally:
                is_.bitti.set()
                if is_.oncelik == "acil":
                    self._acil_bitti()

    def _seviye_sec(self, is_):
        """Özenli işte düşünme seviyesini işe başlamadan hızlı model seçer."""
        if is_.model != "ozenli" or is_.dusunme:
            return
        try:
            cevap = llm.sor("hizli", SEVIYE_SISTEM, is_.kullanici[:3000])
            is_.dusunme = cevap.get("seviye") if cevap.get("seviye") in ("low", "medium", "high") else "medium"
        except Exception:
            is_.dusunme = "medium"
        log(f"ozenli is dusunme seviyesi: {is_.dusunme}")

    def _buyuk_isci(self):
        while True:
            is_ = self.buyuk.get()
            while self.acil_var.is_set():      # acil iş varken büyük model hiç başlamaz
                time.sleep(0.5)
            try:
                self._seviye_sec(is_)
                if self.acik_buyuk and self.acik_buyuk != is_.model:
                    llm.kapat(self.acik_buyuk)  # Gemma ile gpt-oss aynı anda RAM'e sığmaz
                llm.ac(is_.model)
                self.acik_buyuk = is_.model
                self._calistir(is_, durdur=self.acil_var)
                is_.bitti.set()
            except llm.Iptal:
                is_.kesilme += 1
                log(f"is kesildi (acil is geldi): {is_.tur}, sonra yeniden yapilacak")
                self.buyuk.put(is_)            # aynı sıra anahtarı: kuyruğun başına döner
            except Exception as e:
                is_.hata = str(e)
                log(f"HATA is: {is_.tur}: {e}")
                is_.bitti.set()
            finally:
                self.son_buyuk = time.time()

    def _bosta_kapatici(self):
        while True:
            time.sleep(30)
            if self.acik_buyuk and self.buyuk.empty() and time.time() - self.son_buyuk > BUYUK_BOSTA_KAPAT_SN:
                log(f"buyuk model bosta, kapatiliyor: {self.acik_buyuk}")
                llm.kapat(self.acik_buyuk)
                self.acik_buyuk = None
