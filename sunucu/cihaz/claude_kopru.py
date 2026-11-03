"""Mac'teki Claude Code'u Tulpar'dan çalıştırır: projeleri (klasör + son konuşmalar) listeler, seçilen projede seçilen konuşmayı
sürdürerek (ya da yenisini açarak) bir işi arka planda yapar, bitince sonucu HP'ye yollar (/claude/sonuc).
Güvenlik: yalnızca ~/Documents/Projects altındaki bilinen projeler; push, silme, sudo, ağdan indirip çalıştırma yasak (sahibi kendisi yapar);
sorulmadan yayın yok. Mac ajanı (mac-ajan.py) içinden çağrılır."""
import json
import os
import pathlib
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid

KOK = pathlib.Path.home() / ".claude/projects"
IZINLI_KOK = pathlib.Path.home() / "Documents/Projects"
CLAUDE = shutil.which("claude") or str(pathlib.Path.home() / ".local/bin/claude")
YASAK = ["Bash(git push:*)", "Bash(git reset --hard:*)", "Bash(git clean:*)", "Bash(git checkout -- :*)", "Bash(rm:*)", "Bash(sudo:*)",
         "Bash(curl:*)", "Bash(wget:*)", "Bash(ssh:*)", "Bash(scp:*)", "Bash(chmod:*)", "Bash(kill:*)", "Bash(pkill:*)"]
SURE_SN = 30 * 60
AKTIF_SN = 10 * 60  # bu kadar yakın zamanda yazılmış konuşma açık olabilir: üstüne yazmak yerine ondan dal alınır
_isler = {}


def _oturum_bilgisi(dosya):
    """(başlık, cwd): özel başlık varsa o, yoksa ilk kullanıcı mesajı; cwd ilk 400 satırda aranır."""
    baslik, ilk, cwd = None, None, None
    try:
        with open(dosya, encoding="utf-8") as f:
            for i, satir in enumerate(f):
                if i > 400 or (cwd and (baslik or ilk)):
                    break
                try:
                    k = json.loads(satir)
                except ValueError:
                    continue
                cwd = cwd or k.get("cwd")
                if k.get("type") == "custom-title" and k.get("customTitle"):
                    baslik = k["customTitle"]
                if ilk or k.get("type") != "user" or k.get("isSidechain"):
                    continue
                ic = k.get("message", {}).get("content")
                if isinstance(ic, list):
                    ic = " ".join(p.get("text", "") for p in ic if isinstance(p, dict) and p.get("type") == "text")
                if isinstance(ic, str) and ic.strip() and not ic.lstrip().startswith(("<", "Caveat", "Base directory")):
                    ilk = " ".join(ic.split())[:90]
    except OSError:
        pass
    return (baslik or ilk or "(başlıksız)")[:90], cwd


def _aciklama(klasor):
    for ad in ("CLAUDE.md", "README.md"):
        try:
            for satir in (pathlib.Path(klasor) / ad).read_text(encoding="utf-8").splitlines():
                s = satir.strip().lstrip("#>* -").strip()
                if len(s) > 15 and not s.startswith(("<", "=")):
                    return s[:140]
        except OSError:
            continue
    return ""


def projeler():
    """[{ad, klasor, aciklama, oturumlar: [{id, baslik, zaman}]}]; en son kullanılan proje önce. Aynı klasörün konuşmaları birleşir."""
    klasorler = {}
    for d in KOK.iterdir() if KOK.exists() else []:
        for p in sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[:6]:
            if p.stat().st_size < 2000:
                continue
            baslik, cwd = _oturum_bilgisi(p)
            if not cwd or not os.path.isdir(cwd):
                continue
            yol = pathlib.Path(cwd).resolve()
            if IZINLI_KOK not in yol.parents:
                continue
            klasorler.setdefault(str(yol), []).append({"id": p.stem, "baslik": baslik, "zaman": p.stat().st_mtime})
    sonuc = [{"ad": pathlib.Path(k).name, "klasor": k, "aciklama": _aciklama(k), "oturumlar": sorted(o, key=lambda x: -x["zaman"])[:5]}
             for k, o in klasorler.items()]
    return sorted(sonuc, key=lambda x: -x["oturumlar"][0]["zaman"])


def _hp(hp_ayar, yol, govde):
    for adres in hp_ayar.get("adresler") or [hp_ayar.get("adres", "")]:
        try:
            r = urllib.request.Request(adres + yol, data=json.dumps(govde).encode(),
                                       headers={"x-tulpar-anahtar": hp_ayar["anahtar"], "Content-Type": "application/json"})
            return json.load(urllib.request.urlopen(r, timeout=8))
        except Exception:  # noqa: BLE001
            continue
    return None


def _calistir(is_id, komut, klasor, hp_ayar, bilgi):
    t0 = time.time()
    try:
        r = subprocess.run(komut, cwd=klasor, capture_output=True, text=True, timeout=SURE_SN)
        try:
            c = json.loads(r.stdout)
        except ValueError:
            c = {"result": (r.stdout or r.stderr)[-3000:], "is_error": r.returncode != 0}
        govde = {"id": is_id, **bilgi, "sonuc": str(c.get("result", ""))[:6000], "hata": bool(c.get("is_error")),
                 "oturum": c.get("session_id"), "sure": int(time.time() - t0), "maliyet": c.get("total_cost_usd")}
    except subprocess.TimeoutExpired:
        govde = {"id": is_id, **bilgi, "sonuc": "Süre doldu (30 dk), iş yarıda kesildi.", "hata": True, "sure": SURE_SN}
    except Exception as e:  # noqa: BLE001
        govde = {"id": is_id, **bilgi, "sonuc": f"Çalıştırılamadı: {type(e).__name__}: {e}", "hata": True, "sure": int(time.time() - t0)}
    _isler[is_id] = govde
    if hp_ayar:
        _hp(hp_ayar, "/claude/sonuc", govde)


def baslat(v, hp_ayar):
    """v: {klasor, gorev, oturum (id|None), mod ('plan'|'duzenle'), proje, sohbet}. Hemen döner; sonuç HP'ye POST edilir."""
    klasor = pathlib.Path(str(v.get("klasor", ""))).resolve()
    bilinen = {p["klasor"]: p for p in projeler()}
    if str(klasor) not in bilinen:
        return "bilinmeyen proje klasörü"
    gorev = str(v.get("gorev", "")).strip()
    if not gorev:
        return "görev boş"
    komut = [CLAUDE, "-p", gorev, "--output-format", "json", "--permission-mode", "plan" if v.get("mod") == "plan" else "acceptEdits",
             "--disallowedTools", ",".join(YASAK)]
    oturum = v.get("oturum")
    if oturum:
        dosya = next((p for p in (KOK / d.name for d in KOK.iterdir()) if (p / f"{oturum}.jsonl").exists()), None)
        if dosya:
            yeni_mi = time.time() - (dosya / f"{oturum}.jsonl").stat().st_mtime < AKTIF_SN
            komut += ["--resume", str(oturum)] + (["--fork-session"] if yeni_mi else [])
    is_id = uuid.uuid4().hex[:10]
    bilgi = {"proje": bilinen[str(klasor)]["ad"], "gorev": gorev[:200], "mod": v.get("mod") or "duzenle", "sohbet": v.get("sohbet"), "onay": v.get("onay")}
    _isler[is_id] = {"id": is_id, **bilgi, "sonuc": None}
    threading.Thread(target=_calistir, args=(is_id, komut, str(klasor), hp_ayar, bilgi), daemon=True).start()
    return f"baslatildi {is_id}"
