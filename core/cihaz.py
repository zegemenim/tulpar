"""Hızlı yol: "sesi aç", "müziği durdur" gibi basit cihaz komutları yapay zekaya hiç gitmeden kural ile tanınır ve
anında uygulanır (saniyenin altında, model/RAM harcamaz). Tanınmayan her şey normal yoldan (Gemma) gider.
Cihazlar ~/tulpar/veri/cihazlar.json içinde: {"mac": {"adres": "http://100.x.y.z:8097", "anahtar": "..."}}.
Telefon komutları (ses, parlaklık, rahatsız etme) uygulamada çalışır: sunucu "eylem" olarak uygulamaya iletir."""
import json
import pathlib
import re
import urllib.request

from kuyruk import log

AYAR = pathlib.Path.home() / "tulpar/veri/cihazlar.json"
HEDEFLER = {"telefon": ("telefon", "telefonun", "telefonumun", "cebimin"), "mac": ("mac", "macbook", "bilgisayar", "bilgisayarın", "mac'in", "macin")}
SAYI = re.compile(r"(?:yüzde\s*)?%?\s*(\d{1,3})")

# (işlem, desen); sırası önemli: özel olan önce
KURALLAR = [
    ("medya_devam", re.compile(r"(?i)(en son çalın|kaldığı yerden|devam ettir|devam et|^(?:mac\w*\s+|telefon\w*\s+)?(?:bir\s+)?(müzi[ğg]i|muzigi|müzik|muzik|şarkıyı)\s*(çal|cal|aç|ac|başlat|baslat)$)")),
    ("medya_dur", re.compile(r"(?i)(müzi[ğg]i|muzigi|şarkıyı|sarkiyi|videoyu|medyayı)?\s*(durdur|duraklat|dur\b|sustur$)")),
    ("medya_sonraki", re.compile(r"(?i)(sonraki|sıradaki|siradaki|geç\b|atla)")),
    ("medya_onceki", re.compile(r"(?i)(önceki|onceki|geri al şarkı|bir önceki)")),
    ("sessiz", re.compile(r"(?i)(sesi|sesini)\s*(kapat|kıs sıfır|sessize al)|sessize al|sessiz(e)? (yap|al)|mute")),
    ("ses_ayar", re.compile(r"(?i)(sesi|sesini)\s*(%|yüzde)?\s*\d{1,3}\s*(yap|ayarla|getir|olsun)?")),
    ("parlaklik_ayar", re.compile(r"(?i)parlaklı[ğg]\w*\s*(%|yüzde)?\s*\d{1,3}\s*(yap|ayarla|getir|olsun)?")),
    ("ses_ac", re.compile(r"(?i)(sesi|sesini)\s*(aç|ac|yükselt|yukselt|arttır|arttir|artır|artir)")),
    ("ses_kis", re.compile(r"(?i)(sesi|sesini)\s*(kıs|kis|azalt|düşür|dusur)")),
    ("parlaklik_ac", re.compile(r"(?i)parlaklı[ğg]\w*\s*(aç|ac|arttır|arttir|artır|artir|yükselt|yukselt)")),
    ("parlaklik_kis", re.compile(r"(?i)parlaklı[ğg]\w*\s*(kıs|kis|azalt|düşür|dusur)")),
    ("rahatsiz_etme_ac", re.compile(r"(?i)rahatsız etme(yi)?\s*(aç|ac|başlat|baslat|devreye)|odak(\s*modu)?\s*(aç|ac)|sessiz mod(a)?\s*(geç|gec|aç|ac)")),
    ("rahatsiz_etme_kapat", re.compile(r"(?i)rahatsız etme(yi)?\s*(kapat|bitir|iptal)")),
]
SARKI = re.compile(r"(?i)^(.{3,60}?)\s+(?:çal|cal|oynat)$")
ETIKET = {"sarki_cal": "şarkı aranıp çalınıyor", "muzik_chrome": "müzik kaynağı Chrome", "muzik_sistem": "müzik kaynağı sistem", "medya_devam": "müzik devam ediyor", "medya_dur": "duraklatıldı", "medya_sonraki": "sonraki parça", "medya_onceki": "önceki parça",
          "medya_cal": "müzik başlatıldı", "sessiz": "ses kapatıldı", "ses_ayar": "ses ayarlandı", "parlaklik_ayar": "parlaklık ayarlandı", "ses_ac": "ses açıldı", "ses_kis": "ses kısıldı",
          "parlaklik_ac": "parlaklık artırıldı", "parlaklik_kis": "parlaklık azaltıldı",
          "rahatsiz_etme_ac": "rahatsız etme açıldı", "rahatsiz_etme_kapat": "rahatsız etme kapatıldı"}


def _hedef(metin):
    k = metin.lower()
    for ad, sozler in HEDEFLER.items():
        if any(re.search(rf"\b{re.escape(s)}\w*", k) for s in sozler):
            return ad
    return None


def tani(metin):
    """Metin basit bir cihaz komutuysa (islem, hedef, deger) döner; değilse None. Uzun/soru cümleleri hızlı yola girmez."""
    m = metin.strip()
    if len(m) > 70 or m.endswith("?") or len(m.split()) > 9:
        return None
    for islem, desen in KURALLAR:
        if desen.search(m):
            sayi = SAYI.search(m)
            return islem, _hedef(m), (min(int(sayi.group(1)), 100) if sayi and islem.startswith(("ses", "parlaklik")) and islem.endswith("ayar") else None)
    s = SARKI.match(m)
    if s:
        ad = re.sub(r"(?i)\b(şarkısını|sarkisini|parçasını|youtube music(?:te|ten)?|yt music(?:te|ten)?|mac(?:'?te|te)?|macbook(?:'?ta|ta)?|bilgisayar\w*|telefon\w*)\b", " ", s.group(1))
        ad = " ".join(ad.split())
        if ad and not re.match(r"(?i)(ses|parlakl|rahatsız|müzik|muzik|odak)", ad):
            return "sarki_cal", _hedef(m), ad
    return None


def _ajana_gonder(ad, islem, deger):
    try:
        ayar = json.loads(AYAR.read_text())[ad]
        istek = urllib.request.Request(ayar["adres"] + "/islem", data=json.dumps({"islem": islem, "deger": deger}).encode(),
                                       headers={"x-tulpar-anahtar": ayar["anahtar"]})
        with urllib.request.urlopen(istek, timeout=15) as y:
            return json.loads(y.read()).get("durum", "tamam")
    except (FileNotFoundError, KeyError):
        return None  # bu cihaz tanımlı değil
    except Exception as e:  # noqa: BLE001
        return f"hata: {type(e).__name__}"


def uygula(metin):
    """(cevap, eylem) döner; hızlı yola girmiyorsa None. Hedef telefonsa eylem uygulamaya iletilir, Mac ise ajana gider."""
    t = tani(metin)
    if not t:
        return None
    islem, hedef, deger = t
    hedef = hedef or "telefon"  # söylenmediyse konuştuğu cihaz (telefon)
    if hedef == "telefon":
        log(f"CİHAZ KOMUTU (hızlı yol) | telefon | {islem} {deger or ''}")
        komut("telefon", islem, deger)  # uygulamadaki servis sıradan alıp uygular (en geç 3 sn)
        return f"Tamam, {ETIKET[islem]}.", None
    sonuc = _ajana_gonder(hedef, islem, deger)
    log(f"CİHAZ KOMUTU (hızlı yol) | {hedef} | {islem} {deger or ''} | {sonuc}")
    if sonuc is None:
        return f"{hedef.capitalize()} henüz bağlı değil; cihaz ajanını kurmam gerekiyor.", None
    if sonuc.startswith("hata"):
        return f"{hedef.capitalize()} cevap vermedi ({sonuc}).", None
    if not sonuc.startswith(("tamam", "baslatildi", "zaten")):  # ajan işlemi yapamadıysa nedenini söyle
        return f"{hedef.capitalize()}: {sonuc}", None
    return f"Tamam, {hedef}: {ETIKET[islem]}.", {"tur": "cihaz", "hedef": hedef, "islem": islem, "deger": deger}


# ---- cihaz merkezi: herhangi bir cihaz (menü çubuğu, uygulama) herhangi bir cihazı HP üzerinden kontrol eder ----
_bekleyen = {"telefon": []}  # telefon uygulaması /cihaz/bekleyen ile alıp çalıştırır (APK'da yerel modül gerekir)


def liste():
    try:
        tanimli = list(json.loads(AYAR.read_text()))
    except FileNotFoundError:
        tanimli = []
    return sorted(set(tanimli) | set(_bekleyen))


def komut(hedef, islem, deger=None):
    """Seçilen cihazda işlemi çalıştırır; telefon için sıraya koyar. Metin sonuç döner."""
    if hedef in _bekleyen:
        _bekleyen[hedef] = (_bekleyen[hedef] + [{"islem": islem, "deger": deger}])[-20:]
        return "telefona iletildi"
    sonuc = _ajana_gonder(hedef, islem, deger)
    return f"{hedef} bağlı değil" if sonuc is None else sonuc


def bekleyen(hedef):
    cikan, _bekleyen[hedef] = _bekleyen.get(hedef, []), []
    return cikan
