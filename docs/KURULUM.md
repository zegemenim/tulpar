# Jarvis — HP Bilgisayara Linux Kurulumu

Hedef: HP'de (i5 12. nesil, 16 GB RAM) Windows'un yanına arayüzsüz, en hafif Linux'u kurmak.
Linux açıkken Jarvis çalışır; Windows'a geçtiğinde işler sırada bekler.

**Seçilen sistem: Ubuntu Server 26.04.1 LTS** (masaüstü yok)
- Boşta ~400 MB RAM kullanır, geri kalan ~15 GB modele kalır.
- En yeni LTS: 12. nesil Intel için daha yeni çekirdek ve sürücüler; 2031e kadar destek.
- 12. nesil Intel işlemci, Wi-Fi ve llama.cpp için en iyi destek bunda.

---

## A. Windows'ta hazırlık (~20 dk)

1. **BitLocker kontrolü (önemli!)**
   - Ayarlar → Gizlilik ve güvenlik → Cihaz şifreleme / BitLocker.
   - Açıksa kurtarma anahtarını kaydet: https://account.microsoft.com/devices/recoverykey
   - Bunu yapmazsan Linux kurduktan sonra Windows kurtarma anahtarı isteyebilir.
2. **Hızlı Başlatma'yı kapat**
   - Denetim Masası → Güç Seçenekleri → "Güç düğmelerinin yapacaklarını seçin" → "Hızlı başlatmayı aç" işaretini kaldır.
   - *Neden:* Hızlı başlatma açıkken "Kapat" aslında tam kapatma değil, yarı uyku modudur. Windows diski ve donanımı (özellikle Wi-Fi kartını) kilitli bir durumda bırakır. Ardından Linux açılınca Wi-Fi çalışmayabilir, saat kayabilir, Linux Windows diskine dokunursa veri bozulabilir. Bedeli: Windows birkaç saniye geç açılır.
3. **Linux için yer ayır**
   - Bölümün zaten varsa: en az **150 GB** olmalı. Model dosyaları 13–17 GB'lık parçalar ve birkaç tanesini deneyeceğiz.
   - Bölüm yoksa: Win+X → Disk Yönetimi → C: sağ tık → Birimi Daralt.
   - Linux'a ayıracağın alan "Ayrılmamış" kalsın, biçimlendirme. Linux kurulumu biçimlendirecek.
4. **Kurulum USB'si** (en az 8 GB, içindeki her şey silinir)
   - ISO: https://ubuntu.com/download/server → Ubuntu Server 26.04.1 LTS
   - Yazdırma aracı: https://rufus.ie → Bölüm şeması: GPT, Hedef: UEFI
5. **BIOS ayarları** (açılışta F10)
   - Secure Boot: **açık kalabilir**, Ubuntu destekliyor.
   - Pil koruma: "Battery Care Function" veya "Adaptive Battery Optimizer" seçeneğini **etkinleştir**. Laptop sürekli şarjda kalacağı için pili korur.
   - Kurulumda disk görünmezse: SATA/NVMe modu "RAID/Intel RST" ise sorun budur. Bana yaz, Windows'u bozmadan nasıl değiştirileceğini anlatırım.

## B. Ubuntu Server 26.04.1 kurulumu (~20 dk)

USB takılıyken bilgisayarı başlat, F9 (boot menüsü) → USB'yi seç.

| Ekran | Seçim |
|---|---|
| Dil | English (hata mesajlarını aramak kolay olur) |
| Klavye | Turkish (Q) |
| Kurulum türü | **Ubuntu Server** (minimized değil) |
| Ağ | Mümkünse Ethernet kablosu tak. Wi-Fi'yi kurulumdan sonra da ayarlayabiliriz (D bölümü). |
| Proxy / Mirror | Varsayılan |
| Depolama | **Custom storage layout** → "free space" seç → `ext4`, mount `/`, tüm boş alan. **Windows bölümlerine dokunma.** |
| Profil | İsim: istediğin; sunucu adı: `tulpar`; kullanıcı adı: istediğin |
| Ubuntu Pro | Skip |
| SSH | ✅ **Install OpenSSH server** |
| Featured snaps | Hiçbirini seçme |

Kurulum bitince "Reboot Now" → USB'yi çıkar. Açılışta GRUB menüsü gelir. Ubuntu varsayılandır, Windows için menüden "Windows Boot Manager"ı seç.

## C. Kurulumdan sonra senin yapacakların (sadece 2 komut)

Kurulumda **Wi-Fi'yi ağ ekranında seç ve şifreni gir**, sunucu adına `tulpar` yaz.
Açılınca kullanıcı adın ve şifrenle giriş yap, sonra:

**1) Tailscale'a bağla** — ekrana QR kod çıkar, telefonla okut ve onayla:
```bash
curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up --qr
```

**2) Benim şifresiz `sudo` kullanabilmem için:**
```bash
echo "$USER ALL=(ALL) NOPASSWD:ALL" | sudo tee /etc/sudoers.d/90-$USER
```

Sonra bana **"hazır" + kullanıcı adını** yaz. Mac'te bir terminal sekmesi açacağım; orada şifreni **bir kez** yazacaksın. Kalan her şeyi (güncellemeler, kapak/uyku ayarı, Wi-Fi sağlamlaştırma, model kurulumu) ben uzaktan yapacağım.

> Kurulum ekranında Wi-Fi görünmezse: geçici olarak telefonundan USB ile internet paylaş (USB tethering) veya kablo tak, Wi-Fi'yi sonra ben ayarlarım.

---

## Sonraki adımlar (bunları ben yapacağım)

1. **llama.cpp**: HP'nin işlemcisine özel derleme (AVX-VNNI), RAM'e kilitli çalıştırma.
2. **Model yarışması**: 3 aday modeli senin gerçek mesaj tiplerinle test edip kazananı seçmek.
   - Gemma 4 26B-A4B (Q3_K_XL 12.9 GB / IQ4_XS 13.6 GB)
   - Qwen3.6 35B-A3B (IQ3_XXS 13.2 GB)
   - Qwen3.5 9B (Q8, ~9.5 GB; daha az bilgili ama kesin değerlendirme)
3. **Jarvis çekirdeği**: görev kuyruğu, güvenlik katmanı, onay sistemi, hafıza.
4. **WhatsApp**: okuma, özet, önem tespiti, taslak + doğallık puanı (puan düşükse Claude'a yeniden yazdırma).
5. **Android uygulaması**: sesli konuşma + taslak inceleme ekranı.
6. **Claude Code köprüsü**: %80'de uyarı, %20 acil işlere ayrılır.
7. **İnce ayar** (daha sonra): Colab'de LoRA.
