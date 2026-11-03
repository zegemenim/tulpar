"""Claude Code köprüsü: proje/konuşma/mod seçimi (Mac'e bağlanmadan). Çalıştır: python test_claude_kod.py"""
import claude_kod as c

L = [
    {"ad": "tulpar", "klasor": "/p/tulpar", "aciklama": "Kişisel asistan", "oturumlar": [
        {"id": "a1", "baslik": "Jarvis asistanı geliştirme", "zaman": 3}, {"id": "a2", "baslik": "WhatsApp taslak deneyi", "zaman": 1}]},
    {"ad": "Tradey", "klasor": "/p/Tradey", "aciklama": "Borsa botu", "oturumlar": [{"id": "b1", "baslik": "Mum grafiği hatası", "zaman": 2}]},
    {"ad": "Tradey-app", "klasor": "/p/Tradey-app", "aciklama": "Mobil", "oturumlar": [{"id": "c1", "baslik": "Giriş ekranı", "zaman": 2}]},
    {"ad": "MTS", "klasor": "/p/MTS", "aciklama": "", "oturumlar": []},
]
assert c.proje_sec("Tradey'de mum hatasına bak", None, L)[0]["ad"] == "Tradey"
assert c.proje_sec("Tradey-app giriş ekranını düzelt", None, L)[0]["ad"] == "Tradey-app"  # en uzun ad kazanır
assert c.proje_sec("Tulpar'da pano hatası var", None, L)[0]["ad"] == "tulpar"
assert c.proje_sec("şunu yap", "mts", L)[0]["ad"] == "MTS"  # araç parametresi ipucu
assert c.proje_sec("bir şey yap", None, L)[0] is None
assert c.proje_sec("borsa botu", None, L, lambda s, i: {"proje": "Tradey"})[0]["ad"] == "Tradey"  # model yedeği
assert c.proje_sec("borsa", None, L, lambda s, i: {"proje": "yok"})[0] is None
p = L[0]
assert c.oturum_sec(p, "taslak deneyi sonuçlarını incele")["id"] == "a2"  # başlıkla örtüşen
assert c.oturum_sec(p, "pano hatasını düzelt")["id"] == "a1"  # örtüşme yok: en son
assert c.oturum_sec(p, "yeni konuşma aç, pano hatasını düzelt") is None
assert c.oturum_sec(L[3], "x") is None
assert c.mod_sec("Tradey'de mum hatasına bak") == "plan"
assert c.mod_sec("dosyayı oku, hiçbir şeyi değiştirme") == "plan"
assert c.mod_sec("Tradey'de hatayı düzelt") == "duzenle"
assert c.mod_sec("neden çöküyor incele ve düzelt") == "duzenle"
print("tamam")
