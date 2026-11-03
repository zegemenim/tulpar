"""Gece deneyi raporu: strateji ortalamaları + KÖR okuma dosyası (adaylar harfle karıştırılır; anahtar ayrı dosyada).
Kullanım (HP'de): python taslak_rapor.py -> veri/eval/deney-kor.md ve deney-anahtar.json"""
import json
import pathlib
import random

K = pathlib.Path.home() / "tulpar/veri/eval"
d = json.loads((K / "deney.json").read_text())
stratejiler = sorted({s for v in d for s in v["adaylar"]})
print(f"{len(d)} vaka")
print(f"{'strateji':22} {'top1':>6} {'en_iyi':>7} {'uzunluk_farki':>14} {'sn':>5}")
for s in stratejiler:
    r = [v["adaylar"][s] for v in d if s in v["adaylar"]]
    print(f"{s:22} {sum(x['top1'] for x in r)/len(r):6.3f} {sum(x['en_iyi'] for x in r)/len(r):7.3f} {sum(x['uzunluk_farki'] for x in r)/len(r):14.2f} {sum(x['sn'] for x in r)/len(r):5.0f}")
rnd = random.Random(5)
satir, anahtar = [], {}
for i, v in enumerate(d, 1):
    sirali = list(v["adaylar"])
    rnd.shuffle(sirali)
    anahtar[i] = {chr(65 + j): s for j, s in enumerate(sirali)}
    satir += [f"## {i}. GELEN: {' / '.join(v['gelen'])[:140]}", f"GERÇEK: {v['gercek']}"]
    for j, s in enumerate(sirali):
        satir.append(f"{chr(65 + j)}: " + " || ".join(x[:80] for x in v["adaylar"][s]["secenekler"][:3]))
    satir.append("")
(K / "deney-kor.md").write_text("\n".join(satir))
(K / "deney-anahtar.json").write_text(json.dumps(anahtar, ensure_ascii=False))
