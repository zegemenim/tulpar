"""Tulpar kural katmanı: modelden önce ve sonra çalışan, kodla yazılmış kurallar.

Model ne derse desin, buradaki güvenlik kuralları son sözü söyler. Kurallar mesajı
gizleyemez veya önemini düşüremez; sadece yükseltebilir (güvenlik) ya da
başkasına verilen görevi sahibin görevi olmaktan çıkarabilir (hitap).
"""
import re
import unicodedata

import sahip

SAHIP_ADLARI = sahip.ADLAR
ASISTAN_ADLARI = ["tulpar", "kahya", "kâhya"]


def sade(metin):
    """Küçük harf, Türkçe karakterleri ASCII'ye indir: 'Kâhya ŞİFRE' -> 'kahya sifre'."""
    m = metin.replace("İ", "i").replace("I", "ı").lower()
    m = m.translate(str.maketrans("çğıöşüâî", "cgiosuai"))
    return unicodedata.normalize("NFKD", m)


# --- Güvenlik kuralları: (ad, açıklama, eşleşme fonksiyonu) ---

def _asistana_talimat(s):
    if not any(re.search(rf"\b{a}\b", s) for a in ASISTAN_ADLARI):
        return False
    return bool(re.search(r"(talimat|unut|isaretle|gosterme|gizle|sil|gonder|ilet|onemsiz|yoksay|okuyorsan)", s))


def _para_istegi(s):
    iban = re.search(r"\b(iban|tr\d{2}[\d ]{10,})", s)
    tutar = re.search(r"\d[\d.,]*\s*(tl|lira|₺)|para", s)
    istek = re.search(r"(lazim|gonder|atar misin|at\b|yolla|borc|acil|geri veririm)", s)
    return bool(iban and (tutar or istek)) or bool(tutar and istek and re.search(r"(acil|kimseye soyleme|geri veririm)", s))


def _kod_istegi(s):
    otp = re.search(r"(\d\s*haneli|dogrulama|onay|sms|whatsapp)\s*(bi\s*|bir\s*)?kod|kod\s*(geldi|gitti)|yanlislikla.*kod", s)
    return bool(otp) and bool(re.search(r"(atar misin|gonder|ilet|soyler misin|yolla|at\b|okur musun)", s))


def _sifre_istegi(s):
    return bool(re.search(r"(sifre|parola|password|\.env|api key|token|root)", s)) and bool(
        re.search(r"(ilet|gonder|at\b|atar|yolla|paylas|ver\b)", s))


SUPHELI_UZANTI = r"\.(xyz|top|click|info|live|online|site|icu|buzz|shop)\b"


def _supheli_link(s):
    if re.search(r"(bit\.ly|tinyurl|t\.co/|cutt\.ly)", s):
        return True
    if re.search(SUPHELI_UZANTI, s):
        return True
    # kurum adı + tire ile uydurulmuş alan adı: ptt-kargo-..., ziraat-guvenlik-tr.com
    return bool(re.search(r"\b(ptt|kargo|ziraat|garanti|akbank|isbank|yapikredi|edevlet|turkiye)[a-z]*-[a-z-]+\.(com|net|org)", s))


GUVENLIK = [
    ("asistana_talimat", "Mesaj Tulpar'a talimat vermeye çalışıyor; talimat uygulanmadı, mesaj sana gösteriliyor.", _asistana_talimat),
    ("para_istegi", "Para veya IBAN isteniyor; hesap ele geçirilmiş olabilir, kişiyi telefonla arayıp doğrula.", _para_istegi),
    ("kod_istegi", "Doğrulama kodu isteniyor; WhatsApp hesabı çalma yöntemi, kodu kimseye verme.", _kod_istegi),
    ("sifre_istegi", "Şifre veya gizli bilgi isteniyor; kimseyle paylaşma.", _sifre_istegi),
    ("supheli_link", "Şüpheli bağlantı var; tıklama.", _supheli_link),
]


def guvenlik_kontrol(metin):
    s = sade(metin)
    return [(ad, aciklama) for ad, aciklama, f in GUVENLIK if f(s)]


# --- Hitap kuralı: grup mesajı sahibe mi söylendi? ---

TOPLU = r"\b(arkadaslar|herkes|millet|ekip|gencler|cocuklar|hepiniz|herkesin)\b"


def kime(metin, grup):
    """'sahip' | 'herkes' | 'baskasi' | 'belirsiz'"""
    s = sade(metin)
    if re.search(r"@\s*(" + "|".join(SAHIP_ADLARI) + r")\b", s) or any(re.search(rf"\b{a}", s) for a in SAHIP_ADLARI):
        return "sahip"
    if not grup:
        return "sahip"
    if re.search(TOPLU, s):
        return "herkes"
    # "Ahmet sen ...", "Ahmet, ...", "@Ahmet": başka birine hitap
    if re.match(r"\s*@?\s*[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(\s*,|\s+sen\b|\s+siz\b)", metin) or re.match(r"\s*@\S+", metin):
        return "baskasi"
    return "belirsiz"


SAHIBE_OZEL = {"claude_gorev", "cevap_taslagi"}


def uygula(sonuc, metin, grup):
    """Model çıktısını kurallarla düzelt. sonuc: triage JSON'u (dict). Değişiklikleri 'kural_notlari'na yazar."""
    sonuc = dict(sonuc or {})
    notlar = []
    uyarilar = guvenlik_kontrol(metin)
    if uyarilar:
        sonuc.update(onem="yuksek", tur="supheli", aksiyon="uyar")
        notlar += [a for _, a in uyarilar]
        sonuc["guvenlik"] = [ad for ad, _ in uyarilar]
    hedef = kime(metin, grup)
    sonuc["kime"] = hedef
    if hedef == "baskasi" and sonuc.get("aksiyon") in SAHIBE_OZEL:
        sonuc.update(aksiyon="yok", onem="dusuk")
        notlar.append("Görev başka birine verilmiş; sadece özete bilgi olarak girer.")
    if notlar:
        sonuc["kural_notlari"] = notlar
    return sonuc
