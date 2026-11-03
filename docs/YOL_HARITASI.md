# Tulpar yol haritası

Sahibinin istekleri ve kararları. Biten işler işaretlenir; yenileri eklendikçe buraya yazılır.

## Bitenler
- [x] HP'de Ubuntu Server, llama.cpp, Gemma 4 26B (tek model), Whisper; kuyruk, kurallar, hafıza tabanı
- [x] WhatsApp köprüsü (Baileys): hariç tutma, okundu bilgisi yok, alıntılı gönderim, tam geçmiş
- [x] Şifreli yedekten 3 yıllık geçmiş aktarımı (hariç sohbetler atlanır)
- [x] Taslaklar: kişiye göre üslup, karar seçenekleri, uydurmama; grupta "taslak hazırlayayım mı?" kartı
- [x] Android uygulaması: ana ekran (ses/yazı), onaylar, WhatsApp görünümü, taslaklar, görevler, ayarlar
- [x] Uygulama Tailscale yoksa ev ağından bağlanır
- [x] İkinci ekran: "ikinci ekranı aç" komutu, 30 dk değişmezse kapanır
- [x] Fine-tune verisi (maskeleme: şifre, kart, IBAN, telefon, e-posta, link, adlar) ve Colab defteri
- [ ] İlk fine-tune (Colab'da sürüyor) → LoRA'yı HP'ye kur, eskisiyle karşılaştır

## Sıradakiler (sahibinin onayladığı sıra)
1. **Telefondan bilgisayar**: uygulamada Terminal (HP kabuğu, tmux) ve Ekran (HP ekranını izle/kontrol et)
2. **Hafıza ("hakkımda")**: ad, hitaplar, sevdikleri, alışkanlıklar, kime nasıl davrandığı; konuşmalardan sürekli öğrenir; uygulamada görüp düzeltilebilir. Model değişse de taşınır.
3. **Tarayıcı ajanı**: HP ekranında, sahibinin gözü önünde araştırır (Playwright); okunabilen sayfayı metin olarak, okunamayanı ekran görüntüsüyle anlar
   - Varsayılan Tulpar yapar; çok derin iş veya kuyrukta çok iş varsa Claude Code'a verir, sonucu Tulpar anlatır
   - Hesaplara girişi sahibi kendisi yapar, Tulpar oturumu sadece okur; satın alma, silme yasak
   - İndirme / paket kurma: kaynağı iki kez doğrula (resmî kaynak, imza/checksum, itibar), sonra sahibine sor
   - Bot koruması (CAPTCHA) çıkarsa: bildirim gönder, sahibi telefondan Ekran sayfasında çözer, Tulpar devam eder
4. **Claude Code köprüsü**: HP'de Claude Code (Pro), `claude_kod(görev, klasör)` aracı; projeleri çalıştırıp test eder, GitHub'dan çeker; silme/yayın/push öncesi sorar; Pro limitini %80'de uyarır, %20 önemli işlere
5. **Telefon bildirimleri ve SMS okuma**; OTP kodları saklanmaz
   - [x] Sunucu: `core/bildirim.py`, `POST/GET /bildirim` (30 gün, OTP süzgeci, tekrar yok sayma, testli); HP'ye kuruldu
   - [x] Uygulama: `BildirimDinleyici` (WhatsApp ve kalıcı bildirimler atlanır, SMS uygulamasından gelenler `sms` türü), Cihazlar sekmesinde "Bildirim erişimi" düğmesi → APK 23'te (toplu derleme)
   - [x] Doğrulama kodu: SMS/bildirimden gerçek kod seçilir (kod sözcüğünden sonra gelen; tutar, referans, B1245 gibi harf önekli numara, yıl elenir), panoya 10 dk konur (Mac'e de eşitlenir, telefon kendi panosuna da yazar), geçmişten silinir, `bildirim.jsonl`'a yazılmaz
   - [x] Mac menüsünde "Telefon bildirimleri" (önemli olanlar: SMS, para/kargo/randevu/güvenlik)
   - [ ] Bildirimlerden özet/görev çıkarma ve Mac menüsünde gösterme; sonra #6 para analizi
6. **Aylık para analizi**: banka SMS'lerinden harcama özeti, "ne aldın / gerekli miydi", gelirle bütçe ve birikim hedefleri (yatırım tavsiyesi değil)
7. **Gmail** (5-6 e-posta hesabı Gmail'e yönlendirilip bağlanacak)
8. **Telefon görüşmeleri**: kayıt klasöründen yazıya dök, konuşmacı ayır, sahibinin sesini tanı, görev/takvim çıkar; konuşma üslubunu ve ses tonunu öğren
9. **Fotoğraf/çıkartma anlama** (Gemma görüntü desteği)
10. **Düzenli yeniden eğitim**: ~6 ayda bir veri otomatik hazırlanır, bildirim gelir, Colab'da tek tıkla eğitilir; eğitim konuları: mesaj üslubu, konuşma üslubu, taslak kararları/düzeltmeleri, komut alışkanlıkları, e-posta üslubu

## Ek istekler
- Taslaklarda çıkartma: sık kullanılan / favori çıkartmalardan seçip gönderebilsin, taslakta görünsün
- Tepki (emoji reaksiyon): önce hangi mesaja hangi tepki ve bağlamı anlatıp onay alsın
- [x] Ana ekranda Tulpar'ın cevabının altında hızlı cevap düğmeleri (Daha kısa söyle / Devam et / Bunu göreve ekle / Neden?) — APK 23
- [x] Sesli okuma sadece telefonun sesi açıkken (`react-native-volume-manager`, medya sesi ≈0 ise sadece yazı) — APK 23
- Uzak ekran (isteğe bağlı; terminal öncelikli)

## Telefon asistanı (planlanan)
- Normal aramalara Android uygulama erişimi yok; yol: SIP numarası (ör. Netgsm) HP'ye bağlanır
- Giden arama: "dişçiyi ara, randevu al" → Tulpar arar, sonucu bildirir
- Gelen: cevapsız/meşgulde operatör yönlendirmesi SIP numarasına → Tulpar karşılar, ne istendiğini öğrenir, "bağlayayım mı?" diye sorar, onayla aktarır
- Modlar: sekreter / sahibinin üslubu — her ikisinde de başta asistan olduğunu söyler; kayıt varsa bildirilir (KVKK)
- Sınır: bu işlemcide yanıt ~5-10 sn; akıcı görüşme için ekran kartı gerekir

## Kaynak dağıtımı (HP / Raspberry Pi / VDS)
Karar: model (Gemma) bölünmez (ağ gecikmesi hızı çökertir); yan işler yük dağıtımı için taşınır.
- [x] **Konuşma sentezi (Piper) → Raspberry Pi**: `sunucu/pi/tulpar-ses.*`, Pi'de `~/tulpar-pi/`, port 8095, anahtarlı. HP `core/tts.py` önce Pi'yi dener, olmazsa yerelde üretir (HP `veri/pi-ses.json` ile bağlanır; HP ağa dönünce yazılacak). Ölçüm: 3,3 sn ses 1,2–2,4 sn'de üretiliyor.
- [x] **Yedekleme → Pi SSD (734 GB boş)** (kuruldu: `tulpar-yedekle`, her gece 04:30, Pi'de 14 gün tutulur; HP'nin Pi'deki anahtarı kısıtlı: sadece `~/tulpar-yedek` klasörü, başka komut çalıştıramaz): HP `veri/` (tulpar.db, haric.json, sohbet-modlari.json, sahip.json, anahtar) ve model dosyaları günlük `rsync` ile; Pi'deki Immich/Nextcloud verilerine dokunulmaz.
- [x] **Model dosyaları**: sadece internette olmayanlar Pi'de saklanır: eğitilmiş LoRA (`tulpar-lora`, Pi'de) ve birleşmiş yeni model (indirme bitince kopyalanacak). İnternette bulunan hazır modeller (Q3_K_XL, Q8, Qwen) yedeklenmez, gerekirse yeniden indirilir; kullanılmayan Q8 ve Qwen HP'den silindi.
- [x] **Web araştırması (tarayıcı) → Raspberry Pi**: `sunucu/pi/tulpar-arastir.*`, port 8096, anahtarlı, sistem Chromium, `MemoryMax=900M` + `OOMScoreAdjust=900` (bellek dolarsa ilk bu kapanır; Immich/Nextcloud etkilenmez). Ölçüm: 2 sayfalık araştırma 35 sn, kullanılabilir RAM en düşük ~1,2 GB. HP `core/tarayici.py` önce Pi'yi dener, olmazsa HP'de yapar (HP `veri/pi-arastir.json` ile bağlanır; HP ağa dönünce yazılacak). VDS kullanılmıyor: iki cihaz yeter.
- [ ] RAM yükseltmesi: 2×16 GB (eşleşen çift; 24 GB karışık çiftli kanalı bozar). Hız değil kararlılık/önbellek kazandırır.
- Küçük model (sınıflandırma) Pi/VDS'e kurulmayacak: kural tabanlı eleme (kanal/bülten) aynı işi bedavaya yapıyor.

## Cihaz kontrolü ve hızlı yol
Karar: "sesi aç", "müziği durdur" gibi basit komutlar Gemma'ya hiç gitmez. Önce kural tabanlı hızlı yol (saniyenin altında, RAM harcamaz); tanınmazsa normal yol. Ayrı bir küçük model şimdilik kurulmayacak: kurallar bu komut türünün büyük kısmını bedavaya çözüyor, HP'nin RAM'i model + Whisper ile dolu, Pi'de yer dar. Kurallar yetmezse (serbest ifadeler) 2. aşamada küçük bir sınıflandırıcı eklenir.
- [x] Hızlı yol: `core/cihaz.py` (ses aç/kıs/ayarla/sessiz, parlaklık, müzik dur/devam/sonraki/önceki, rahatsız etme) sohbet ve sesli konuşma uç noktalarına bağlı.
- [x] Mac ajanı: `sunucu/cihaz/mac-ajan.py` + `kur-mac.sh` (port 8097, anahtarlı, sabit işlem listesi; YouTube Music'i Chrome'dan kontrol eder: "en son çalınanı devam ettir").
- [x] Mac ajanı Mac'e kuruldu (LaunchAgent, 3 Kasım). Kalan izinler: Chrome'da Apple Events JavaScript izni; Erişilebilirlik izni; HP'de `veri/cihazlar.json` ve Mac'te `~/.tulpar-ajan/hp.json` (HP erişilince). Eski not: ( Chrome'da Apple Events JavaScript izni; Erişilebilirlik izni; rahatsız etme için "Tulpar Rahatsız Etme Aç/Kapat" Kısayolları).
- [x] (APK 17) Telefon: uygulamada yerel modül (ses, parlaklık, rahatsız etme izni) — sunucudan gelen `cihaz` eylemini uygular.
- [x] Pano eşitleme: HP `/pano` (7 gün geçmiş, şifre gibi metinler atlanır) + Mac ajanı 2 sn'de bir eşitler; telefon: Mac→telefon uygulama kapalıyken de (komut servisi yazar), telefon→Mac uygulama açıkken (Android arka planda okutmaz) (APK 23).
- [x] Mac menü çubuğu uygulaması `sunucu/cihaz/mac-menu.py` (rumps; pano geçmişi ve bildirim satırına tıklayınca Mac panosuna kopyalar; taslak/görev listesi + ses/müzik/parlaklık/rahatsız etme). Kurulum için `pip install rumps` ve hp.json gerekir.
- [x] "X şarkısını çal" hızlı yolu (YT Music araması, kırılgan).
- [x] (APK 17) Uygulamada "Cihazlar" sekmesi (aynı komutlar düğmelerle).
- [ ] Diğer cihazlar; telefon izinleri (parlaklık, rahatsız etme) Cihazlar sekmesinden bir kez verilir (Windows/Linux ajanı, Home Assistant üzerinden Pi'deki akıllı cihazlar).

## Günlük (terminal) okunabilirliği
- [x] Kuyruk, gelen/giden mesaj, sonuç ve bildirim satırları Türkçe ve düzenli: kim/hangi sohbet, içerik önizlemesi, süre, sırada bekleyen.

## Notlar
- Donanım: RAM yükseltmesi ileride (2×32 GB DDR4-3200 SO-DIMM, Çin'den yolcu beraberinde en uygun)
- Repo şimdilik private; kişisel bilgiler `~/tulpar/veri/sahip.json` içinde, repoda yok
