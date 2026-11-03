"""Tarayıcı ajanı (1. aşama): bir soruyu web'de araştırır, birkaç sayfayı okur, kaynaklarıyla özetler.
Sadece okur: indirme, form doldurma, giriş yok. Aynı anda tek tarayıcı çalışır (HP'nin RAM'i modelle paylaşılıyor),
iş bitince kapanır. Görseller/fontlar yüklenmez. Arama Ecosia'dan (yedek Bing): Google, Brave, Yandex ve Mojeek başsız
tarayıcıya CAPTCHA çıkarıyor; Bing ise sorgunun çoğunu yok sayıp alakasız sonuç veriyor."""
import json
import os
import pathlib
import re
import subprocess
import threading
import time
import urllib.request
from urllib.parse import urlencode, urlparse

import ayarlar
from kuyruk import log

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
SAYFA_SAYISI = 3          # okunacak sayfa
SAYFA_KARAKTER = 2500     # sayfa başına modele giden metin (bu işlemcide okuma yavaş: ~20 kelime/sn)
BOT_IZI = ("captcha", "robot olmadığınızı", "i'm not a robot", "unusual traffic", "olağandışı trafik", "verify you are human")
_kilit = threading.Lock()
# (ad, adres, sonuç bağlantısı seçicisi)
ARAMA = [
    ("ecosia", "https://www.ecosia.org/search?{}", "q", "a.result__link"),
    ("bing", "https://www.bing.com/search?{}&setlang=tr", "q", "li.b_algo h2 a"),
]


class BotKorumasi(Exception):
    """Arama sitesi bot koruması (CAPTCHA) çıkardı."""


def _bot_mu(sayfa):
    try:
        metin = (sayfa.title() + " " + sayfa.inner_text("body")[:3000]).lower()
    except Exception:
        return False
    return any(i in metin for i in BOT_IZI)


def _ilgili(metin, soru, sinir=SAYFA_KARAKTER):
    """Sayfanın soruyla en ilgili parçalarını (sıralarını koruyarak) seçer: menü, reklam, alt bilgi elenir."""
    kelimeler = {k for k in re.findall(r"\w{3,}", soru.lower())}
    parcalar = [p.strip() for p in re.split(r"\n+|(?<=[.!?])\s+", metin) if len(p.strip()) > 40]
    puanli = sorted(range(len(parcalar)), key=lambda i: -len(kelimeler & set(re.findall(r"\w{3,}", parcalar[i].lower()))))
    secilen, uzunluk = set(), 0
    for i in puanli:
        if uzunluk + len(parcalar[i]) > sinir:
            continue
        secilen.add(i)
        uzunluk += len(parcalar[i])
    return " ".join(parcalar[i] for i in sorted(secilen))


PI_AYAR = pathlib.Path.home() / "tulpar/veri/pi-arastir.json"  # {"adres": "http://192.168.1.2:8096", "anahtar": "..."}; yoksa HP'de yapılır


def ara(soru, n=SAYFA_SAYISI, bildir=None):
    """Ayar açıksa önce HP'deki görünür tarayıcıda (telefondan izlenir, CAPTCHA'yı sahibi çözer); olmazsa Raspberry Pi'deki tarayıcı servisine sorar (HP'nin RAM'i modele kalır); ulaşılamazsa HP'de kendisi yapar.
    BotKorumasi Pi'den gelirse aynen yükseltilir. Döner: [{baslik, url, metin}]."""
    if ayarlar.al("arastirma_gorunur"):
        try:
            return gorunur_ara(soru, n, bildir)
        except BotKorumasi:
            raise
        except Exception as e:  # noqa: BLE001
            log(f"gorunur tarayici kullanilamadi, Pi/baslisiz yola geciliyor ({type(e).__name__}: {e})")
    try:
        ayar = json.loads(PI_AYAR.read_text())
        istek = urllib.request.Request(ayar["adres"] + "/ara", data=json.dumps({"soru": soru, "n": n}).encode(),
                                       headers={"x-tulpar-anahtar": ayar["anahtar"]})
        with urllib.request.urlopen(istek, timeout=240) as y:
            govde = json.loads(y.read())
        if govde.get("bot"):
            raise BotKorumasi(govde["bot"])
        return govde["sayfalar"]
    except BotKorumasi:
        raise
    except Exception as e:  # noqa: BLE001  (dosya yok, Pi kapalı, zaman aşımı)
        log(f"arastirma Pi'de yapilamadi, HP'de yapiliyor ({type(e).__name__})")
    return yerel_ara(soru, n)


def _sayfalari_oku(ortam, soru, n, bot_bekle=None):
    """Arama yapar, ilk sonuçlardan okunabilen n sayfayı döndürür. bot_bekle(sayfa) -> True: bot koruması sahibi tarafından aşıldı
    (görünür tarayıcıda telefondan çözülür); yoksa ya da aşılmazsa o site atlanır."""
    sayfa = ortam.new_page()
    sonuclar, engelleyen = [], []
    for ad, adres, alan, secici in ARAMA:
        try:
            sayfa.goto(adres.format(urlencode({alan: soru})), timeout=25000)
            sayfa.wait_for_timeout(1500)
        except Exception as e:
            log(f"arama acilmadi: {ad} ({type(e).__name__})")
            continue
        if _bot_mu(sayfa) and not (bot_bekle and bot_bekle(sayfa)):
            engelleyen.append(ad)
            continue
        sonuclar = [(a.inner_text().strip(), a.get_attribute("href")) for a in sayfa.query_selector_all(secici)]
        if sonuclar:
            break
    if not sonuclar and engelleyen:
        raise BotKorumasi(", ".join(engelleyen))
    okunan = []
    for baslik, adres in sonuclar:
        if len(okunan) >= n:
            break
        if not adres or not adres.startswith("http"):
            continue
        s = None
        try:
            s = ortam.new_page()
            s.goto(adres, timeout=20000, wait_until="domcontentloaded")
            s.wait_for_timeout(800)
            if _bot_mu(s) and not (bot_bekle and bot_bekle(s)):
                continue
            metin = _ilgili(s.inner_text("body"), soru)
            if len(metin) > 300:
                okunan.append({"baslik": baslik, "url": s.url, "metin": metin})
        except Exception as e:  # zaman aşımı, PDF (indirme kapalı) vb.: o sayfayı atla
            log(f"arastirma sayfa atlandi: {adres[:80]} ({type(e).__name__})")
        finally:
            if s:
                s.close()
    sayfa.close()
    return okunan


def yerel_ara(soru, n=SAYFA_SAYISI):
    """Soruyu bu makinede başsız tarayıcıyla arar: [{baslik, url, metin}]."""
    from playwright.sync_api import sync_playwright
    with _kilit, sync_playwright() as p:
        tarayici = p.chromium.launch(args=["--disable-dev-shm-usage"], executable_path=os.environ.get("TULPAR_CHROMIUM") or None)
        try:
            ortam = tarayici.new_context(user_agent=UA, locale="tr-TR", accept_downloads=False)
            ortam.route("**/*", lambda r: r.abort() if r.request.resource_type in ("image", "media", "font") else r.continue_())
            return _sayfalari_oku(ortam, soru, n)
        finally:
            tarayici.close()


CDP = "http://127.0.0.1:9222"
BOT_BEKLE_SN = 300  # sahibi telefondan çözsün diye en çok bu kadar beklenir


def _servis(islem):
    return subprocess.run(["sudo", "-n", "systemctl", islem, "tulpar-tarayici.service"], capture_output=True, timeout=60).returncode == 0


def gorunur_ara(soru, n=SAYFA_SAYISI, bildir=None):
    """Araştırmayı HP'deki görünür Chromium'da yapar (telefondaki Ekran sayfasından izlenir). Bot koruması çıkarsa `bildir(mesaj)` ile
    sahibine haber verilir ve sayfa çözülene kadar (BOT_BEKLE_SN) beklenir. Servis kapalıysa açılır, iş bitince kapatılır.
    Açılamazsa RuntimeError (çağıran Pi/başsız yola düşer)."""
    from playwright.sync_api import sync_playwright
    with _kilit:
        if not _servis("start"):
            raise RuntimeError("görünür tarayıcı servisi başlamadı")
        try:
            for _ in range(30):
                try:
                    urllib.request.urlopen(CDP + "/json/version", timeout=2)
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(1)
            else:
                raise RuntimeError("görünür tarayıcıya bağlanılamadı")
            with sync_playwright() as p:
                tarayici = p.chromium.connect_over_cdp(CDP)
                ortam = tarayici.contexts[0]

                def bekle(sayfa):
                    if bildir:
                        bildir("Arama sitesi bot koruması (CAPTCHA) çıkardı. Uygulamada Bilgisayar sekmesindeki Ekran'ı açıp çözer misin? "
                               f"{BOT_BEKLE_SN // 60} dakika bekleyeceğim.")
                    bitis = time.time() + BOT_BEKLE_SN
                    while time.time() < bitis:
                        sayfa.wait_for_timeout(4000)
                        if not _bot_mu(sayfa):
                            return True
                    return False
                try:
                    return _sayfalari_oku(ortam, soru, n, bekle)
                finally:
                    for sayfa in ortam.pages:  # sonraki oturum temiz başlasın
                        try:
                            sayfa.close()
                        except Exception:  # noqa: BLE001
                            pass
        finally:
            _servis("stop")


OZET_SISTEM = (
    "Sen Tulpar'sın. Sahibin bir soru sordu, sen de web'de birkaç sayfa okudun. SADECE aşağıdaki sayfalardaki bilgilere "
    "dayanarak Türkçe, kısa ve net cevap ver (en fazla 5-6 cümle). Bilgi sayfalarda yoksa veya çelişiyorsa bunu açıkça söyle; "
    "uydurma. Hangi bilginin hangi kaynaktan geldiğini [1], [2] gibi numarayla belirt. Liste ve emoji kullanma."
)


def ozetle(soru, sayfalar, model_sor):
    """model_sor(sistem, metin) -> cevap. Cevabın altına kaynak listesi eklenir."""
    icerik = "\n\n".join(f"[{i}] {s['baslik']} ({urlparse(s['url']).netloc})\n{s['metin']}" for i, s in enumerate(sayfalar, 1))
    cevap = (model_sor(OZET_SISTEM, f"Soru: {soru}\n\nSayfalar:\n{icerik}") or "").strip()
    if not cevap:
        return ""
    return cevap + "\n\nKaynaklar:\n" + "\n".join(f"[{i}] {s['baslik']} - {s['url']}" for i, s in enumerate(sayfalar, 1))
