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
6. **Aylık para analizi**: banka SMS'lerinden harcama özeti, "ne aldın / gerekli miydi", gelirle bütçe ve birikim hedefleri (yatırım tavsiyesi değil)
7. **Gmail** (5-6 e-posta hesabı Gmail'e yönlendirilip bağlanacak)
8. **Telefon görüşmeleri**: kayıt klasöründen yazıya dök, konuşmacı ayır, sahibinin sesini tanı, görev/takvim çıkar; konuşma üslubunu ve ses tonunu öğren
9. **Fotoğraf/çıkartma anlama** (Gemma görüntü desteği)
10. **Düzenli yeniden eğitim**: ~6 ayda bir veri otomatik hazırlanır, bildirim gelir, Colab'da tek tıkla eğitilir; eğitim konuları: mesaj üslubu, konuşma üslubu, taslak kararları/düzeltmeleri, komut alışkanlıkları, e-posta üslubu

## Notlar
- Donanım: RAM yükseltmesi ileride (2×32 GB DDR4-3200 SO-DIMM, Çin'den yolcu beraberinde en uygun)
- Repo şimdilik private; kişisel bilgiler `~/tulpar/veri/sahip.json` içinde, repoda yok
