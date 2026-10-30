"""Model sunucularıyla konuşma. Akışlı (stream) istek atar, böylece büyük model
işin ortasında durdurulabilir: acil bir iş gelince bağlantı kapatılır, sunucu üretmeyi bırakır."""
import http.client
import json
import subprocess
import time
import urllib.request

MODELLER = {  # ad: (port, systemd servisi)
    "hizli": (8080, "tulpar-llm@hizli"),
    "buyuk": (8081, "tulpar-llm@buyuk"),
    "ozenli": (8082, "tulpar-llm@ozenli"),
}


class Iptal(Exception):
    """İş, daha acil bir iş yüzünden yarıda kesildi."""


def hazir_mi(model):
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{MODELLER[model][0]}/health", timeout=2)
        return True
    except Exception:
        return False


def ac(model, bekle=900):
    if hazir_mi(model):
        return
    subprocess.run(["sudo", "systemctl", "start", MODELLER[model][1]], check=True)
    for _ in range(bekle):
        if hazir_mi(model):
            return
        time.sleep(1)
    raise RuntimeError(f"{model} modeli açılamadı")


def kapat(model):
    subprocess.run(["sudo", "systemctl", "stop", MODELLER[model][1]], check=False)


def akis(model, sistem, kullanici, json_cevap=False, dusunme=None, durdur=None):
    """Modelin cevabını üretildikçe parça parça verir (anlık okuma/gösterme için).
    durdur: threading.Event; set edilirse iş kesilir ve Iptal fırlatılır."""
    kw = {"enable_thinking": False}
    if dusunme:
        kw["reasoning_effort"] = dusunme
    govde = {
        "messages": [{"role": "system", "content": sistem}, {"role": "user", "content": kullanici}],
        "temperature": 0.3,
        "stream": True,
        "chat_template_kwargs": kw,
    }
    if json_cevap:
        govde["response_format"] = {"type": "json_object"}
    baglanti = http.client.HTTPConnection("127.0.0.1", MODELLER[model][0], timeout=3600)
    baglanti.request("POST", "/v1/chat/completions", json.dumps(govde), {"Content-Type": "application/json"})
    yanit = baglanti.getresponse()
    try:
        for satir in yanit:
            if durdur is not None and durdur.is_set():
                raise Iptal()
            satir = satir.strip()
            if not satir.startswith(b"data:") or satir == b"data: [DONE]":
                continue
            parca = json.loads(satir[5:])["choices"][0].get("delta", {}).get("content")
            if parca:
                yield parca
    finally:
        baglanti.close()


def sor(model, sistem, kullanici, json_cevap=True, dusunme=None, durdur=None):
    """Modelden cevabın tamamını al. dusunme: None | 'low' | 'medium' | 'high' (sadece düşünen modeller)."""
    metin = "".join(akis(model, sistem, kullanici, json_cevap, dusunme, durdur))
    if not json_cevap:
        return metin
    try:
        return json.loads(metin)
    except json.JSONDecodeError:
        return {"_ham": metin}
