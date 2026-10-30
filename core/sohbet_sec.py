"""Terminalde sohbet seçimi: hangi sohbet tam okunsun, sadece önemliler mi, hiç okunmasın mı.
Kullanım: tulpar-sohbetler   (Mac'ten: ssh -t tulpar tulpar-sohbetler)
Tuşlar: ↑/↓ gez, boşluk mod değiştir, / ara, Enter aramayı bitir, k kaydet, q çık."""
import curses
import json
import pathlib

VERI = pathlib.Path.home() / "tulpar/veri"
MODLAR = ["tam", "onemli", "kapali"]
ETIKET = {"tam": "TAM     ", "onemli": "ÖNEMLİ  ", "kapali": "KAPALI  "}


def yukle():
    adlar = json.loads((VERI / "wa-adlar.json").read_text())
    try:
        sira = json.loads((VERI / "secim-idler.json").read_text())
    except FileNotFoundError:
        sira = []
    sira = sira or list(adlar)  # sadece mesajı olan sohbetler ve gruplar
    try:
        modlar = json.loads((VERI / "sohbet-modlari.json").read_text())
    except FileNotFoundError:
        modlar = {}
    haric = set()
    try:
        haric = set(json.loads((VERI / "haric.json").read_text()).get("sohbetler", []))
    except FileNotFoundError:
        pass
    satirlar = []
    for j in sira:
        a = adlar.get(j, {"ad": j.split("@")[0], "grup": j.endswith("@g.us")})
        mod = "kapali" if j in haric else modlar.get(j) or ("onemli" if a["grup"] else "tam")
        satirlar.append({"id": j, "ad": a["ad"] or j.split("@")[0], "grup": a["grup"], "mod": mod})
    return satirlar


def kaydet(satirlar):
    (VERI / "haric.json").write_text(json.dumps(
        {"sohbetler": [s["id"] for s in satirlar if s["mod"] == "kapali"]}, ensure_ascii=False))
    (VERI / "sohbet-modlari.json").write_text(json.dumps(
        {s["id"]: s["mod"] for s in satirlar if s["mod"] != "kapali"}, ensure_ascii=False))
    (VERI / "haric-onaylandi").write_text("ok")


def ana(ekran):
    curses.curs_set(0)
    curses.use_default_colors()
    for i, renk in enumerate([curses.COLOR_GREEN, curses.COLOR_YELLOW, curses.COLOR_RED], 1):
        curses.init_pair(i, renk, -1)
    satirlar = yukle()
    imlec, ust, arama, arama_modu, mesaj = 0, 0, "", False, ""
    while True:
        gorunen = [s for s in satirlar if arama.lower() in s["ad"].lower()]
        imlec = max(0, min(imlec, len(gorunen) - 1))
        y, x = ekran.getmaxyx()
        alan = y - 4
        ust = min(max(ust, imlec - alan + 1), imlec)
        ekran.erase()
        say = {m: sum(s["mod"] == m for s in satirlar) for m in MODLAR}
        ekran.addnstr(0, 0, f" TULPAR sohbet seçimi   tam {say['tam']}  önemli {say['onemli']}  kapalı {say['kapali']}", x - 1, curses.A_BOLD)
        ekran.addnstr(1, 0, " ↑↓ gez  boşluk: mod değiştir  /: ara  k: kaydet  q: çık" + (f"   arama: {arama}_" if arama_modu or arama else ""), x - 1)
        for i, s in enumerate(gorunen[ust:ust + alan]):
            renk = curses.color_pair(MODLAR.index(s["mod"]) + 1)
            vurgu = curses.A_REVERSE if ust + i == imlec else 0
            ekran.addnstr(3 + i, 0, f" {ETIKET[s['mod']]}{'[grup] ' if s['grup'] else '       '}{s['ad']}", x - 1, renk | vurgu)
        if mesaj:
            ekran.addnstr(y - 1, 0, mesaj, x - 1, curses.A_BOLD)
        tus = ekran.get_wch()
        mesaj = ""
        if arama_modu:
            if tus in ("\n", "\x1b"):
                arama_modu = False
            elif tus in ("\x7f", curses.KEY_BACKSPACE, "\b"):
                arama = arama[:-1]
            elif isinstance(tus, str) and tus.isprintable():
                arama += tus
                imlec = 0
            continue
        if tus in (curses.KEY_UP, "w"):
            imlec -= 1
        elif tus in (curses.KEY_DOWN, "s"):
            imlec += 1
        elif tus == curses.KEY_PPAGE:
            imlec -= alan
        elif tus == curses.KEY_NPAGE:
            imlec += alan
        elif tus == " " and gorunen:
            s = gorunen[imlec]
            s["mod"] = MODLAR[(MODLAR.index(s["mod"]) + 1) % 3]
        elif tus == "/":
            arama_modu, arama = True, ""
        elif tus == "\x1b":
            arama = ""
        elif tus == "k":
            kaydet(satirlar)
            mesaj = " Kaydedildi. Tulpar artık bu ayarlarla okuyor. (q ile çık)"
        elif tus == "q":
            return


if __name__ == "__main__":
    curses.wrapper(ana)
