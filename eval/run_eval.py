#!/usr/bin/env python3
"""Tulpar model yarışması: her modeli llama-server ile açar, Türkçe senaryoları çalıştırır, puanlar."""
import json, subprocess, sys, time, urllib.request, pathlib, syslog

HOME = pathlib.Path.home() / "tulpar"
SERVER = HOME / "llama.cpp/build/bin/llama-server"
PORT = 8091
CASES = json.loads((pathlib.Path(__file__).parent / "cases.json").read_text())


def log(msg):
    syslog.openlog("tulpar")
    syslog.syslog(msg)
    print(msg, flush=True)


def chat(system, user, max_tokens=300):
    body = {
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.3,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions",
                                 data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=900) as r:
        res = json.load(r)
    text = res["choices"][0]["message"]["content"]
    timings = res.get("timings", {})
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    return parsed, text, time.time() - t0, timings


def run_model(name, path):
    log(f"model yukleniyor: {name}")
    proc = subprocess.Popen([str(SERVER), "-m", str(path), "--port", str(PORT), "-t", "10", "-c", "4096",
                             "--jinja", "--no-webui"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(300):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2)
                break
            except Exception:
                time.sleep(2)
        log(f"model hazir: {name}")
        out = {"model": name, "triage": [], "tool": [], "draft": []}

        for c in CASES["triage"]:
            p, raw, sec, tm = chat(CASES["system_triage"], f"Kaynak: {c['kaynak']}\nMesaj: {c['mesaj']}")
            low = lambda v: "dusuk" if v in ("yok", "dusuk") else v
            ok = bool(p) and all((low(p.get(k)) == low(v)) if k == "onem" else p.get(k) == v for k, v in c["beklenen"].items())
            out["triage"].append({"id": c["id"], "ok": ok, "cevap": p or raw, "sn": round(sec, 1),
                                  "kelime_sn": round(tm.get("predicted_per_second", 0), 1)})
            log(f"{name} {c['id']} {'tamam' if ok else 'HATA'} ({sec:.0f} sn)")

        for c in CASES["tool"]:
            p, raw, sec, tm = chat(CASES["system_tool"], c["istek"])
            ok = bool(p) and p.get("arac") == c["beklenen_arac"] and p.get("onay_gerekir") == c["beklenen_onay"]
            out["tool"].append({"id": c["id"], "ok": ok, "cevap": p or raw, "sn": round(sec, 1)})
            log(f"{name} {c['id']} {'tamam' if ok else 'HATA'} ({sec:.0f} sn)")

        for c in CASES["draft"]:
            gelen = "\n".join(f"[{m['id']}] {m['metin']}" for m in c["gelen"])
            p, raw, sec, tm = chat(CASES["system_draft"], f"Kişi: {c['kisi']}\nGelen mesajlar:\n{gelen}\nDurum: {c['not']}")
            out["draft"].append({"id": c["id"], "cevap": p or raw, "sn": round(sec, 1)})
            log(f"{name} {c['id']} taslak cevap uretildi ({sec:.0f} sn)")

        tr = sum(x["ok"] for x in out["triage"]); to = sum(x["ok"] for x in out["tool"])
        out["puan"] = {"triage": f"{tr}/{len(out['triage'])}", "tool": f"{to}/{len(out['tool'])}"}
        log(f"{name} sonuc: siniflandirma {tr}/{len(out['triage'])}, arac secimi {to}/{len(out['tool'])}")
        return out
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    name, path = sys.argv[1], sys.argv[2]
    res = run_model(name, path)
    (pathlib.Path(__file__).parent / f"sonuc-{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
