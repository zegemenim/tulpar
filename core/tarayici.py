"""Tarayıcı ajanı (1. aşama): bir soruyu web'de araştırır, birkaç sayfayı okur, kaynaklarıyla özetler.
Sadece okur: indirme, form doldurma, giriş yok. Aynı anda tek tarayıcı çalışır (HP'nin RAM'i modelle paylaşılıyor),
iş bitince kapanır. Görseller/fontlar yüklenmez. Arama Ecosia'dan (yedek Bing): Google, Brave, Yandex ve Mojeek başsız
tarayıcıya CAPTCHA çıkarıyor; Bing ise sorgunun çoğunu yok sayıp alakasız sonuç veriyor."""
import re
import threading
from urllib.parse import urlencode, urlparse

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


def ara(soru, n=SAYFA_SAYISI):
    """Soruyu arar, ilk sonuçlardan okunabilen n sayfayı döndürür: [{baslik, url, metin}]."""
    from playwright.sync_api import sync_playwright
    with _kilit, sync_playwright() as p:
        tarayici = p.chromium.launch(args=["--disable-dev-shm-usage"])
        try:
            ortam = tarayici.new_context(user_agent=UA, locale="tr-TR", accept_downloads=False)
            ortam.route("**/*", lambda r: r.abort() if r.request.resource_type in ("image", "media", "font") else r.continue_())
            sayfa = ortam.new_page()
            sonuclar, engelleyen = [], []
            for ad, adres, alan, secici in ARAMA:
                try:
                    sayfa.goto(adres.format(urlencode({alan: soru})), timeout=25000)
                    sayfa.wait_for_timeout(1500)
                except Exception as e:
                    log(f"arama acilmadi: {ad} ({type(e).__name__})")
                    continue
                if _bot_mu(sayfa):
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
                    if _bot_mu(s):
                        continue
                    metin = _ilgili(s.inner_text("body"), soru)
                    if len(metin) > 300:
                        okunan.append({"baslik": baslik, "url": s.url, "metin": metin})
                except Exception as e:  # zaman aşımı, PDF (indirme kapalı) vb.: o sayfayı atla
                    log(f"arastirma sayfa atlandi: {adres[:80]} ({type(e).__name__})")
                finally:
                    if s:
                        s.close()
            return okunan
        finally:
            tarayici.close()


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
