#!/usr/bin/env python3
"""Tulpar model yarışması v2: zor Türkçe senaryolar (tarih hesabı, dolandırıcılık, talimat saldırısı,
kişiye göre üslup, uydurmama, grup özeti). Kullanım: run_eval_v2.py <ad> <model.gguf> [ctx]"""
import json, os, subprocess, sys, time, urllib.request, pathlib, syslog

HOME = pathlib.Path.home() / "tulpar"
SERVER = HOME / "llama.cpp/build/bin/llama-server"
PORT = 8091
HERE = pathlib.Path(__file__).parent
CASES = json.loads((HERE / "cases_v2.json").read_text())
BUGUN = CASES["bugun"]
CASUAL = ["kanka", "knk", "kral", "lan", "abi", "moruk", "kardeşim"]


def log(msg):
    syslog.openlog("tulpar")
    syslog.syslog(msg)
    print(msg, flush=True)


def chat(system, user, max_tokens=400):
    body = {
        "messages": [{"role": "system", "content": system.replace("{bugun}", BUGUN)},
                     {"role": "user", "content": user}],
        "temperature": 0.3,
        "max_tokens": int(os.environ.get("MAX_TOKENS", max_tokens)),
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False, "reasoning_effort": os.environ.get("EFFORT", "low")},
    }
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            res = json.load(r)
    except Exception as e:
        return None, f"istek hatasi: {e}", time.time() - t0, {}
    text = res["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    return parsed, text, time.time() - t0, res.get("timings", {})


def norm_onem(v):
    return "dusuk" if v in ("yok", "dusuk") else v


def match(field, got, want):
    if isinstance(want, list):
        return got in want
    if field == "saat" and isinstance(got, str):
        return got.zfill(5) == want
    return got == want


def flat(x):
    return json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x


def has_any(text, alts):
    return any(a.lower() in text.lower() for a in alts)


def check_triage(c, p):
    if not p:
        return False, ["json yok"]
    errs = []
    for k, v in c["beklenen"].items():
        got = p.get(k)
        ok = match(k, got, v) or (k == "onem" and not isinstance(v, list) and norm_onem(got) == norm_onem(v))
        if not ok:
            errs.append(f"{k}={got} (beklenen {v})")
    return not errs, errs


def check_tool(c, p):
    if not p:
        return False, ["json yok"]
    errs = []
    arac = str(p.get("arac", "")).replace("()", "")
    if arac != c["arac"]:
        errs.append(f"arac={arac}")
    if c["onay"] is not None and p.get("onay_gerekir") != c["onay"]:
        errs.append(f"onay={p.get('onay_gerekir')}")
    params = flat(p.get("parametreler", {}))
    for s in c.get("param_icerir", []):
        if s not in params:
            errs.append(f"parametrede {s} yok")
    return not errs, errs


def check_draft(c, p):
    if not p or not isinstance(p.get("mesajlar"), list) or not p["mesajlar"]:
        return False, ["mesaj yok"]
    text = " ".join(str(m.get("metin", "")) for m in p["mesajlar"])
    errs = []
    if c["iliski"] in ("aile", "resmi") and has_any(f" {text} ", [f" {w}" for w in CASUAL]):
        errs.append("ilişkiye uygunsuz samimi hitap")
    for alts in c.get("gerekli", []):
        if not has_any(text, alts):
            errs.append(f"eksik: {alts[0]}")
    for w in c.get("yasak", []):
        if w.lower() in text.lower():
            errs.append(f"uydurma/yasak: {w}")
    return not errs, errs


def check_summary(c, p):
    if not p:
        return False, ["json yok"]
    text = flat(p)
    errs = [f"eksik: {alts[0]}" for alts in c["gerekli"] if not has_any(text, alts)]
    errs += [f"uydurma: {w}" for w in c.get("yasak", []) if w.lower() in text.lower()]
    return not errs, errs


def run_model(name, path, ctx):
    log(f"model yukleniyor: {name}")
    t_load = time.time()
    proc = subprocess.Popen([str(SERVER), "-m", str(path), "--port", str(PORT), "-t", "10", "-c", str(ctx),
                             "--jinja", "--no-webui"] + os.environ.get("EXTRA_ARGS", "").split(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(900):
            if proc.poll() is not None:
                raise RuntimeError("sunucu kapandi")
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
                break
            except Exception:
                time.sleep(2)
        load_sec = round(time.time() - t_load, 1)
        log(f"model hazir: {name} ({load_sec} sn'de yuklendi)")
        out = {"model": name, "yukleme_sn": load_sec, "sonuclar": {}}
        groups = [
            ("triage", "system_triage", check_triage, lambda c: f"Kaynak: {c['kaynak']}\nMesaj: {c['mesaj']}"),
            ("tool", "system_tool", check_tool, lambda c: c["istek"]),
            ("draft", "system_draft", check_draft, lambda c: f"Kişi: {c['kisi']}\nGelen mesajlar:\n" +
                "\n".join(f"[{m['id']}] {m['metin']}" for m in c["gelen"]) + f"\nDurum: {c['not']}"),
            ("summary", "system_summary", check_summary, lambda c: f"Grup: {c['grup']}\n" + "\n".join(c["sohbet"])),
        ]
        speeds = []
        for key, sysk, check, fmt in groups:
            rows = []
            for c in CASES[key]:
                p, raw, sec, tm = chat(CASES[sysk], fmt(c), 600 if key == "summary" else 400)
                ok, errs = check(c, p)
                if tm.get("predicted_per_second"):
                    speeds.append(tm["predicted_per_second"])
                rows.append({"id": c["id"], "ok": ok, "hatalar": errs, "cevap": p or raw, "sn": round(sec, 1)})
                log(f"{name} {c['id']} {'tamam' if ok else 'HATA ' + '; '.join(errs)} ({sec:.0f} sn)")
            out["sonuclar"][key] = rows
        out["puan"] = {k: f"{sum(r['ok'] for r in v)}/{len(v)}" for k, v in out["sonuclar"].items()}
        total = sum(sum(r["ok"] for r in v) for v in out["sonuclar"].values())
        n = sum(len(v) for v in out["sonuclar"].values())
        out["toplam"] = f"{total}/{n}"
        out["kelime_sn"] = round(sum(speeds) / len(speeds), 2) if speeds else None
        out["ort_sn"] = round(sum(r["sn"] for v in out["sonuclar"].values() for r in v) / n, 1)
        log(f"{name} SONUC: {out['toplam']} {out['puan']} hiz {out['kelime_sn']} kelime/sn")
        return out
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    name, path = sys.argv[1], sys.argv[2]
    ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 4096
    res = run_model(name, path, ctx)
    (HERE / f"v2-{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
