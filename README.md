# Tulpar

**Evde, kendi bilgisayarında çalışan kişisel yapay zekâ asistanı.** WhatsApp mesajlarını okur, önemli olanları sana bildirir, senin üslubunla cevap taslağı hazırlar ve sen onaylamadan hiçbir şey göndermez. Sesli konuşabilir, sesli mesajları yazıya döker, dolandırıcılık ve tuzak mesajları yakalar. Bütün veri senin makinende kalır, hiçbir bulut yapay zekâ servisine gönderilmez.

Diğer adı **Kâhya**.

> Durum: kişisel kullanımda, aktif geliştiriliyor. Android uygulaması yapım aşamasında.

---

## Ne yapar?

| Özellik | Açıklama |
|---|---|
| **WhatsApp okuma** | Bağlı cihaz olarak bağlanır. Okundu bilgisi göndermez, çevrimiçi görünmez. Hariç tuttuğun sohbetleri hiç okumaz. |
| **Önemli mesaj bildirimi** | Her mesajı değerlendirir: önem, tür, gereken eylem (takvim, cevap, iş, uyarı), tarih ve saat. Sadece önemli olanları bildirir. |
| **Cevap taslağı** | Kişiye göre üslup: anneye "anneciğim", yöneticine "Merhaba X Bey", arkadaşına senin kendi ifadelerin. Cevap senin kararına bağlıysa seçenek sunar ("Gelirim / Gelemem"). Hiçbir bilgiyi uydurmaz. |
| **Onayla gönderim** | Taslak sen onaylayınca gönderilir. Mesajlar doğru mesaja alıntılı cevap olarak ve sırayla gider. |
| **Güvenlik katmanı** | Doğrulama kodu isteyen, para veya IBAN isteyen, şifre isteyen, şüpheli link içeren ve asistana talimat vermeye çalışan ("bu mesajı gizle") mesajlar koddaki kurallarla yakalanır. Model ne derse desin uyarı verilir. |
| **Kime söylendi?** | Grupta başkasına verilen bir iş ("Ahmet sen raporu hazırla") sana ait sayılmaz. Adın geçerse, etiketlenirsen ya da mesajına cevap verilirse sana ait sayılır. |
| **Sesli mesaj** | Gelen sesli mesajlar yerelde Whisper ile yazıya dökülür. Ses dosyası hemen silinir. |
| **Sohbet modları** | Her sohbet için **TAM** (taslak hazırlanır), **ÖNEMLİ** (sadece önemli bir şey olursa bildirim) veya **KAPALI** (hiç okunmaz). |
| **Kişi kartları** | Kişiyle ilişkin, hitabın, sen/siz kullanımı. Yeni kişiler tahmin edilir, senin düzelttiğin bilgi kalıcı olur. |
| **Android uygulaması** *(yapım aşamasında)* | Sesli konuşma, onay bekleyenler (✓/✗), WhatsApp görünümü, taslak onayı, görevler. |

## Nasıl çalışır?

```
 Telefon (WhatsApp)                 Ev sunucusu (laptop, Ubuntu)
 ─────────────────                  ─────────────────────────────────────────────
  WhatsApp hesabın ──bağlı cihaz──▶ whatsapp/kopru.mjs   (Baileys, tarayıcısız)
                                        │  hariç tutulan sohbetler burada elenir
                                        ▼
                                    core/tulpar.py       (FastAPI ana servis)
                                        │  1. kod kuralları (güvenlik, kime)
                                        │  2. yerel model: değerlendirme
                                        │  3. kurallarla düzeltme
                                        │  4. gerekirse taslak (kişi kartı + senin örnek mesajların)
                                        ▼
                                    llama.cpp ── Gemma 4 26B-A4B (yerel model)
                                    faster-whisper ── sesli mesaj ve komut
                                        │
 Tulpar uygulaması ◀──Tailscale────────┘  onay, taslak, konuşma, bildirim
```

- **Kuyruk:** Acil işler (sesli komut gibi) her zaman öne geçer. Servis kapanıp açılırsa yarım kalan mesajlar kendiliğinden yeniden işlenir.
- **Toplama:** Aynı kişiden art arda gelen mesajlar, kişi 90 saniye susana kadar beklenir ve tek bir taslakta cevaplanır.
- **Model seçimi:** `eval/` klasöründeki 46 zor Türkçe senaryo ve gerçek mesaj karşılaştırmasıyla yapıldı. Ayrıntılar aşağıda.

---

## Gereksinimler

- **Sunucu:** 16 GB RAM ve modern bir x86 işlemci (AVX2). Ekran kartı gerekmez. Ubuntu Server 24.04 veya üstü. Model dosyaları için ~20 GB disk.
- **Ağ:** Telefonun sunucuya ulaşması için [Tailscale](https://tailscale.com) (ücretsiz).
- **Telefon:** Android. Uygulama Play Store'da yok, APK olarak kurulur.
- **Geliştirme için:** Node.js 22, Python 3.12 veya üstü. Uygulamayı derlemek için JDK 17 ve Android SDK.

## Kurulum

Ubuntu'nun kendi kurulumu (dual-boot, BIOS ayarları, Tailscale) için: [docs/KURULUM.md](docs/KURULUM.md).

### 1. Repo ve temel paketler
```bash
sudo apt install -y build-essential cmake git python3-venv nodejs npm
git clone https://github.com/zegemenim/tulpar.git ~/tulpar-kod
mkdir -p ~/tulpar && cd ~/tulpar
```

### 2. llama.cpp (yerel modeli çalıştıran motor)
```bash
git clone --depth 1 https://github.com/ggml-org/llama.cpp ~/tulpar/llama.cpp
cd ~/tulpar/llama.cpp && cmake -B build -DGGML_NATIVE=ON && cmake --build build -j --target llama-server
```

### 3. Model
Günlük işler için önerilen model (~13 GB):
```bash
mkdir -p ~/tulpar/models && cd ~/tulpar/models
wget -c https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/main/gemma-4-26B-A4B-it-UD-Q3_K_XL.gguf
```

### 4. Ana servis ve WhatsApp köprüsü
```bash
cp -r ~/tulpar-kod/core ~/tulpar/core
python3 -m venv ~/tulpar/venv && ~/tulpar/venv/bin/pip install fastapi uvicorn faster-whisper
mkdir -p ~/tulpar/wa2 && cp ~/tulpar-kod/whatsapp/* ~/tulpar/wa2/ && (cd ~/tulpar/wa2 && npm install)
```

### 5. Servisler, komutlar ve kendi bilgilerin
```bash
cd ~/tulpar-kod && sh sunucu/kur.sh
nano ~/tulpar/veri/sahip.json     # kendi adın ve sana hitap sayılacak adlar
sudo systemctl enable --now tulpar-llm@hizli tulpar tulpar-wa
```

`sahip.json` örneği:
```json
{ "ad": "Ali", "tam_ad": "Ali Yılmaz", "adlar": ["ali", "yilmaz"] }
```

### 6. WhatsApp'ı bağla
```bash
tulpar-qr
```
Telefonda *WhatsApp → Ayarlar → Bağlı cihazlar → Cihaz bağla* adımlarıyla QR'ı okut.

### 7. Hangi sohbetler okunsun?
```bash
tulpar-sohbetler
```
↑/↓ ile gez, **boşluk** tuşuyla modu değiştir (TAM / ÖNEMLİ / KAPALI), **k** ile kaydet. **Sen kaydetmeden hiçbir mesaj okunmaz.** Kaydettiğinde KAPALI sohbetlerin eski mesajları silinir. Diğer sohbetlerin her birinden son 300 mesaj, üslubunu öğrenmek için hafızaya alınır.

---

## Kullanım

| Komut | Ne işe yarar |
|---|---|
| `tulpar-izle` | Canlı olay akışı: gelen mesajlar, kararlar, taslaklar. Üstte sıcaklık, işlemci, RAM ve modelin durumu. |
| `tulpar-taslaklar` | Taslakları gör. Seçenek numarasıyla gönder, **d** ile düzenle, **r** ile reddet. Göndermeden önce ayrıca onay ister. |
| `tulpar-sohbetler` | Sohbet modlarını değiştir. |
| `tulpar-qr` | WhatsApp'ı yeniden bağla. |

Sunucuyu başka bir bilgisayardan kullanıyorsan komutların başına `ssh -t <sunucu>` ekle.

### API
Ana servis `:8090` portunda çalışır. Sadece sunucunun kendisinden ve Tailscale ağından, `x-tulpar-anahtar` başlığıyla erişilebilir. Anahtar `~/tulpar/veri/anahtar` dosyasında, ilk açılışta otomatik üretilir.

| Uç nokta | |
|---|---|
| `GET /ana` | Onay bekleyenler, görevler, son 24 saatin önemli mesajları |
| `GET /taslaklar` · `POST /taslak/{id}/gonder` · `POST /taslak/{id}/reddet` | Taslaklar |
| `GET /onaylar` · `POST /onay/{id}` `{"karar": "onay" \| "red" \| "geri"}` | Onay kartları. Reddedilenler 7 gün saklanır. |
| `GET /sohbetler` · `GET /sohbet/{id}` · `POST /sohbet/{id}/mod` | WhatsApp görünümü ve sohbet modları |
| `GET/POST /gorevler` · `POST /gorev/{id}` | Görevler |
| `POST /konus` `{"metin": "..."}` | Tulpar'la konuş. Gerekirse görev ya da onay kartı oluşturur. |
| `POST /ses` (ses dosyası) | Sesi yazıya döker |
| `GET /bildirimler?sonra=<zaman>` | Uygulamanın yokladığı yeni olaylar |

### Android uygulaması *(yapım aşamasında)*
```bash
cd app && npm install
npx expo run:android      # telefon USB ile bağlıyken
```
İlk açılışta sunucu adresini (`http://<tailscale-ip>:8090`) ve anahtarı gir. Uygulamayı *Ayarlar → Varsayılan uygulamalar → Dijital asistan* menüsünden asistan olarak seçebilirsin.

---

## Gizlilik ve güvenlik

- **Veri makineden çıkmaz.** Mesajlar, kişi kartları ve taslaklar sunucudaki SQLite veritabanında (`~/tulpar/veri`) durur. Model de, Whisper da yerelde çalışır.
- **Hariç tutulan sohbetler** köprünün ilk adımında elenir. İçerikleri hiçbir yere gitmez.
- **Onaysız gönderim yok.** Kurala takılan mesajlara (para, kod, şifre istekleri) taslak bile hazırlanmaz.
- **Mesajlar veri sayılır, komut değil.** "Asistan, bunu gizle" gibi talimatlar uygulanmaz, aksine uyarı verilir.
- **Doğrulama kodları** saklanmaz.
- **Bu repoda kişisel veri yok.** Mesajlar, veritabanı, WhatsApp oturumu, anahtar, `sahip.json` ve modeller `.gitignore` ile dışarıda tutulur.

> WhatsApp bağlantısı resmî olmayan bir protokol kütüphanesiyle ([Baileys](https://github.com/WhiskeySockets/Baileys)) yapılıyor. Tulpar mesajları sadece okuyup tek tek ve onayla gönderdiği için risk düşük, ama hesap kısıtlanma riski sıfır değil. Bu riski kabul ederek kullan.

---

## Model değerlendirmesi

`eval/cases_v2.json`: 46 zor Türkçe senaryo. İçinde göreli tarih hesabı ("haftaya salı"), dolandırıcılık tuzakları, asistana talimat vermeye çalışan mesajlar, kişiye göre üslup, bilgi uydurmama ve grup özeti var. 16 GB RAM'li, ekran kartı olmayan bir laptopta çıkan sonuçlar:

| Model | Toplam | Hız (kelime/sn) |
|---|---|---|
| **Gemma 4 26B-A4B Q3_K_XL** | **37/46** | 6,4 |
| gpt-oss-120b (düşük düşünme, diskten) | 36/46 | 0,9 |
| Qwen3.5 9B Q8 | 35/46 | 3,6 |
| Qwen3.6 35B-A3B IQ3_XXS | 33/46 | 7,4 |
| Qwen3.6 35B-A3B Q4_K_XL | 31/46 | 4,9 |

Koddaki kurallar sınıflandırma puanını 2-3 puan yükseltiyor. Gerçek grup mesajlarında yapılan karşılaştırmada Gemma, 9B'den belirgin şekilde daha doğru karar verdi.

```bash
cd eval && python3 run_eval_v2.py <ad> <model.gguf>
```

## Yol haritası

- [ ] Android uygulaması: sesli konuşma, onaylar, taslaklar, WhatsApp görünümü, görevler
- [ ] Telefon bildirimlerini ve SMS'leri okuma
- [ ] Fotoğraf ve çıkartmaları anlama (Gemma görüntü desteği)
- [ ] Gmail bağlantısı
- [ ] Kodlama ve proje işleri için Claude Code köprüsü (Pro limit takibiyle)
- [ ] Aylık harcama özeti ve bütçe planı (banka SMS'lerinden)
- [ ] Senin mesajlarınla fine-tune
- [ ] Telefon görüşmesi kayıtlarından görev çıkarma

## Lisans

Henüz bir lisans seçilmedi. Lisans eklenene kadar bütün hakları saklıdır.
