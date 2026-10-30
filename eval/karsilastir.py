"""Son gerçek mesajlar: kayıtlı 9B kararı ile Gemma'nın kararı (aynı istem, 15 mesaj bağlam, kurallar)."""
import json, sys, time, pathlib
sys.path.insert(0, str(pathlib.Path.home() / "tulpar/core"))
import db, kurallar, llm, sahip
ISTEM = {k: sahip.doldur(v) for k, v in json.loads((pathlib.Path.home() / "tulpar/core/istemler.json").read_text()).items()}
llm.ac("buyuk")
rows = db.oku("SELECT * FROM mesajlar WHERE benden=0 AND eleme IS NOT NULL AND zaman>strftime('%s','now')-10800 ORDER BY zaman")
sistem = ISTEM["system_triage"].replace("{bugun}", "2026-10-30 Cuma")
t0 = time.time()
for m in rows:
    onceki = [x for x in db.son_mesajlar(m["sohbet_id"], 40) if x["id"] != m["id"] and x["zaman"] <= m["zaman"]][-15:]
    baglam = "\n".join(f"{sahip.AD if x['benden'] else x.get('gonderen_adi') or '?'}: {x['metin'][:200]}" for x in onceki)
    kaynak = f"{m['sohbet_adi']} (grup), yazan: {m['gonderen_adi']}" if m["grup"] else m["sohbet_adi"]
    istem = f"Kaynak: {kaynak}\nÖnceki mesajlar (sadece bağlam, değerlendirme):\n{baglam}\nDeğerlendirilecek mesaj: {m['metin']}"
    g = kurallar.uygula(llm.sor("buyuk", sistem, istem), m["metin"], bool(m["grup"]))
    q = json.loads(m["eleme"])
    print(f"\n[{m['sohbet_adi'][:22]}] {m['metin'][:70]}\n   9B   : {q.get('onem')}/{q.get('aksiyon')}: {(q.get('ozet') or '')[:90]}\n"
          f"   Gemma: {g.get('onem')}/{g.get('aksiyon')}: {(g.get('ozet') or '')[:90]}", flush=True)
print(f"\nGemma: {len(rows)} mesaj, {time.time() - t0:.0f} sn")
