# Tulpar

Kişisel yapay zekâ asistanı (diğer adı **Kâhya**). Evdeki bir laptopta yerel modelle çalışır; veriler makineden çıkmaz.

- **WhatsApp**: mesajları okur (hariç tutulan sohbetler hiç okunmaz), önemlileri bildirir, kişiye göre üslupla cevap taslağı hazırlar. Hiçbir şey onaysız gönderilmez.
- **Güvenlik**: dolandırıcılık, IBAN/kod/şifre istekleri ve Tulpar'a talimat vermeye çalışan mesajlar koddaki kurallarla yakalanır; model ne derse desin uyarı verilir.
- **Ses**: sesli mesajlar ve sesli komutlar yerelde Whisper ile yazıya dökülür.
- **Android uygulaması**: sesli konuşma, onay bekleyen işler, taslak onayı, WhatsApp görünümü, görevler.

## Yapı

| Klasör | İçerik |
|---|---|
| `core/` | Ana servis (FastAPI): kuyruk, kurallar, eleme, taslak, kişi kartları, uygulama uç noktaları |
| `whatsapp/` | WhatsApp köprüsü (Baileys, tarayıcısız) |
| `app/` | Android uygulaması (Expo / React Native) |
| `eval/` | Model yarışması: 46 zor Türkçe senaryo ve değerlendirme betikleri |
| `sunucu/` | systemd servisleri, terminal komutları (`tulpar-izle`, `tulpar-qr`, `tulpar-sohbetler`, `tulpar-taslaklar`), model ayar örnekleri |
| `docs/` | Kurulum rehberi |

## Donanım ve modeller

HP laptop (i5-1235U, 16 GB RAM, GPU yok), Ubuntu Server 26.04, llama.cpp.
Günlük işler: **Gemma 4 26B-A4B (Q3_K_XL)**. Yedek: Qwen3.5 9B. Özenli mod: gpt-oss-120b.
Seçim `eval/` içindeki testle ve gerçek mesaj karşılaştırmasıyla yapıldı.

## Gizlilik

Mesajlar, veritabanı, WhatsApp oturumu, API anahtarı ve modeller bu repoda **yoktur** (`.gitignore`). Hepsi sunucuda `~/tulpar/veri` altında durur.
