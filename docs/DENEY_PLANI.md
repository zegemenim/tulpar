# Taslak üslubu deneyi (3 Kasım gecesi)

Amaç: yerel modelle sahibin diline en yakın taslağı üreten yöntemi bulmak. Model sabit (Gemma, eski), değişen strateji.
Düzenek: `core/taslak_deney.py` (HP'de `tulpar-deney` servisi, en çok 7,5 saat, 14 gerçek vaka, her vakada gerçek cevap gizli).
Çıktı: `veri/eval/deney.json`; rapor: `core/taslak_rapor.py` (strateji ortalamaları + kör okuma dosyası `deney-kor.md`, anahtar `deney-anahtar.json`).

| Kod | Strateji |
|---|---|
| A0 | Temel: son 15 mesajın örnek (şimdiki yöntem) |
| A1 | + benzer geçmiş durumlar (gelen→cevap çiftleri) + yazış alışkanlığı sayıları |
| A2 | Sohbet biçiminde few-shot: benzer durumlar kullanıcı/asistan turları olarak, düz metin tek cevap |
| A3 | A2 ile 4 aday (yüksek sıcaklık), sahibin benzer durumlardaki cevaplarına benzerliğe göre sırala |
| A4 | Üslup kılavuzu (modelin 150 mesajdan çıkardığı madde madde profil) + benzer durumlar |
| A5 | Çok örnek: 40 kendi mesajı + 20 benzer durum |
| A6 | İki aşama: önce 3 olası yön, sonra her yön için A2 tarzı yazım |
| A7 | A0 taslağını örnek mesajlara bakarak yeniden yazdırma |

Ölçüt: otomatik n-gram benzerliği (top1, en iyi seçenek), uzunluk farkı; asıl hakem kör okumayla Claude (karar uydurma, bağlam, üslup 0-2 puan).
Sabah: `python taslak_rapor.py` -> kazananı `taslak.py`'ye taşı, kalanları belgeye yaz.

## Sonuç (14 vaka, 2 sa 46 dk sürdü)
Kör puan (Claude, 0-2, strateji adı bilinmeden) / otomatik benzerlik (top1):
| Strateji | Kör puan ort. | top1 |
|---|---|---|
| A1 benzer durumlar + alışkanlık | **1,50** | **0,166** |
| A4 üslup kılavuzu + benzer durumlar | 1,43 | 0,078 |
| A5 çok örnek | 1,21 | 0,111 |
| A7 yeniden yazdırma | 1,14 | 0,078 |
| A3 çoklu aday + sıralama | 1,07 | 0,082 |
| A0 temel (eski) | 1,07 | 0,072 |
| A2 sohbet few-shot (tek cevap) | 0,86 | 0,077 |
| A6 iki aşama | 0,79 | 0,080 |
Yorum: A1 (zaten üretimde) eski yönteme göre belirgin iyi; A4 yakın ikinci. Küçük örneklem (n=14), fark yönü anlamlı ama kesin değil.
Gözlem: tek cevaplı yöntemler (A2, A7) ve iki aşamalı yöntem seçenek çeşitliliğini kaybettiği için geride kaldı; çok seçenek veren yöntemler "karar" vakalarında kazandı.
Sıradaki: A1+A4 birleşimi, daha fazla vaka (30+), kötü kalıpları (örn. "[video]" yer tutucusu, klavye ezmesi, gereksiz "hocam") süzen kural.
