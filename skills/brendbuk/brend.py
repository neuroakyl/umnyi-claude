"""Брендбук: проверка шрифтов на кыргызские и казахские буквы, контраст цветов. Mac и Windows, Python 3.8+, без установки пакетов.

Запуск: sh "$HOME/.claude/umnyi/bin/py" "$HOME/.claude/skills/brendbuk/brend.py" <команда>
  shrift "Montserrat" "Golos Text" ...   есть ли в шрифте Google Fonts все буквы: русские, кыргызские (ң ө ү), казахские (ә ғ қ ұ һ і)
  kontrast "#111111" "#C6F432"           контраст текста и фона (WCAG): читается ли на телефоне
  otkryt                                 открыть Projects/мозг/бренд/брендбук.html в браузере
Источник: пакет «Умный Claude», 15.11.2026.
"""
import json
import re
import struct
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path.home()
RU = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя"
KY = "ҢӨҮңөү"
KK = "ӘҒҚҢӨҰҮҺІәғқңөұүһі"


def proekty():
    try:
        s = json.loads((HOME / ".claude" / "umnyi-sostoyanie.json").read_text(encoding="utf-8"))
        if s.get("proekty"):
            return Path(s["proekty"])
    except Exception:
        pass
    return HOME / "Projects"


def get(url):
    # Без браузерного User-Agent Google Fonts отдаёт TTF — его легко прочитать без библиотек.
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "umnyi-claude"}), timeout=30) as r:
        return r.read()


def cmap(ttf):
    """Все коды символов из таблицы cmap (форматы 4 и 12)."""
    n = struct.unpack(">H", ttf[4:6])[0]
    tabl = {ttf[12 + 16 * i:16 + 16 * i].decode("latin1"): struct.unpack(">II", ttf[20 + 16 * i:28 + 16 * i]) for i in range(n)}
    off = tabl["cmap"][0]
    kody = set()
    for i in range(struct.unpack(">H", ttf[off + 2:off + 4])[0]):
        sub = off + struct.unpack(">I", ttf[off + 8 + 8 * i:off + 12 + 8 * i])[0]
        fmt = struct.unpack(">H", ttf[sub:sub + 2])[0]
        if fmt == 4:
            segx2 = struct.unpack(">H", ttf[sub + 6:sub + 8])[0]
            ends = struct.unpack(f">{segx2 // 2}H", ttf[sub + 14:sub + 14 + segx2])
            starts = struct.unpack(f">{segx2 // 2}H", ttf[sub + 16 + segx2:sub + 16 + 2 * segx2])
            deltas = struct.unpack(f">{segx2 // 2}h", ttf[sub + 16 + 2 * segx2:sub + 16 + 3 * segx2])
            ro_pos = sub + 16 + 3 * segx2
            ranges = struct.unpack(f">{segx2 // 2}H", ttf[ro_pos:ro_pos + segx2])
            for k, (s, e) in enumerate(zip(starts, ends)):
                for c in range(s, e + 1):
                    if c == 0xFFFF:
                        continue
                    if ranges[k] == 0:
                        g = (c + deltas[k]) & 0xFFFF
                    else:
                        p = ro_pos + 2 * k + ranges[k] + 2 * (c - s)
                        g = struct.unpack(">H", ttf[p:p + 2])[0]
                        g = (g + deltas[k]) & 0xFFFF if g else 0
                    if g:
                        kody.add(c)
        elif fmt == 12:
            ng = struct.unpack(">I", ttf[sub + 12:sub + 16])[0]
            for j in range(ng):
                s, e, _ = struct.unpack(">III", ttf[sub + 16 + 12 * j:sub + 28 + 12 * j])
                kody.update(range(s, e + 1))
    return kody


def shrift(semeistva):
    vse_ok = True
    for fam in semeistva:
        tekst = RU + KY + KK
        url = "https://fonts.googleapis.com/css2?family=" + urllib.parse.quote(fam) + "&text=" + urllib.parse.quote(tekst)
        try:
            css = get(url).decode("utf-8")
        except urllib.error.HTTPError:
            print(f"✗ {fam}: нет такого шрифта в Google Fonts (проверь написание на fonts.google.com)")
            vse_ok = False
            continue
        est = set()
        for u in re.findall(r"url\((https://[^)]+)\)", css):
            est |= cmap(get(u))
        net = lambda bukvy: "".join(b for b in bukvy if ord(b) not in est)
        ru, ky, kk = net(RU), net(KY), net(KK)
        stroka = (f"{fam}: русский {'✓' if not ru else '✗ нет ' + ru} · кыргызский {'✓' if not ky else '✗ нет ' + ky}"
                  f" · казахский {'✓' if not kk else '✗ нет ' + kk}")
        print(("✓ " if not (ru or ky) else "✗ ") + stroka)
        vse_ok &= not (ru or ky)
    print("ИТОГ: " + ("все шрифты годятся для русского и кыргызского" if vse_ok else "есть шрифт без нужных букв — замени его"))


def lum(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def kontrast(a, b):
    l1, l2 = sorted((lum(a), lum(b)), reverse=True)
    k = (l1 + 0.05) / (l2 + 0.05)
    if k >= 7:
        v = "отлично, читается везде"
    elif k >= 4.5:
        v = "хорошо для обычного текста и субтитров"
    elif k >= 3:
        v = "только для крупных заголовков, мелкий текст не читается"
    else:
        v = "плохо: на телефоне не прочитать, поменяй цвет"
    print(f"{a} и {b}: контраст {k:.1f} : 1 — {v}")


def otkryt():
    import webbrowser
    f = proekty() / "мозг" / "бренд" / "брендбук.html"
    if not f.exists():
        print(f"Нет файла {f}")
        sys.exit(1)
    print(("Открыл: " if webbrowser.open(f.as_uri()) else "Открой вручную: ") + str(f))


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
    elif a[0] == "shrift" and len(a) > 1:
        shrift(a[1:])
    elif a[0] == "kontrast" and len(a) == 3:
        kontrast(a[1], a[2])
    elif a[0] == "otkryt":
        otkryt()
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
