"""Cevap taslağı: kişi kartı + sahibin o kişiye/benzerlerine yazdıkları + son konuşma -> Gemma."""
import json
import re
import time

import ayarlar
import db
import sahip
from kuyruk import Is

YER_TUTUCU = re.compile(r"\[[^\]]{2,30}\]")  # [fotoğraf], [çıkartma] ...
SAMIMI = ["kanka", "knk", "kral", "lan", "abi", "moruk", "kardeşim", "kanki", "reis"]
SAMIMI_YASAK_ILISKI = {"aile", "hoca", "resmi", "is"}

KART_SISTEM = sahip.doldur(
    "Bir WhatsApp kişisinin sahibiyle ({SAHIP}) ilişkisini tahmin et. Mesajlara ve hitaplara bak "
    "(\"oğlum\" -> aile, \"hocam\"/akademik unvan -> hoca, \"X Bey/Hanım\", kurum adı -> resmi veya is, "
    "\"kanka/knk\" -> arkadas). Emin değilsen bilinmiyor de. "
    'SADECE JSON: {"iliski": "aile|yakin|arkadas|hoca|ogrenci|resmi|is|bilinmiyor", '
    '"hitap": "SAHİBİN bu kişiye hitabı (örn. anne, Ayşe Hanım, hocam, kanka) veya null", "sen_siz": "sen|siz"}'
)

TASLAK_SISTEM = sahip.doldur(
    "Sen Tulpar'sın. {SAHIP_TAM} adına WhatsApp cevabı TASLAĞI hazırlıyorsun (gönderilmeyecek, onaya sunulacak).\n"
    "Kişi kartı ve sahibinin gerçek mesaj örnekleri aşağıda; üslubu, harf kullanımını ve hitabı ÖRNEKLERE benzet.\n"
    "Kurallar: aileye, hocalara ve resmi kişilere asla 'kanka/knk/kral/abi/lan' yok; resmi kişilere 'siz' ve düzgün yazım. "
    "İlk kez yazan kişide karşı tarafın hitabına uy; emin değilsen nötr ve kibar yaz.\n"
    "sahibinin kararını bilmediğin şeyleri (gelir mi, getirir mi, ne zaman müsait, yaptı mı) ASLA kendin seçme. "
    "Cevap sahibinin bir kararına bağlıysa, her olası karar için ayrı bir SEÇENEK hazırla (örn. 'Gelirim' / 'Gelemem'; "
    "iki karar varsa birleşimleri: 'Gelirim, topum var' / 'Gelirim, topum yok' / 'Gelemem'). En fazla 4 seçenek. "
    "Cevap sahibinin bildiği bir bilgiye bağlıysa (örn. 'bugün son tarihli ödev var mı?'), her olası cevap için seçenek yaz "
    "('Yok', 'Var: [hangisi]', 'Bilmiyorum'); etiket sahibine soruyu açıkça sorsun. "
    "Bir tarih/saat gibi seçeneklenemeyen bilgi gerekiyorsa [köşeli parantez] içinde boş bırak.\n"
    "Gerekirse birden çok kısa mesaj yaz; her mesajın yanit_id'si cevapladığı gelen mesajın id'si olsun (genel cevapta null).\n"
    'SADECE JSON: {"ozet": "gelenlerin tek cümle özeti", "secenekler": [{"etiket": "kısa karar adı", '
    '"mesajlar": [{"yanit_id": "...", "metin": "..."}]}]}  (karar gerekmiyorsa tek seçenek)'
)


def kart_getir(kuyruk, sohbet_id, ad, gecmis):
    kart = db.kisi(sohbet_id)
    if kart and kart.get("iliski") != "bilinmiyor":
        return kart
    metin = "\n".join(f"{sahip.AD if m['benden'] else m.get('gonderen_adi') or ad}: {m['metin']}" for m in gecmis[-ayarlar.al("baglam_mesaj"):])
    tahmin = kuyruk.ekle(Is("eleme", KART_SISTEM, f"Kişi adı (rehber): {ad}\nSohbet:\n{metin}")).bekle(300) or {}
    return db.kisi_kaydet(sohbet_id, ad=ad, iliski=tahmin.get("iliski") or "bilinmiyor",
                          hitap=tahmin.get("hitap"), sen_siz=tahmin.get("sen_siz"), guven="tahmin")


def ornekler(sohbet_id, iliski):
    """Önce bu kişiye yazdıkları, yetmezse aynı ilişki türündeki kişilere yazdıkları."""
    kendi = [m["metin"] for m in db.benim_mesajlarim(sohbet_id, 15)]
    if len(kendi) < 8 and iliski != "bilinmiyor":
        benzer = db.oku("""SELECT m.metin FROM mesajlar m JOIN kisiler k ON k.id=m.sohbet_id
                           WHERE m.benden=1 AND k.iliski=? AND m.sohbet_id!=? ORDER BY m.zaman DESC LIMIT ?""",
                        iliski, sohbet_id, 15 - len(kendi))
        kendi += [m["metin"] for m in benzer]
    return [m for m in kendi if m and len(m) < 300]


def uslup_kontrol(kart, mesajlar):
    metin = " " + " ".join(m.get("metin", "") for m in mesajlar).lower() + " "
    uyarilar = []
    if kart.get("iliski") in SAMIMI_YASAK_ILISKI:
        bulunan = [w for w in SAMIMI if re.search(rf"\b{w}\b", metin)]
        if bulunan:
            uyarilar.append(f"{kart['iliski']} ilişkisine uygunsuz hitap: {', '.join(bulunan)}")
    if kart.get("iliski") == "bilinmiyor":
        uyarilar.append("Kişiyi tanımıyorum; nötr ve kibar yazdım, ilişkiyi belirtirsen öğrenirim.")
    return uyarilar


def dersler(sohbet_id):
    """Sahibinin önceki taslaklara verdiği geri bildirimler: aynı hatayı tekrarlamamak için isteme eklenir."""
    satirlar = []
    for g in db.son_geri_bildirimler(sohbet_id):
        bu = "bu kişi" if g["sohbet_id"] == sohbet_id else "başka bir kişi"
        oneri = " / ".join(m["metin"] for sec in json.loads(g["oneri"] or "[]") for m in sec.get("mesajlar", []))[:200]
        if g["tur"] == "red":
            satirlar.append(f"- ({bu}) Reddetti: \"{oneri}\"" + (f" — sebep: {g['neden']}" if g["neden"] else ""))
        else:
            gonderilen = " / ".join(m["metin"] for m in json.loads(g["gonderilen"] or "[]"))[:200]
            satirlar.append(f"- ({bu}) Önerilen: \"{oneri}\" -> sahibi bunu gönderdi: \"{gonderilen}\"")
    if not satirlar:
        return ""
    return ("SAHİBİNİN ÖNCEKİ TASLAKLARA GERİ BİLDİRİMLERİ (bunlardan ders al, aynı hataları yapma):\n"
            + "\n".join(satirlar) + "\n\n")


def hazirla(kuyruk, sohbet_id, sohbet_adi, gelenler, talimat=None):
    """gelenler: cevaplanacak mesaj satırları (db.mesajlar). Taslak id'si döner."""
    gecmis = db.son_mesajlar(sohbet_id, 40)
    kart = kart_getir(kuyruk, sohbet_id, sohbet_adi, gecmis)
    ornek = ornekler(sohbet_id, kart["iliski"])
    konusma = "\n".join(f"[{m['id']}] {sahip.AD if m['benden'] else m.get('gonderen_adi') or sohbet_adi}: {m['metin']}"
                        for m in gecmis[-25:])
    istem = (dersler(sohbet_id) +
             f"Kişi kartı: ad={kart.get('ad')}, ilişki={kart['iliski']}, hitap={kart.get('hitap')}, "
             f"sen/siz={kart.get('sen_siz')}, not={kart.get('notlar')}\n"
             f"{sahip.AD} adlı sahibin örnek mesajları:\n" + ("\n".join(f"- {o}" for o in ornek) or "- (henüz yok)") +
             f"\n\nSon konuşma (bağlam):\n{konusma}\n\n"
             "CEVAPLANACAK MESAJ(LAR) — SADECE bunlara cevap ver, sohbetteki başka konulara değil:\n"
             + "\n".join(f"[{m['id']}] {m.get('gonderen_adi') or sohbet_adi}: {m['metin']}" for m in gelenler) + "\n"
             f"Bugün: {time.strftime('%Y-%m-%d %A %H:%M')}")
    if talimat:
        istem += ("\n\nSAHİBİNİN TALİMATI: " + talimat + "\nCevabı bu talimata göre, sahibin üslubuyla yaz. Talimatta olmayan bilgi, söz veya plan UYDURMA. "
                  "Tek seçenek yeter.")
    gecerli = {m["id"] for m in gecmis}
    for deneme in range(2):
        cevap = kuyruk.ekle(Is("taslak", TASLAK_SISTEM, istem)).bekle() or {}
        secenekler = []
        for sec in cevap.get("secenekler") or []:
            if not isinstance(sec, dict):
                continue
            # "[çıkartma]" gibi yer tutucular gönderilemez; sadece gerçek metinler kalır
            mesajlar = [m for m in sec.get("mesajlar") or [] if isinstance(m, dict) and m.get("metin")
                        and not YER_TUTUCU.fullmatch(m["metin"].strip())]
            for m in mesajlar:  # model uydurma id verdiyse alıntıyı kaldır
                if m.get("yanit_id") not in gecerli:
                    m["yanit_id"] = None
            if mesajlar:
                secenekler.append({"etiket": sec.get("etiket") or "Cevap", "mesajlar": mesajlar})
        tum = [m for sec in secenekler for m in sec["mesajlar"]]
        uyarilar = uslup_kontrol(kart, tum)
        if secenekler and not any("uygunsuz" in u for u in uyarilar):
            break
        istem += ("\n\nÖNCEKİ TASLAK REDDEDİLDİ: " + uyarilar[0] + ". Bu kelimeleri kullanma.") if uyarilar else ""
    if talimat:  # sözlü talimat: tek seçenek, tek mesaj
        secenekler = [{"etiket": "Talimatına göre", "mesajlar": secenekler[0]["mesajlar"]}] if secenekler else secenekler
    return db.taslak_ekle(sohbet_id, sohbet_adi, [m["id"] for m in gelenler], cevap.get("ozet"), secenekler, uyarilar)
